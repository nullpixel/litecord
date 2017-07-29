import asyncio
import json
import logging
import time
import subprocess
import collections
import base64
import binascii
import pathlib
import os
import pprint

import motor.motor_asyncio
import itsdangerous
from aiohttp import web
from itsdangerous import TimestampSigner

import litecord.api as api
import litecord.managers as managers

from .enums import OP
from .utils import random_digits, _json, _err, get_random_salt, \
    pwd_hash, get, delete

from .voice.server import VoiceManager

from .objects import User
from .err import ConfigError, RequestCheckError
from .ratelimits import WSBucket, GatewayRatelimitModes


log = logging.getLogger(__name__)


BOILERPLATES = {
    'user': 'boilerplate_data/users.json',
    'guild': 'boilerplate_data/guilds.json',
    'channel': 'boilerplate_data/channels.json',
    'role': 'boilerplate_data/roles.json',
}


API_PREFIXES = [
    '/api',
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
        'shard_id': 0,
        'shard_count': 0,
        'properties': None,

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
    flags: dict
        Server configuration.
    loop: event loop
        asyncio event loop.
    accept_clients: bool
        If the server accepts new clients through REST or the Gateway.
    endpoints: int
        Amount of declared endpoints on the server(:meth:`Litecord.compliance` fills it)
    good: `asyncio.Event`
        Set when the server has a "good" cache, if it is filled
        with all the information from the collections it needs.

    mongo_client: `AsyncIOMotorClient`_
        MongoDB Client.
    event_cache: dict
        Relates user IDs to the last events they received. Used for resuming.
    
    users: list[:class:`User`]
        Cache of user objects.
    raw_users: dict
        Cache of raw user objects.

    atomic_markers: dict
        Relates session IDs to bools representing
        if that session comes from Atomic Discord.
    sessions: dict
        Relates session IDs to their respective :class:`Connection` object.
    connections: dict
        Relates user IDs to a list of :class:`Connection` objects tied to them.

    images: :class:`Images`
        Image manager instance.
    guild_man: :class:`GuildManager`
        Guild manager instance.
    presence: :class:`PresenceManager`
        Presence manager instance.
    embed: :class:`EmbedManager`
        Embed manager instance.
    voice: :class:`VoiceManager`
        Voice manager instance.
    settings: :class:`SettingsManager`
        Settings manager instance.
    relations: :class:`RelationsManager`
        Relationship manager instance.
    apps: :class:`ApplicationManager`
        Application manager instance.

    request_counter: `collections.defaultdict(dict)`
        Manages request counts for all identified connections.
    buckets: dict
        Ratelimit bucket objects.
    """
    def __init__(self, flags=None, loop=None):
        if flags is None:
            flags = {}

        self.flags = flags
        check_configuration(flags)
        self.accept_clients = True
        self.endpoints = 0
        self.good = asyncio.Event()

        self.rest_ratelimits = {}
        self.ws_ratelimits = {}

        # if anybody needs
        self.loop = loop
        if loop is None:
            self.loop = asyncio.get_event_loop()

        # mongodb stuff
        self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient()
        self.litecord_db = self.mongo_client[self.flags.get('mongo_name', 'litecord')]

        # jesus christ the amount of collections
        self.message_coll = self.litecord_db['messages']
        self.user_coll = self.litecord_db['users']
        self.guild_coll = self.litecord_db['gulids']
        self.channel_coll = self.litecord_db['channels']
        self.role_coll = self.litecord_db['roles']
        self.invite_coll = self.litecord_db['invites']
        self.member_coll = self.litecord_db['members']
        self.presence_coll = self.litecord_db['presences']

        self.settings_coll = self.litecord_db['settings']
        self.relations_coll = self.litecord_db['relations']

        self.app_coll = self.litecord_db['applications']
        self.webhook_coll = self.litecord_db['webhooks']

        # cache for dispatched packets
        # used for resuming
        self.event_cache = collections.defaultdict(empty_ev_cache)

        self.users = []
        self.raw_users = {}

        self.atomic_markers = {}
        self.sessions = {}

        self.request_counter = collections.defaultdict(dict)
        self.connections = collections.defaultdict(list)

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
        except KeyError: pass

        try:
            conn = self.sessions.pop(session_id)
        except KeyError: return

        try:
            user_id = conn.user.id
        except AttributeError: return

        log.debug('Removing sid=%s from uid=%d', session_id, user_id)

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

    def get_shards(self, user_id: int) -> 'dict':
        """Get all shards for a user
        
        Returns
        -------
        dict
            Relating Shard IDs to :class:`Connection` objects.
        """
        shards = {}

        for conn in self.get_connections(user_id):
            if conn.sharded:
                shards[conn.shard_id] = conn

        return shards

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
        """Load the user collection into the server's cache.
        
        While loading, it can generate a salt and hash for the password
        if the data is not provided.
        """

        self.users = []
        self.raw_users = {}

        cur = self.user_coll.find()

        count = 0
        async for raw_user in cur:
            raw_user.pop('_id')
            uid = raw_user['user_id']
            password = raw_user['password']

            if len(password['salt']) < 1:
                password['salt'] = await get_random_salt()

            # generate password if good
            if len(password['hash']) < 1:
                password['hash'] = pwd_hash(password['plain'], password['salt'])
                # we are trying to be secure here ok
                password.pop('plain')

            query = {'user_id': uid}
            await self.user_coll.update_one(query, {'$set': {'password': password}})

            # add to cache
            self.users.append(User(self, raw_user))
            self.raw_users[uid] = raw_user

            count += 1

        log.info('Loaded %d users', count)

    async def reload_user(self, user):
        """Update the user cache with an existing user object."""
        raw_user = await self.user_coll.find_one({'user_id': user.id})
        raw_user.pop('_id')

        if raw_user is None:
            # non-existing
            try:
                self.users.remove(user)
            except ValueError: pass

            try:
                self.raw_users.pop(user.id)
            except KeyError: pass

            del user
            return

        user._raw.update(raw_user)
        user._update(user._raw)
        return user

    async def insert_user(self, raw_user):
        old = await self.user_coll.find_one({'user_id': user.id})
        if old is not None:
            log.warning('Inserting an existing user, ignoring')
            return

        uid = raw_user['user_id']
        await self.user_coll.insert_one(raw_user)
        self.raw_users[uid] = raw_user
        self.users.append(User(self, raw_user))
        return True

    def get_raw_user(self, user_id):
        """Get a raw user object using the user's ID."""
        user_id = int(user_id)
        u = self.raw_users.get(user_id)

        # no one should use the _id field tbh
        try:
            u.pop('_id')
        except: pass

        log.debug('[get:raw_user] %d -> %r', user_id, u.keys())
        return u

    def get_user(self, user_id):
        """Get a :class:`User` object using the user's ID."""
        user_id = int(user_id)
        u = get(self.users, id=user_id)
        log.debug('[get:user] %d -> %r', user_id, u)
        return u

    async def get_raw_user_email(self, email):
        """Get a raw user object from a user's email."""
        raw_user = await self.user_coll.find_one({'email': email})
        try:
            keys = raw_user.keys()
        except:
            keys = None
        log.debug('[get:raw_user:email] %r -> %r', email, keys)
        return raw_user

    async def _user(self, token):
        """Get a user object from its token.

        This is a helper function to save lines of code in endpoint objects.
        """
        # TODO: delet this
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
        if raw_user is None:
            raise Exception('User not found to generate a token from')

        try:
            pwd_hash = raw_user['password']['hash']
        except:
            log.debug(raw_user)
            raise Exception('Raw user is not a good one')

        s = TimestampSigner(pwd_hash)
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

        s = TimestampSigner(raw_user['password']['hash'])

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

        # dude the mongodb is local 10ms would be alarming
        if mongo_ping_msec > 10:
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
        url = f'ws://{ws[2] if len(ws) == 3 else ws[0]}:{ws[1]}'
        return url

    async def check_request(self, request) -> 'tuple':
        """Checks a request to the API.

        This function checks if a request has the required headers
        to do any authenticated request to Litecord's API.

        More information at:
        https://discordapp.com/developers/docs/reference#authentication

        NOTE: This function doesn't support OAuth2 Bearer tokens.

        Returns
        -------
        tuple
            With the token value and the user ID that
            the token references.

        Raises
        ------
        :class:`RequestCheckError`
            On any error with the request data
        """
        auth_header = request.headers.get('Authorization')
        if auth_header is None:
            raise RequestCheckError(_err('No header provided', status_code=401))

        if len(auth_header) < 1:
            raise RequestCheckError(_err('Malformed header', status_code=401))

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

        # only 9500 discrims per user
        # because I want to.
        if len(used_discrims) >= 9500:
            return None

        discrim = str(await random_digits(4))

        while True:
            try:
                used_discrims.index(discrim)
                discrim = str(await random_digits(4))
            except ValueError:
                log.info(f'[get:discrim] Generated discrim {discrim!r} for {username!r}')
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
        """Returns a handler for `OPTIONS`."""
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

        self.endpoints += 1
        routes = [f'{prefix}/{route_path}' for prefix in API_PREFIXES]
        for route in routes:
            _r.add_get(route, route_handler)
            self.add_empty(route, 'GET')

    def add_post(self, route_path, route_handler):
        _r = self.app.router

        self.endpoints += 1
        routes = [f'{prefix}/{route_path}' for prefix in API_PREFIXES]
        for route in routes:
            _r.add_post(route, route_handler)
            self.add_empty(route, 'POST')

    def add_put(self, route_path, route_handler):
        _r = self.app.router

        self.endpoints += 1
        routes = [f'{prefix}/{route_path}' for prefix in API_PREFIXES]
        for route in routes:
            _r.add_put(route, route_handler)
            self.add_empty(route, 'PUT')

    def add_patch(self, route_path, route_handler):
        _r = self.app.router

        self.endpoints += 1
        routes = [f'{prefix}/{route_path}' for prefix in API_PREFIXES]
        for route in routes:
            _r.add_patch(route, route_handler)
            self.add_empty(route, 'PATCH')

    def add_delete(self, route_path, route_handler):
        _r = self.app.router

        self.endpoints += 1
        routes = [f'{prefix}/{route_path}' for prefix in API_PREFIXES]
        for route in routes:
            _r.add_delete(route, route_handler)
            self.add_empty(route, 'DELETE')

    def compliance(self):
        """Measure compliance with the Server's routes"""
        methods = ('DELETE', 'GET', 'PATCH', 'POST', 'PUT', 'PUT/PATCH')
        endpoints = []

        scopes = collections.Counter()
        found_scopes = collections.Counter()

        raw = (pathlib.Path(__file__).resolve().parents[0] / 'discord-endpoints.txt').read_text()
        for line in raw.split('\n'):
            for method_find in methods:
                method = line.find(method_find)
                if method == -1:
                    continue

                name = line[:method].strip()
                endpoint = line[method+len(method_find):].strip()

                endpoints.append((name, method_find, endpoint))

                scope = endpoint.split('/')[1]
                scopes[scope] += 1

        routes = self.app.router.routes()
        routes = list(routes)

        found = []
        for epoint_name, epoint_method, epoint in endpoints:
            _flag = False

            for route in routes:
                if _flag:
                    continue

                if route.method != epoint_method:
                    continue

                r = route.resource
                ri = r.get_info()
                if 'formatter' not in ri:
                    continue

                epoint = epoint.replace('.', '_')
                rf = ri['formatter']
                rf = rf.replace('/api', '')

                scope = rf.split('/')[1]

                if epoint == rf:
                    found_scopes[scope] += 1
                    found.append(rf)
                    _flag = True

        not_found = set([t[2] for t in endpoints]) ^ set(found)
        log.debug('Endpoints not found: %s', pprint.pformat(not_found))

        for scope, count in scopes.most_common():
            found_count = found_scopes[scope]

            log.info('scope %s: %d total, %d found', \
                scope, count, found_count)

        total = len(endpoints)
        found_count = len(found)
        log.info('From %d listed endpoints, %d total, %d found, %.2f%% compliant', \
            total, self.endpoints, found_count, (found_count / total) * 100)
        return

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
            self.images = managers.Images(self, self.flags.get('images', {}))

            log.debug('[init] GuildManager')
            self.guild_man = managers.GuildManager(self)
            await self.guild_man.init()

            log.debug('[init] PresenceManager')
            self.presence = managers.PresenceManager(self)

            log.debug('[init] EmbedManager')
            self.embed = managers.EmbedManager(self) 

            log.debug('[init] VoiceManager')
            self.voice = VoiceManager(self)
            self.voice_task = self.loop.create_task(self.voice.init_task(self.flags))

            log.debug('[init] SettingsManager')
            self.settings = managers.SettingsManager(self)

            log.debug('[init] RelationsManager')
            self.relations = managers.RelationsManager(self)

            log.debug('[init] ApplicationManager')
            self.apps = managers.ApplicationManager(self)

            log.debug('[init] endpoints')
            self.gw_endpoint = api.GatewayEndpoint(self)
            self.users_endp = api.UsersEndpoint(self)
            self.guilds_endp = api.guilds.GuildsEndpoint(self)
            self.channels_endp = api.ChannelsEndpoint(self)
            self.invites_endp = api.InvitesEndpoint(self)
            self.images_endp = api.ImageEndpoint(self)
            self.admins_endp = api.AdminEndpoints(self)
            self.auth_endp = api.AuthEndpoints(self)
            self.voice_endp = api.VoiceEndpoint(self)
            self.webhook_endp = api.WebhookEndpoints(self)

            self.add_get('version', self.h_get_version)

            t_end = time.monotonic()
            delta = (t_end - t_init) * 1000

            log.info('[load:server] Loaded in %.2fms', delta)

            self.good.set()
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
