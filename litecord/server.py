import asyncio
import json
import logging
import os
import base64
import hashlib
import time

import motor.motor_asyncio
from aiohttp import web

from .snowflake import get_raw_token, get_snowflake
from .utils import strip_user_data, random_digits, _json, _err, get_random_salt, pwd_hash
from .guild import GuildManager
from .presence import PresenceManager
from .api import users, guilds, channels
from .objects import User, Guild
from .images import Images

log = logging.getLogger(__name__)


BOILERPLATES = {
    'user': 'boilerplate_data/users.json',
    'guild': 'boilerplate_data/guilds.json',
}


class LitecordServer:
    """Main class for the Litecord server.

    Attributes:
        flags: A dictionary, server configuration goes there.
        loop: asyncio event loop.
        mongo_client: An instance of `AsyncIOMotorClient`.
        event_cache: A dictionary that relates user IDs to the last events they received.
            Used for resuming.
        cache: An internal dictionary that relates IDs to objects/raw objects.
        valid_tokens: List of valid tokens(strings),
            A valid token is a token that was used in a connection and it is still,
            being used in that connection
        session_dict: A dictionary relating tokens to their respective `Connection`.
        sessions: A dictionary relating session IDs to their respective `Connection` object.
        guild_man: An instance of `GuildManager`.
        presence: An instance of `PresenceManager`.

        TODO: rest_ratelimits.
        TODO: ws_ratelimits.
    """
    def __init__(self, flags=None):
        if flags is None:
            flags = {}

        self.flags = flags

        self.rest_ratelimits = {}
        self.ws_ratelimits = {}

        # if anybody needs
        self.loop = asyncio.get_event_loop()

        # mongodb stuff
        self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient()
        self.litecord_db = self.mongo_client['litecord']

        self.message_db =   self.litecord_db['messages']
        self.user_db =      self.litecord_db['users']
        self.guild_db =     self.litecord_db['gulids']
        self.token_db =     self.litecord_db['tokens']

        # cache for events
        self.event_cache = {}

        # cache for objects
        self.cache = {}

        self.valid_tokens = []
        self.session_dict = {}
        self.sessions = {}

        self.presence = None
        self.guild_man = None

    async def boilerplate_init(self):
        """Load boilerplate data."""

        for key in BOILERPLATES:
            path = BOILERPLATES[key]
            data = None
            with open(path, 'r') as f:
                data = json.loads(f.read())

            db_to_update = getattr(self, f'{key}_db')

            tot = 0
            for element in data:
                res = await db_to_update.replace_one({'id': element['id']}, element, True)
                tot += 1
            log.info(f"[boilerplate] Replaced {tot} elements in {key!r}")

    async def load_users(self):
        """Load users database using MongoDB.

        Creates the `id->raw_user` and `id->user` dictionaries in `LitecordServer.cache`.
        """

        # create cache objects
        self.cache['id->raw_user'] = {}
        self.cache['id->user'] = {}

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
            cached_raw_user = raw_user_cache[raw_user['id']]
            cached_user = user_cache[raw_user['id']]

            differences = set(raw_user.values()) ^ set(cached_raw_user.values())
            if len(differences) > 0:
                user = User(self, raw_user)

                # dispatch USER_UPDATE to all online clients
                for guild in user.guilds:
                    for member in guild.online_members:
                        conn = member.connection
                        await conn.dispatch('USER_UPDATE', user.as_json)
                        events += 1

                cached_raw_user = raw_user
                cached_user = user

        log.info(f'[userdb_update] Updated {updated_users} users, dispatched {events} events')

    # helpers
    def get_raw_user(self, user_id):
        """Get a raw user object using the user's ID."""
        user_id = int(user_id)
        users = self.cache['id->raw_user']
        return users.get(user_id)

    def get_user(self, user_id):
        """Get a `User` object using the user's ID."""
        user_id = int(user_id)
        users = self.cache['id->user']
        return users.get(user_id)

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
        session_id = self.session_dict[token]
        user_id = self.sessions[session_id].user.id
        user = self.get_user(user_id)
        return user

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

    async def login(self, request):
        """Login a user through the `POST:/auth/login` endpoint.

        Input: a JSON object:
            {
                "email": "the email of the user",
                "password": "the plaintext password of the user",
            }

        Output: Another JSON object:
            {
                "token": "user token"
            }
            With the token you can connect to the gateway and send an IDENTIFY payload

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
        auth_header = request.headers['Authorization']
        if len(auth_header) < 1:
            return _err('401: Unauthorized, Malformed request')

        try:
            token_type, token_value = auth_header.split()
        except:
            if auth_header.startswith('memework_'):
                token_type = 'Bot'
                token_value = auth_header
            else:
                log.info(f"Received weird auth header: {auth_header!r}")
                return _err('error parsing Authorization header')

        if token_type != 'Bot':
            return _err('401: Unauthorized, Invalid token type')

        # check if token is valid
        try:
            self.valid_tokens.index(token_value)
        except:
            return _err(f'401: Unauthorized, Invalid token {token_value!r}')

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

    async def init(self, app):
        """Initialize the server.

        Loads databases, managers and endpoints.
        """
        try:
            t_init = time.monotonic()

            log.info("[load] boilerplate data")
            await self.boilerplate_init()

            log.info('[load] user database')
            await self.load_users()

            log.info('[load] Images')
            self.images = Images(self, self.flags.get('images', {}))

            log.info('[init] GuildManager')
            self.guild_man = GuildManager(self)
            await self.guild_man.init()

            log.info('[init] PresenceManager')
            self.presence = PresenceManager(self)

            log.info('[init] endpoint objects')
            self.users_endpoint = users.UsersEndpoint(self)
            self.users_endpoint.register(app)

            self.guilds_endpoint = guilds.GuildsEndpoint(self)
            self.guilds_endpoint.register(app)

            self.channels_endpoint = channels.ChannelsEndpoint(self)
            self.channels_endpoint.register(app)

            t_end = time.monotonic()
            delta = round((t_end - t_init) * 1000, 2)

            log.info(f"[server] Loaded in {delta}ms")
            return True
        except:
            log.error('Error when initializing LitecordServer', exc_info=True)
            return False
