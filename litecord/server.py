import json
import logging
import os
import base64
import hashlib

from aiohttp import web
from .snowflake import get_raw_token, get_snowflake
from .utils import strip_user_data, random_digits, _json, _err
from .guild import GuildManager
from .presence import PresenceManager

from .api import users, guilds, channels

from .objects import User, Guild

log = logging.getLogger(__name__)

def get_random_salt(size=32):
    return base64.b64encode(os.urandom(size)).decode()

def pwd_hash(plain, salt):
    return hashlib.sha256(f'{plain}{salt}'.encode()).hexdigest()

class LitecordServer:
    """Main class for the Litecord server.

    Attributes:
        db_paths: A dictionary with database file paths,
            See `gateway_server` for more explanation.
        db: A dictionary that relates database IDs with actual database objects.
        cache: An internal dictionary that relates IDs to objects/raw objects.
        valid_tokens: List of valid tokens(strings),
            A valid token is a token that was used in a connection and it is still,
            being used in that connection
        session_dict: A dictionary relating tokens to their respective `Connection`.
        sessions: A dictionary relating session IDs to their respective `Connection` object.
        guild_man: An instance of `GuildManager`.
    """
    def __init__(self, valid_tokens, session_dict, sessions):
        self.db_paths = None
        self.db = {}

        self.cache = {}

        self.valid_tokens = valid_tokens
        self.session_dict = session_dict
        self.sessions = sessions
        self.guild_man = None

    def db_init_all(self):
        """Initialize all declared databases in `self.db_paths`."""
        for database_id in self.db_paths:
            db_path = self.db_paths[database_id]
            try:
                self.db[database_id] = json.load(open(db_path, 'r'))

                # usually load functions put stuff in cache
                # so that other parts of the code doesn't become too complicated
                db_load_function = getattr(self, f'dbload_{database_id}', None)
                if db_load_function is not None:
                    db_load_function()
            except:
                log.error(f"Error loading database {database_id} at {db_path}", exc_info=True)
                return False

        return True

    def db_save(self, list_db):
        """Save one database into its file."""
        for database_id in list_db:
            path = self.db_paths[database_id]
            db_object = self.db[database_id]
            json.dump(db_object, open(path, 'w'))

    def dbload_users(self):
        """Load users database.

        Creates the `id->raw_user` and `id->user` dictionaries in `self.cache`.
        """
        users = self.db['users']

        # create cache objects
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
        """Get a raw user object using the user's ID."""
        user_id = int(user_id)
        users = self.cache['id->raw_user']
        return users.get(user_id)

    def get_user(self, user_id):
        """Get a `User` object using the user's ID."""
        user_id = int(user_id)
        users = self.cache['id->user']
        return users.get(user_id)

    def _user(self, token):
        """Get a user object from its token.

        This is a helper function to save lines of code in endpoint objects.
        """
        session_id = self.session_dict[token]
        user_id = self.sessions[session_id].user['id']
        user = self.get_user(user_id)
        return user

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
        """Checks a request to the API.

        This function checks if the request has the required methods
        to do any authenticated request to Litecord's API.

        More information at:
        https://discordapp.com/developers/docs/reference#authentication

        NOTE: This function doesn't check for OAuth2 Bearer tokens.
        """
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
        """Generate a discriminator from a username."""
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
        """Dummy handler for `POST:/guild/{guild_id}/messages`

        TODO: remove this
        """

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

    def init(self, app):
        """Initialize the server.

        Loads databases, managers and endpoints.
        """
        try:
            log.info('Initializing server state')
            if not self.db_init_all():
                return False

            log.info('Initializing GuildManager')
            self.guild_man = GuildManager(self)
            if not self.guild_man.init():
                return False

            log.info('Creating PresenceManager')
            self.presence = PresenceManager(self)

            log.info('Initializing endpoint objects')
            self.users_endpoint = users.UsersEndpoint(self)
            self.users_endpoint.register(app)

            self.guilds_endpoint = guilds.GuildsEndpoint(self)
            self.guilds_endpoint.register(app)

            self.channels_endpoint = channels.ChannelsEndpoint(self)
            self.channels_endpoint.register(app)

            return True
        except:
            log.error('Error when initializing LitecordServer', exc_info=True)
            return False
