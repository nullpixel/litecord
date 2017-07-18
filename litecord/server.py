import asyncio
import json
import logging
import time
import subprocess
import collections
import base64
import binascii

import motor.motor_asyncio
import itsdangerous
from aiohttp import web
from itsdangerous import Signer

import litecord.api as api
from .basics import OP
from .utils import strip_user_data, random_digits, _json, _err, get_random_salt, pwd_hash
from .guild import GuildManager
from .presence import PresenceManager
from .voice.server import VoiceManager
from .objects import User
from .images import Images
from .embedder import EmbedManager
from .err import ConfigError, RequestCheckError
from .ratelimits import WSBucket, GatewayRatelimitModes
from .user_settings import SettingsManager
from .relations import RelationsManager

log = logging.getLogger(__name__)


BOILERPLATES = {
    'user': 'boilerplate_data/users.json',
    'guild': 'boilerplate_data/guilds.json',
    'channel': 'boilerplate_data/channels.json',
    'role': 'boilerplate_data/roles.json',
}


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


def empty_ev_cache():
    """Return an empty event cache."""
    return {
        'sent_seq': 0,
        'recv_seq': 0,
        'events': {},
    }


class LitecordServer:
    """Main class for the Litecord server.

    .. _AsyncIOMotorClient: https://motor.readthedocs.io/en/stable/api-asyncio/asyncio_motor_client.html

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
    valid_tokens: list
        List of valid tokens(strings).
        A valid token is a token that was used in a connection and it is still,
        being used in that connection.
    sessions: dict
        Relates session IDs to their respective :class:`Connection` object.
    guild_man: :class:`GuildManager`
        Guild manager instance.
    presence: :class:`PresenceManager`
        Presence manager instance.
    request_counter: `collections.defaultdict(dict)`
        Manages request counts for all identified connections.
    connections: `collections.defaultdict(list)`
        List of all connections that are linked to a User ID.
    buckets: dict
        Ratelimit bucket objects.
    """
    def __init__(self, flags=None, loop=None):
        if flags is None:
            flags = {}

        self.flags = flags
        check_configuration(flags)
        self.accept_clients = True

        self.rest_ratelimits = {}
        self.ws_ratelimits = {}

        # if anybody needs
        self.loop = loop
        if loop is None:
            self.loop = asyncio.get_event_loop()

        # mongodb stuff
        self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient()
        self.litecord_db = self.mongo_client[self.flags.get('mongo_name', 'litecord')]

        self.message_coll = self.litecord_db['messages']
        self.user_coll = self.litecord_db['users']
        self.guild_coll = self.litecord_db['gulids']
        self.channel_coll = self.litecord_db['channels']
        self.role_coll = self.litecord_db['roles']
        self.token_coll = self.litecord_db['tokens']
        self.invite_coll = self.litecord_db['invites']
        self.member_coll = self.litecord_db['members']
        self.presence_coll = self.litecord_db['presences']
        self.settings_coll = self.litecord_db['settings']
        self.relations_coll = self.litecord_db['relations']

        # cache for events
        self.event_cache = collections.defaultdict(empty_ev_cache)

        # cache for all kinds of objects
        self.cache = {}

        self.session_dict = {}
        self.atomic_markers = {}
        self.sessions = {}

        self.request_counter = collections.defaultdict(dict)
        self.connections = collections.defaultdict(list)

        self.presence = None
        self.guild_man = None
        self.app = None

        self.litecord_version = subprocess.check_output("git rev-parse HEAD", \
            shell=True).decode('utf-8').strip()

        default = [120, 60]
        rtl_config = flags['ratelimits']

        global_req, global_sec = rtl_config.get('global_ws', default)

        close = GatewayRatelimitModes.CLOSE
        ignore = GatewayRatelimitModes.IGNORE_PACKET

        self.buckets = {
            'all': WSBucket('all', requests=global_req, seconds=global_sec, mode=close),
            'presence_updates': WSBucket('presence_updates', requests=5, seconds=60, mode=ignore),
            'identify': WSBucket('identify', requests=1, seconds=5, mode=close)
        }

    def add_connection(self, user_id: int, conn):
        """Add a connection and tie it to a user.

        Parameters
        ----------
        user_id: int
            The user that is going to have this connection referred to.
        conn: :class:`Connection`
            Connection object.
        """
        user_id = int(user_id)
        log.debug('Adding sid=%s to uid=%d', conn.session_id, user_id)

        if conn.sharded:
            log.debug('Adding a shard (%d).', conn.shard_id)

        self.connections[user_id].append(conn)
        self.sessions[conn.session_id] = conn

    def remove_connection(self, session_id: str):
        """Remove a connection from the connection table.
        
        Parameters
        ----------
        session_id: str
            Session ID of the connection to be removed.
        """
        session_id = str(session_id)

        try:
            self.request_counter.pop(session_id)
        except KeyError:
            pass

        try:
            conn = self.sessions.pop(session_id)
        except KeyError:
            return

        try:
            # not identified
            user_id = conn.user.id
        except AttributeError:
            return

        log.debug(f"Removing sid={session_id} from uid={user_id}")

        ref = self.connections[user_id]
        for i, conn in enumerate(ref):
            if conn.session_id == session_id:
                del ref[i]
                break

    def get_connections(self, user_id):
        """Yield all connections that are connected to a user."""
        for conn in self.connections[user_id]:
            yield conn

    def count_connections(self, user_id):
        """Return the amount of connections connected to a user."""
        return len(self.connections[user_id])

    async def boilerplate_init(self):
        """Load boilerplate data.
        
        If the ``boilerplate.update`` config flag is set to ``True`` for each
        field, this function overwrites the boilerplate data with the
        current data, ignores if set to ``False``.
        """

        b_flags = self.flags.get('boilerplate.update')

        for key, path in BOILERPLATES.items():
            data = None
            with open(path, 'r') as f:
                try:
                    data = json.load(f)
                except Exception as err:
                    log.warning(f'[boilerplate] No boilerplate data found for field: {key!r}')

            coll = getattr(self, f'{key}_coll')

            tot = 0

            k_field = f'{key}_id'
            for element in data:
                query = {k_field: int(element[k_field])}

                existing = await coll.find_one(query)
                if (existing is not None) and not (b_flags.get(key)):
                    continue

                for k in element:
                    if 'id' in k:
                        try:
                            element[k] = int(element[k])
                        except: log.debug('failed to convert field %r to int in boilerplate object', k)
                await coll.replace_one(query, element, True)
                tot += 1

            log.info(f"[boilerplate] Replaced {tot} elements in {key!r}")

    async def load_users(self):
        """Load user collection.
        If the raw user in the collection doesn't have a hashed
        password in their object, a new one gets created(with a random salt)

        Fills the ``'id->raw_user'`` and ``'id->user'`` caches in :attr:`LitecordServer.cache`.
        """

        # create cache objects
        self.cache['id->raw_user'] = {}
        self.cache['id->user'] = {}

        # reference them
        id_to_raw_user = self.cache['id->raw_user']
        id_to_user = self.cache['id->user']

        cursor = self.user_coll.find()
        all_users = await cursor.to_list(length=None)

        for raw_user in all_users:
            pwd = raw_user['password']

            if len(pwd['salt']) < 1:
                pwd['salt'] = get_random_salt()

            if len(pwd['hash']) < 1 and len(pwd['salt']) > 0:
                pwd['hash'] = pwd_hash(pwd['plain'], pwd['salt'])
                pwd['plain'] = None

            # put that into the database
            raw_user.pop('_id')
            await self.user_coll.update_one({'user_id': raw_user['user_id']}, {'$set': raw_user})

            # cache objects
            user = User(self, raw_user)
            id_to_raw_user[user.id] = raw_user
            id_to_user[user.id] = user

        log.info(f"Loaded {len(all_users)} users")

    async def userdb_update(self):
        """Update the server's user cache with new data from the database.

        Only updates if actually required(differences between cache and database greater than 0).
        Dispatches USER_UPDATE events to respective clients.
        """
        cursor = self.user_coll.find()
        all_users = await cursor.to_list(length=None)

        updated_users = 0
        events = 0

        raw_user_cache = self.cache['id->raw_user']
        user_cache = self.cache['id->user']

        for raw_user in all_users:
            raw_user = strip_user_data(raw_user)

            raw_user_id = int(raw_user['user_id'])

            cached_raw_user = strip_user_data(raw_user_cache[raw_user_id])
            cached_user = user_cache[raw_user_id]

            differences = set(raw_user.values()) ^ set(cached_raw_user.values())
            if len(differences) > 0:
                user = User(self, raw_user)

                # dispatch USER_UPDATE to all online clients
                for guild in user.guilds:
                    events += await guild.dispatch('USER_UPDATE', user.as_json)

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
        """Get a :class:`User` object using the user's ID."""
        try:
            user_id = int(user_id)
        except:
            return None
        return self.cache['id->user'].get(user_id)

    async def get_raw_user_email(self, email):
        """Get a raw user object from a user's email."""
        raw_user = await self.user_coll.find_one({'email': email})

        self.cache['id->raw_user'][raw_user['user_id']] = raw_user

        if raw_user['user_id'] not in self.cache['id->user']:
            self.cache['id->user'][raw_user['user_id']] = User(self, raw_user)

        return raw_user

    async def _user(self, token):
        """Get a user object from its token.

        This is a helper function to save lines of code in endpoint objects.
        """
        user_id = await self.token_find(token)
        return self.get_user(user_id)

    async def generate_token(self, user_id: str):
        """Generate a very random token tied to an user.

        Parameters
        ----------
        userid: str
            User ID tied to that token
        """
        user_id = str(user_id)

        userid_encoded = base64.urlsafe_b64encode(user_id.encode())

        raw_user = self.get_raw_user(user_id)
        s = Signer(raw_user['password']['hash'])
        return s.sign(userid_encoded).decode()

    async def token_find(self, token: str) -> int:
        """Return a user ID from a token.
        
        Parses the token to get the user ID and then unsigns it
        using the user's hashed password as a secret key
        """
        b64 = lambda x: base64.urlsafe_b64decode(x)

        userid_encoded = token.split('.')[0]

        try:
            userid = int(b64(userid_encoded))
        except (binascii.Error, ValueError):
            return None

        raw_user = self.get_raw_user(userid)

        s = Signer(raw_user['password']['hash'])

        try:
            userid_encoded_ft = s.unsign(token)
        except itsdangerous.BadSignature:
            return None
        return userid

    async def check(self) -> dict:
        """Returns a dictionary with self-checking data.
        
        Used to determine the state of the server with:
         - Mongo ping
        """

        report = {
            'good': True
        }

        t1 = time.monotonic()
        result = await self.mongo_client.admin.command({'ping': 1})
        t2 = time.monotonic()

        mongo_ping_msec = round((t2 - t1) * 1000, 4)
        report['mongo_ping'] = mongo_ping_msec

        # dude the mongodb is local 7ms would be alarming
        if mongo_ping_msec > 7:
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

    def get_gateway_url(self):
        ws = self.flags['server']['ws']
        if len(ws) == 2:
            return f'ws://{ws[0]}:{ws[1]}'
        elif len(ws) == 3:
            return f"ws://{ws[2]}:{ws[1]}"

    async def check_request(self, request) -> 'tuple(str, int)':
        """Checks a request to the API.

        This function checks if a request has the required headers
        to do any authenticated request to Litecord's API.

        More information at:
        https://discordapp.com/developers/docs/reference#authentication

        NOTE: This function doesn't support OAuth2 Bearer tokens.
        """
        auth_header = request.headers.get('Authorization')
        if auth_header is None:
            return _err('401: Unauthorized, no token provided')
            raise RequestCheckError(_err('No token provided', status_code=401))

        if len(auth_header) < 1:
            raise RequestCheckError(_err('malformed header', status_code=401))

        try:
            token_type, token_value = auth_header.split()
        except:
            token_type = 'Bot'
            token_value = auth_header

        if token_type != 'Bot':
            raise RequestCheckError(_err('Invalid token type', status_code=401))

        try:
            user_id = await self.token_find(token_value)
        except itsdangerous.BadSignature:
            raise RequestCheckError(_err(f'Invalid token', status_code=401))

        return token_value, user_id

    async def get_discrim(self, username: str) -> str:
        """Generate a discriminator from a username."""

        cursor = self.user_coll.find({
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

    async def make_counts(self) -> dict:
        """Return a dictionary with some counts about the server."""
        return {
            'user_count': len(self.cache['id->raw_user']),
            'guild_count': len(self.guild_man.guilds),
            'channel_count': len(self.guild_man.channels),
            'presence_count': await self.presence.count_all(),
        }

    def make_options_handler(self, method):
        headers = {
            'Access-Control-Allow-Origin': 'http://127.0.0.1',
            'Access-Control-Allow-Methods': method,
            'Access-Control-Allow-Credentials': 'true',
            'Access-Control-Allow-Headers': 'Authorization, Content-Type',
        }

        async def options_handler(request):
            headers['Access-Control-Allow-Origin'] = request.headers['Origin'] 
            return web.Response(status=200, body='', headers=headers)

        return options_handler

    def add_empty(self, route, method):
        self.app.router.add_route('OPTIONS', route, self.make_options_handler(method))

    def add_get(self, route_path, route_handler):
        _r = self.app.router

        routes = [f'{prefix}/{route_path}' for prefix in API_PREFIXES]
        for route in routes:
            _r.add_get(route, route_handler)
            self.add_empty(route, 'GET')

    def add_post(self, route_path, route_handler):
        _r = self.app.router

        routes = [f'{prefix}/{route_path}' for prefix in API_PREFIXES]
        for route in routes:
            _r.add_post(route, route_handler)
            self.add_empty(route, 'POST')

    def add_put(self, route_path, route_handler):
        _r = self.app.router

        routes = [f'{prefix}/{route_path}' for prefix in API_PREFIXES]
        for route in routes:
            _r.add_put(route, route_handler)
            self.add_empty(route, 'PUT')

    def add_patch(self, route_path, route_handler):
        _r = self.app.router

        routes = [f'{prefix}/{route_path}' for prefix in API_PREFIXES]
        for route in routes:
            _r.add_patch(route, route_handler)
            self.add_empty(route, 'PATCH')

    def add_delete(self, route_path, route_handler):
        _r = self.app.router

        routes = [f'{prefix}/{route_path}' for prefix in API_PREFIXES]
        for route in routes:
            _r.add_delete(route, route_handler)
            self.add_empty(route, 'DELETE')

    async def init(self, app):
        """Initialize the server.

        Loads databases, managers and endpoint objects.
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

            log.debug('[init] VoiceManager')
            self.voice = VoiceManager(self)
            self.voice_task = self.loop.create_task(self.voice.init_task(self.flags))

            log.debug('[init] SettingsManager')
            self.settings = SettingsManager(self)

            log.debug('[init] RelationsManager')
            self.relations = RelationsManager(self)

            log.debug('[init] endpoints')
            self.gw_endpoint = api.GatewayEndpoint(self)
            self.users_endpoint = api.UsersEndpoint(self)
            self.guilds_endpoint = api.guilds.GuildsEndpoint(self)
            self.channels_endpoint = api.ChannelsEndpoint(self)
            self.invites_endpoint = api.InvitesEndpoint(self)
            self.images_endpoint = api.ImageEndpoint(self)
            self.admins_endpoint = api.AdminEndpoints(self)
            self.auth_endpoint = api.AuthEndpoints(self)
            self.voice_endpoint = api.VoiceEndpoint(self)

            self.add_get('version', self.h_get_version)

            t_end = time.monotonic()
            delta = round((t_end - t_init) * 1000, 2)

            log.info(f"[server] Loaded in {delta}ms")
            return True
        except:
            log.error('Error when initializing LitecordServer', exc_info=True)
            return False

    async def shutdown_conn(self, conn):
        """Shutdown a connection.

        Sends an OP 7 Reconnect packet and waits 3 seconds so that the
        connection is closed client-side, if the client doesn't close
        in time, the server closes it.
        """
        await conn.send_op(OP.RECONNECT)
        await asyncio.sleep(2)
        if conn.ws.open:
            await conn.ws.close(4000, 'Shutdown procedure')

    def shutdown(self):
        """Send a reconnect packet to all available connections,
        and make the gateway stop receiving new ones.

        Closes the event loop.
        """
        self.accept_clients = False

        loop = self.loop

        reconnect_tasks = []
        sent = 0
        for (_, conn) in self.sessions.items():
            reconnect_tasks.append(loop.create_task(self.shutdown_conn(conn)))
            sent += 1

        rtasks_gathered = asyncio.gather(*reconnect_tasks, loop=loop)
        log.info('[shutdown] Sending op 7 reconnect to %d connections', sent)

        # finish sending RECONNECT to everyone, plz.
        loop.run_until_complete(rtasks_gathered)

        pending = asyncio.Task.all_tasks(loop=loop)
        gathered = asyncio.gather(*pending, loop=loop)

        try:
            gathered.cancel()
            loop.run_until_complete(gathered)
            gathered.exception()
        except:
            pass

        loop.close()
