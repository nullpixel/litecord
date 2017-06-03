import asyncio
import json
import logging
import time
import subprocess
import random
import collections

import motor.motor_asyncio

from .snowflake import get_raw_token
from .utils import strip_user_data, random_digits, _json, _err, get_random_salt, pwd_hash
from .guild import GuildManager
from .presence import PresenceManager
from .voice import VoiceManager
from .api import users, guilds, channels, imgs, invites, admin
from .objects import User
from .images import Images
from .embedder import EmbedManager
from .err import ConfigError

log = logging.getLogger(__name__)


BOILERPLATES = {
    'user': 'boilerplate_data/users.json',
    'guild': 'boilerplate_data/guilds.json',
}


LOADING_LINES = [
    'Loading...',
]


API_PREFIXES = [
    '/api',
    '/api/v5',
    '/api/v6',
    '/api/v7'
]


def check_configuration(flags):
    required_fields = ['server', 'ratelimits', 'images', 'boilerplate.update']
    for field in required_fields:
        if field not in flags:
            raise ConfigError(f"Field {field!r} not found in configuration")


class LitecordServer:
    """Main class for the Litecord server.

    .. _AsyncIOMotorClient: https://motor.readthedocs.io/en/stable/api-asyncio/asyncio_motor_client.html
    .. _Connection: connecting.html
    .. _GuildManager: guild.html
    .. _PresenceManager: presence.html

    Arguments
    ---------
    flags : dict
        Server configuration flags.
    loop : event loop
        Event loop used for ``asyncio``.

    Attributes
    ----------
    flags : dict
        Server configuration.
    loop : event loop
        asyncio event loop.
    mongo_client : `AsyncIOMotorClient`_
        MongoDB Client.
    event_cache : dict
        Relates user IDs to the last events they received. Used for resuming.
    cache : dict
        Relates IDs to objects/raw objects.
    valid_tokens : list
        List of valid tokens(strings).
        A valid token is a token that was used in a connection and it is still,
        being used in that connection.
    sessions : dict
        Relates session IDs to their respective `Connection`_ object.
    guild_man : `GuildManager`_
        meme.
    presence : `PresenceManager`_
        meme.
    """
    def __init__(self, flags=None, loop=None):
        if flags is None:
            flags = {}

        self.flags = flags
        check_configuration(flags)

        self.rest_ratelimits = {}
        self.ws_ratelimits = {}

        # if anybody needs
        self.loop = loop
        if loop is None:
            self.loop = asyncio.get_event_loop()

        # mongodb stuff
        self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient()
        self.litecord_db = self.mongo_client['litecord']

        self.message_db =   self.litecord_db['messages']
        self.user_db =      self.litecord_db['users']
        self.guild_db =     self.litecord_db['gulids']
        self.token_db =     self.litecord_db['tokens']
        self.invite_db =    self.litecord_db['invites']
        self.member_db =    self.litecord_db['members']

        # cache for events
        self.event_cache = {}

        # cache for objects
        self.cache = {}

        self.session_dict = {}
        self.atomic_markers = {}
        self.sessions = {}

        self.request_counter = collections.defaultdict(int)
        self.connections = collections.defaultdict(list)

        self.presence = None
        self.guild_man = None
        self.app = None

        self.litecord_version = subprocess.check_output("git rev-parse HEAD", \
            shell=True).decode('utf-8').strip()

    def add_connection(self, user_id, conn):
        """Add a connection and tie it to a user.

        Parameters
        ----------
        user_id: int
            The user that is going to have this connection referred to.
        conn: :class:`Connection`
            Connection object.
        """
        user_id = int(user_id)
        log.debug(f"Adding sid={conn.session_id} to uid={user_id}")

        self.connections[user_id].append(conn)
        self.sessions[conn.session_id] = conn

    def remove_connection(self, session_id):
        """Remove a connection from the connection table."""
        session_id = str(session_id)

        try:
            conn = self.sessions.pop(session_id)
        except:
            return

        try:
            user_id = conn.user.id
        except:
            return

        log.debug(f"Removing sid={session_id} from uid={user_id}")

        ref = self.connections[user_id]
        for i, conn in enumerate(ref):
            if conn.session_id == session_id:
                del ref[i]
                break

    def get_connections(self, user_id):
        for conn in self.connections[user_id]:
            yield conn

    def count_connections(self, user_id):
        return len(self.connections[user_id])

    async def boilerplate_init(self):
        """Load boilerplate data."""

        b_flags = self.flags.get('boilerplate.update')

        for key in BOILERPLATES:
            path = BOILERPLATES[key]
            data = None
            with open(path, 'r') as f:
                data = json.loads(f.read())

            db_to_update = getattr(self, f'{key}_db')

            tot = 0


            for element in data:
                existing = await db_to_update.find_one({'id': element['id']})
                if (existing is not None) and not (b_flags.get(key)):
                    continue

                await db_to_update.replace_one({'id': element['id']}, element, True)
                tot += 1

            log.info(f"[boilerplate] Replaced {tot} elements in {key!r}")

    async def load_users(self):
        """Load users database using MongoDB.

        Creates the `id->raw_user` and `id->user` dictionaries in `LitecordServer.cache`.
        """

        # create cache objects
        self.cache['id->raw_user'] = {}
        self.cache['id->user'] = {}
        self.cache['token->userid'] = {}

        # reference them
        id_to_raw_user = self.cache['id->raw_user']
        id_to_user = self.cache['id->user']

        cursor = self.user_db.find()
        all_users = await cursor.to_list(length=None)

        for raw_user in all_users:
            pwd = raw_user['password']

            if len(pwd['salt']) < 1:
                pwd['salt'] = get_random_salt()

            if len(pwd['hash']) < 1 and len(pwd['salt']) > 0:
                pwd['hash'] = pwd_hash(pwd['plain'], pwd['salt'])
                pwd['plain'] = None

            # put that into the database
            await self.user_db.find_one_and_replace({'id': raw_user['id']}, raw_user)

            # cache objects
            user = User(self, raw_user)
            id_to_raw_user[user.id] = raw_user
            id_to_user[user.id] = user

        log.info(f"Loaded {len(all_users)} users")

    async def userdb_update(self):
        """Update the server's user cache.

        Dispatches USER_UPDATE events to respective clients.
        """
        cursor = self.user_db.find()
        all_users = await cursor.to_list(length=None)

        updated_users = 0
        events = 0

        raw_user_cache = self.cache['id->raw_user']
        user_cache = self.cache['id->user']

        for raw_user in all_users:
            raw_user = strip_user_data(raw_user)

            raw_user_id = int(raw_user['id'])

            cached_raw_user = strip_user_data(raw_user_cache[raw_user_id])
            cached_user = user_cache[raw_user_id]

            differences = set(raw_user.values()) ^ set(cached_raw_user.values())
            if len(differences) > 0:
                user = User(self, raw_user)

                # dispatch USER_UPDATE to all online clients
                for guild in user.guilds:
                    for member in guild.online_members:
                        conn = member.connection
                        await conn.dispatch('USER_UPDATE', user.as_json)
                        events += 1

                # update the references in internal cache
                cached_raw_user = raw_user
                cached_user = user

                updated_users += 1

        log.info(f'[userdb_update] Updated {updated_users} users, dispatched {events} events')

    # helpers
    def get_raw_user(self, user_id):
        """Get a raw user object using the user's ID."""
        user_id = int(user_id)
        users = self.cache['id->raw_user']
        return users.get(user_id)

    def get_user(self, user_id):
        """Get a `User` object using the user's ID."""
        try:
            user_id = int(user_id)
        except:
            return None
        return self.cache['id->user'].get(user_id)

    async def get_raw_user_email(self, email):
        """Get a raw user object from a user's email."""
        raw_user = await self.user_db.find_one({'email': email})

        self.cache['id->raw_user'][raw_user['id']] = raw_user

        if raw_user['id'] not in self.cache['id->user']:
            self.cache['id->user'][raw_user['id']] = User(self, raw_user)

        return raw_user

    def _user(self, token):
        """Get a user object from its token.

        This is a helper function to save lines of code in endpoint objects.
        """
        try:
            userid = self.cache['token->userid'][token]
        except:
            return None

        return self.get_user(userid)

    # token helper functions
    async def token_userid(self, user_id):
        """Find a token from a user's ID."""
        return (await self.token_db.find_one({'user_id': str(user_id)}))

    async def token_find(self, token):
        """Return a user ID from a token."""
        res = await self.token_db.find_one({'token': str(token)})
        try:
            return res.get('user_id')
        except AttributeError:
            log.warning("No object found")
            return None

    async def token_used(self, token):
        """Returns `True` if the token is alredy used by other account."""
        obj = await self.token_find(token)
        return bool(obj)

    async def token_unregister(self, token):
        """Detach a token from a user."""
        if token is None:
            return True

        res = await self.token_db.delete_one({'token': str(token)})
        return res.deleted_count > 0

    async def token_register(self, token, user_id):
        """Attach a token to a user."""
        log.info(f"Registering {token} to {user_id}")
        res = self.token_db.insert_one({'token': str(token), 'user_id': str(user_id)})
        return res

    async def check(self):
        """Returns a dictionary with check data."""

        report = {
            'good': True
        }

        t1 = time.monotonic()
        result = await self.mongo_client.admin.command({'ping': 1})
        t2 = time.monotonic()

        mongo_ping_msec = round((t2 - t1) * 1000, 4)
        report['mongo_ping'] = mongo_ping_msec

        # dude the mongodb is local 5ms would be alarming
        if mongo_ping_msec > 3:
            report['good'] = False

        return report

    async def h_get_version(self, request):
        """`GET /version`.

        Get the server's git revision.
        This endpoint doesn't require authentication.

        Returns
        -------
        dict:
            With a `version` key
        """

        return _json({
            'version': self.litecord_version,
        })

    async def h_give_gateway(self, request):
        ws = self.flags['server']['ws']
        if len(ws) == 2:
            return _json({"url": f"ws://{ws[0]}:{ws[1]}"})
        elif len(ws) == 3:
            return _json({"url": f"ws://{ws[2]}:{ws[1]}"})

    async def login(self, request):
        """Login a user through the `POST /auth/login` endpoint.

        With the provided token you can connect to the
        gateway and send an IDENTIFY payload.

        Parameters
        ----------
        request: dict
            Two keys, `email` and `password`, password is in plaintext.

        Returns
        -------
        dict:
            With a `token` field.
        """
        try:
            payload = await request.json()
        except Exception as err:
            # error parsing json
            return _err("error parsing")

        email = payload.get('email')
        password = payload.get('password')
        if email is None or password is None:
            return _err("malformed packet")

        raw_user = await self.get_raw_user_email(email)
        if raw_user is None:
            return _err("fail on login [email]")

        pwd = raw_user['password']
        if pwd_hash(password, pwd['salt']) != pwd['hash']:
            return _err("fail on login [password]")

        user_id = raw_user['id']
        old_token = await self.token_userid(user_id)

        new_token = await get_raw_token()
        while (await self.token_used(new_token)):
            new_token = await get_raw_token()

        await self.token_unregister(old_token)

        log.info(f"[login] Generated new token for {user_id}")
        await self.token_register(new_token, user_id)

        return _json({"token": new_token})

    async def check_request(self, request):
        """Checks a request to the API.

        This function checks if the request has the required methods
        to do any authenticated request to Litecord's API.

        More information at:
        https://discordapp.com/developers/docs/reference#authentication

        NOTE: This function doesn't check for OAuth2 Bearer tokens.
        """
        auth_header = request.headers.get('Authorization')
        if auth_header is None:
            return _err('401: Unauthorized, no token provided')

        if len(auth_header) < 1:
            return _err('401: Unauthorized, Malformed request')

        try:
            token_type, token_value = auth_header.split()
        except:
            if auth_header.startswith('litecord_'):
                token_type = 'Bot'
                token_value = auth_header
            else:
                log.info(f"Received weird auth header: {auth_header!r}")
                return _err('error parsing Authorization header')

        if token_type != 'Bot':
            return _err('401: Unauthorized, Invalid token type')

        # check if token is valid
        raw_token_object = await self.token_db.find_one({'token': token_value})
        if raw_token_object is None:
            return _err(f'401: Unauthorized, Invalid token {token_value!r}')

        # NOTE: this doesn't remove any token from cache, we need to check that
        # this is a quickfix.
        self.cache['token->userid'][token_value] = raw_token_object['user_id']

        return _json({
            'code': 1,
            'token': token_value,
        })

    async def get_discrim(self, username):
        """Generate a discriminator from a username."""

        cursor = self.user_db.find({
            'username': username
        })
        raw_user_list = await cursor.to_list(length=None)
        used_discrims = [raw_user['discriminator'] for raw_user in raw_user_list]

        # only 8000 discrims per user
        if len(used_discrims) >= 8000:
            return None

        discrim = str(random_digits(4))

        while True:
            try:
                # list.index raises IndexError if the element isn't found
                used_discrims.index(discrim)
                discrim = str(random_digits(4))
            except ValueError:
                log.info(f'[discrim] Generated discrim {discrim!r} for {username!r}')
                return discrim

    async def make_counts(self):
        """Return a dictionary with some counts."""
        return {
            'user_count': len(self.cache['id->raw_user']),
            'guild_count': len(self.guild_man.guilds),
            'channel_count': len(self.guild_man.channels),
            'presence_count': await self.presence.count_all(),
        }

    def add_get(self, route_path, route_handler):
        _r = self.app.router

        routes = [f'{prefix}/{route_path}' for prefix in API_PREFIXES]
        for route in routes:
            _r.add_get(route, route_handler)

    def add_post(self, route_path, route_handler):
        _r = self.app.router

        routes = [f'{prefix}/{route_path}' for prefix in API_PREFIXES]
        for route in routes:
            _r.add_post(route, route_handler)

    def add_put(self, route_path, route_handler):
        _r = self.app.router

        routes = [f'{prefix}/{route_path}' for prefix in API_PREFIXES]
        for route in routes:
            _r.add_put(route, route_handler)

    def add_patch(self, route_path, route_handler):
        _r = self.app.router

        routes = [f'{prefix}/{route_path}' for prefix in API_PREFIXES]
        for route in routes:
            _r.add_patch(route, route_handler)

    def add_delete(self, route_path, route_handler):
        _r = self.app.router

        routes = [f'{prefix}/{route_path}' for prefix in API_PREFIXES]
        for route in routes:
            _r.add_delete(route, route_handler)

    async def init(self, app):
        """Initialize the server.

        Loads databases, managers and endpoints.
        """
        try:
            t_init = time.monotonic()

            self.app = app

            log.debug("[load] boilerplate data")
            await self.boilerplate_init()

            log.debug('[load] user database')
            await self.load_users()

            log.debug('[load] Images')
            self.images = Images(self, self.flags.get('images', {}))

            log.debug('[init] GuildManager')
            self.guild_man = GuildManager(self)
            await self.guild_man.init()

            log.debug('[init] PresenceManager')
            self.presence = PresenceManager(self)

            log.debug('[init] EmbedManager')
            self.embed = EmbedManager(self)
            self.embed.init(app)

            log.debug('[init] VoiceManager')
            self.voice = VoiceManager(self)
            self.voice_task = self.loop.create_task(self.voice.init_task(self.flags))

            log.debug('[init] endpoint objects')
            self.users_endpoint = users.UsersEndpoint(self)
            self.users_endpoint.register(app)

            self.guilds_endpoint = guilds.GuildsEndpoint(self)
            self.guilds_endpoint.register(app)

            self.channels_endpoint = channels.ChannelsEndpoint(self)
            self.channels_endpoint.register(app)

            self.invites_endpoint = invites.InvitesEndpoint(self)
            self.invites_endpoint.register(app)

            self.images_endpoint = imgs.ImageEndpoint(self)
            self.images_endpoint.register(app)

            self.admins_endpoint = admin.AdminEndpoints(self)
            self.admins_endpoint.register(app)

            # setup internal stuff
            self.add_post('auth/login', self.login)
            self.add_get('version', self.h_get_version)
            self.add_get('gateway', self.h_give_gateway)

            t_end = time.monotonic()
            delta = round((t_end - t_init) * 1000, 2)

            log.info(f"[server] Loaded in {delta}ms")
            return True
        except:
            log.error('Error when initializing LitecordServer', exc_info=True)
            return False
