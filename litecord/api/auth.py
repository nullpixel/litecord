import logging

from voluptuous import Schema, REMOVE_EXTRA

from ..utils import _err, _json, pwd_hash, get_random_salt
from ..decorators import auth_route
from ..enums import AppType

log = logging.getLogger(__name__)

class AuthEndpoints:
    """Handle authentication endpoints."""
    def __init__(self, server):
        self.server = server
        self.register(server.app)

        self.login_schema = Schema({
            'email': str,
            'password': str,
        }, extra=REMOVE_EXTRA)

        self.useradd_schema = Schema({
            'email': str,
            'password': str,
            'username': str,
        }, extra=REMOVE_EXTRA)

    def register(self, app):
        self.server.add_post('auth/login', self.login)
        self.server.add_post('auth/users/add', self.h_add_user)

        # botto
        self.server.add_post('auth/bot/add', self.h_create_bot)
        self.server.add_get('auth/bot/list', self.h_list_bots)
        self.server.add_get('auth/bot/info/{app_id}', self.h_bot_info)

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
            return _err("error parsing")

        payload = self.login_schema(payload)

        email = payload['email']
        password = payload['password']

        raw_user = await self.server.get_raw_user_email(email)
        if raw_user is None:
            return _err("fail on login [email]")

        pwd = raw_user['password']
        if pwd_hash(password, pwd['salt']) != pwd['hash']:
            return _err("fail on login [password]")

        user_id = raw_user['user_id']
        token = await self.server.generate_token(user_id)
        return _json({"token": token})

    async def h_add_user(self, request):
        """`POST /users/add`.

        Creates a user.
        Input: A JSON object::
            {
                "email": "the new user's email",
                "password": "the new user's password",
                "username": "the new user's username",
            }

        NOTE: This endpoint doesn't require authentication
        TODO: Add better error codes
        """

        try:
            payload = await request.json()
        except:
            return _err("error parsing")

        payload = self.useradd_schema(payload)

        email =     payload['email']
        password =  payload['password']
        username =  payload['username']

        user_db = self.server.user_db
        res = await user_db.find_one({'email': email})

        if res is not None:
            return _err("email already used")

        discrim = await self.server.get_discrim(username)
        _salt = get_random_salt()

        new_user = {
            "id": get_snowflake(),
            "email": email,
            "username": username,
            "discriminator": discrim,
            "password": {
                "plain": None,
                "hash": pwd_hash(password, _salt),
                "salt": _salt
            },
            "avatar": "",
            "bot": False,
            "verified": True
        }

        log.info(f"New user {new_user['username']}#{new_user['discriminator']}")
        await user_db.insert_one(new_user)

        return _json({
            "code": 1,
            "message": "success"
        })

    @auth_route
    async def h_list_bots(self, request, user):
        """`GET:/auth/bot/list`.

        Get all bot IDs that are tied to this account
        """
        if user.bot:
            return _err('401: Unauthorized')

        bots = await self.app_man.get_apps(user)
        return _json([bot.id for bot in bots if bot.type == AppType.BOT])

    @auth_route
    async def h_bot_info(self, request, user):
        """`GET:/auth/bot/info/{app_id}`.
        
        Get Bot Application Info.
        Returns a JSON object with bot info:
        name, avatar, token, etc.
        """
        app_id = request.match_info['app_id']
        if user.bot:
            return _err('401: Unauthorized')

        bot = await self.app_man.get_app(app_id)
        if bot.type != AppType.BOT:
            return _err('400: Invalid application type')

        return _json(bot.as_json)

    @auth_route
    async def h_patch_bot_info(self, request, user):
        raise NotImplementedError

    @auth_route
    async def h_create_bot(self, request, user):
        """`POST:/auth/bot/add`.
        
        Create a bot.
        Returns bot user on success
        """
        if user.bot:
            return _err('401: Unauthorized')

        payload = await request.json()
        payload = self.app_add_schema(payload)

        if payload['type'] != AppType.BOT:
            return _err('400: Invalid app type')

        app = await self.app_man.make_app(payload)
        return _json(app.as_json)
