import logging

from voluptuous import Schema, REMOVE_EXTRA, Optional
from aiohttp import web

from ..snowflake import get_snowflake
from ..utils import _err, _json, pwd_hash, get_random_salt
from ..decorators import auth_route
from ..enums import AppType

log = logging.getLogger(__name__)

class AuthEndpoints:
    """Handle authentication endpoints."""
    def __init__(self, server):
        self.server = server
        self.user_coll = server.user_coll
        self.app_coll = server.app_coll
        self.apps = server.apps

        self.login_schema = Schema({
            'email': str,
            'password': str,
        }, extra=REMOVE_EXTRA)

        self.useradd_schema = Schema({
            'email': str,
            'password': str,
            'username': str,
        }, extra=REMOVE_EXTRA)

        _o = Optional
        self.app_add_schema = Schema({
            'name': str,
            _o('description'): str,
            _o('bot_public'): bool,
            _o('icon'): str,
        }, extra=REMOVE_EXTRA)

        self.register()

    def register(self):
        self.server.add_post('auth/login', self.h_login)
        self.server.add_post('auth/users/add', self.h_add_user)

        # create a bot, list all bots
        self.server.add_post('oauth2/applications', self.h_create_bot)
        self.server.add_get('oauth2/applications', self.h_list_bots)

        # get bot info
        self.server.add_get('oauth2/applications/{app_id}', self.h_bot_info)

        # invite a bot to a guild
        self.server.add_post('oauth2/authorize', self.h_authorize_bot)

        # patch bot
        self.server.add_patch('oauth2/applications/{app_id}', self.h_patch_bot_info)
        self.server.add_put('oauth2/applications/{app_id}', self.h_patch_bot_info)

    def app_to_bot(self, app):
        raw_bot_user = self.server.get_raw_user(app.id)
        #raw_bot_user.pop('pwd')
        return {**app.as_json, **raw_bot_user}

    async def h_login(self, request):
        """`POST:/auth/login`.

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
        """`POST:/users/add`.

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

        email = payload['email']
        password = payload['password']
        username = payload['username']

        res = await self.user_coll.find_one({'email': email})

        if res is not None:
            return _err("email already used")

        discrim = await self.server.get_discrim(username)
        salt = await get_random_salt()

        new_user = {
            'user_id': get_snowflake(),
            'email': email,
            'username': username,
            'discriminator': discrim,
            'password': {
                'plain': None,
                'hash': pwd_hash(password, salt),
                'salt': salt
            },
            'avatar': "",
            'bot': False,
            'verified': True
        }

        log.info(f"New user {new_user['username']}#{new_user['discriminator']}")
        await self.user_coll.insert_one(new_user)
        await self.server.userdb_update()

        return _json({
            "code": 1,
            "message": "success"
        })

    @auth_route
    async def h_list_bots(self, request, user):
        """`GET:/oauth2/applications`.

        Get all applications and their info info that are tied to this account
        """
        if user.bot:
            return _err('401: Unauthorized')

        bots = await self.apps.get_apps(user)
        return _json(list(map(self.app_to_bot, bots)))

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

        bot = await self.apps.get_app(app_id)
        if bot.type != AppType.BOT:
            return _err('400: Invalid application type')

        return _json(bot.as_json)

    @auth_route
    async def h_patch_bot_info(self, request, user):
        raise NotImplementedError

    @auth_route
    async def h_create_bot(self, request, user):
        """`POST:/oauth2/applications`.
        
        Create a bot.
        Returns bot user on success
        """
        if user.bot:
            return _err('401: Unauthorized')

        payload = await request.json()
        payload = self.app_add_schema(payload)

        app = await self.apps.create_bot(user, payload)
        return _json(self.app_to_bot(app))

    @auth_route
    async def h_authorize_bot(self, request, user):
        """`POST:/oauth2/authorize`.

        Authorize a bot to a guild.
        """
        if user.bot:
            return _err('401: nani')

        bot_id = request.query['client_id']
        app = await self.apps.get_app(bot_id)
        if app is None:
            return _err('404: Application not found')

        scope = request.query.get('scope', 'bot')
        if scope != 'bot':
            return _err('400: Unauthorized scope')

        wanted_permissions = request.query.get('permissions', 0)

        payload = await request.json()

        guild_id = payload['bot_guild_id']
        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err('404: Guild not found')

        permissions = payload.get('permissions', 0)

        bot_perm = None
        if permissions != 0:
            #bot_perm = Permissions(permissions)
            pass

        authorize = payload.get('authorize', False)
        if not authorize:
            return _err('401: Unauthorized')

        inviter = guild.members.get(user.id)
        if not inviter.has(Permissions.MANAGE_SERVER):
            return _err('401: Not enough permissions')

        bot_user = self.get_user(app.id)
        #bot_role = await guild.add_role(bot_user.name, bot_perm, managed=True)
        bot_member = await guild.add_member(bot_user)
        #await bot_member.add_role(bot_member, bot_role)
        return web.Response(status=200, text='authorized')
