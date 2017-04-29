import json
import logging
import os
import base64
import hashlib

from aiohttp import web
from .snowflake import get_raw_token, get_snowflake
from .utils import strip_user_data, random_digits, _json, _err
from .guild import GuildManager

from .api import users

from .objects import User

log = logging.getLogger(__name__)

def get_random_salt(size=32):
    return base64.b64encode(os.urandom(size)).decode()

def pwd_hash(plain, salt):
    return hashlib.sha256(f'{plain}{salt}'.encode()).hexdigest()

class LitecordServer:
    def __init__(self, valid_tokens, session_dict, sessions):
        self.db_paths = None
        self.db = {}

        self.cache = {}

        self.valid_tokens = valid_tokens
        self.session_dict = session_dict
        self.sessions = sessions
        self.guild_man = None

    def db_init_all(self):
        for database_id in self.db_paths:
            db_path = self.db_paths[database_id]
            try:
                self.db[database_id] = json.load(open(db_path, 'r'))
                if hasattr(self, f'dbload_{database_id}'):
                    getattr(self, f'dbload_{database_id}')()
            except:
                log.error(f"Error loading database {database_id} at {db_path}", exc_info=True)
                return False

        return True

    def db_save(self, list_db):
        for database_id in list_db:
            path = self.db_paths[database_id]
            db_object = self.db[database_id]
            json.dump(db_object, open(path, 'w'))

    def dbload_users(self):
        users = self.db['users']

        # init cache objects
        self.cache['id->raw_user'] = {}
        self.cache['id->user'] = {}

        # reference them
        id_to_raw_user = self.cache['id->raw_user']
        id_to_user = self.cache['id->user']

        for user_email in users:
            user = users[user_email]
            pwd = user['password']

            if len(pwd['salt']) < 1:
                pwd['salt'] = get_random_salt()

            if len(pwd['hash']) < 1 and len(pwd['salt']) > 0:
                pwd['hash'] = pwd_hash(pwd['plain'], pwd['salt'])
                pwd['plain'] = None

            # a helper
            user['email'] = user_email

            # cache objects
            id_to_raw_user[user['id']] = user
            id_to_user[user['id']] = User(self, user)

        self.db_save(['users'])

    # helpers
    def get_raw_user(self, user_id):
        users = self.cache['id->raw_user']
        return users.get(user_id)

    def get_user(self, user_id):
        users = self.cache['id->user']
        return users.get(user_id)

    async def login(self, request):
        try:
            json = await request.json()
        except Exception as err:
            # error parsing json
            return _err("error parsing")

        email = json.get('email')
        password = json.get('password')
        if email is None or password is None:
            return _err("malformed packet")

        users = self.db['users']
        if email not in users:
            return _err("fail on login")

        user = users[email]
        pwd = user['password']
        if pwd_hash(password, pwd['salt']) != pwd['hash']:
            return _err("fail on login")

        tokens = self.db['tokens']
        account_id = user['id']

        # check if there is already a token related to the user
        _old_token = None
        for token in tokens:
            if tokens[token] == account_id:
                _old_token = token

        # make a new one
        _token = await get_raw_token()
        while _token in tokens:
            _token = await get_raw_token()

        # overwrite the previous one if any
        if _old_token is not None:
            tokens.pop(_old_token)

        tokens[_token] = account_id
        self.db_save(['tokens'])

        return _json({"token": _token})

    async def check_request(self, request):
        auth_header = request.headers['Authorization']
        print(auth_header)
        if len(auth_header) < 1:
            return _err('401: Unauthorized, Malformed request')

        token_type, token_value = auth_header.split()
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
        users = self.db['users']

        used_discrims = [users[user_email]['discriminator'] for user_email in \
            users if users[user_email]['username'] == username]

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
                return discrim


    async def h_guild_post_message(self, request):
        '''
        LitecordServer.h_guild_post_message

        Handle POSTS to `/guild/{guild_id}/messages` and dispatches MESSAGE_CREATE events
        to the respective clients
        '''

        guild_id = request.match_info['guild_id']

        # find the guild
        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err('guild not found')

        # store message somewhere... idfk where or how

        # dispatching events should be something along those lines

        # users = list of all users in the guild
        # for user in users:
        #  get gateway.Connection that represents the user
        #  check if the Client is actually there
        #  await connection.dispatch('MESSAGE_CREATE', {data goes here})

        return _err('not implemented')

    def init(self):
        if not self.db_init_all():
            return False

        self.users_endpoint = users.UsersEndpoint(self)

        self.guild_man = GuildManager(self)
        if not self.guild_man.init():
            return False

        return True
