'''
users.py - All handlers under /users/*
'''

import json
import logging
from ..utils import _err, _json, strip_user_data, get_random_salt, pwd_hash
from ..snowflake import get_snowflake

log = logging.getLogger(__name__)

class UsersEndpoint:
    def __init__(self, server):
        self.server = server

    def register(self, app):
        _r = app.router
        _r.add_get('/api/users/{user_id}', self.h_users)

        _r.add_post('/api/users/add', self.h_add_user)
        _r.add_patch('/api/users/@me', self.h_patch_me)

        _r.add_get('/api/users/@me/settings', self.h_get_me_settings)

        #_r.add_get('/api/users/@me/guilds', server.h_users_me_guild)
        #_r.add_delete('/api/users/@me/guilds/{guild_id}', server.h_users_guild_delete)

    async def h_users(self, request):
        """Handle `GET /users/{user_id}`.

        Get a specific user.
        """
        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        user_id = request.match_info['user_id']
        user = self.server._user(_error_json['token'])

        if user_id == '@me':
            return _json(user.as_json)
        else:
            # If we want to be full discord-like, uncomment this
            #if not user['bot']:
            #    return _err(errno=40001)

            log.info(f'searching for user {user_id!r}')

            # way easier using id->raw_user instead of searching through userdb
            raw_userdata = self.server.get_raw_user(user_id)
            if userdata is None:
                return _err(errno=10013)

            return _json(strip_user_data(raw_userdata))

    async def h_add_user(self, request):
        """`POST /users/add`.

        Creates a user.
        Input: A JSON object:
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

        email =     payload.get('email')
        password =  payload.get('password')
        username =  payload.get('username')
        if email is None or password is None or username is None:
            return _err("malformed payload")

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

    async def h_patch_me(self, request):
        """`PATCH /users/@me`.

        Changes a user.
        Returns the new user object.
        """
        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        try:
            payload = await request.json()
        except:
            return _err("error parsing")

        user = self.server._user(_error_json['token'])
        new_raw_user = {}

        new_username = payload.get('username', user.username)
        if new_username != user.username:
            new_raw_user['discriminator'] = await self.server.get_discrim(new_username)

        new_raw_user['username'] = new_username
        new_raw_user['avatar'] = payload.get('avatar', user._data['avatar'])

        self.user_db.find_one_and_update({'id': str(user.id)}, new_raw_user)

        # TODO: This guy will dispatch USER_UPDATE events
        # Also it will update LitecordServer.cache objects.
        #await self.server.userdb_update()

        return _json(user.as_json)

    async def h_get_me_settings(self, request):
        """`GET /users/@me/settings`.

        Dummy handler.
        """
        return _json({})
