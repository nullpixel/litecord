'''
users.py - All handlers under /users/*
'''

import json
import logging
from ..utils import _err, _json, strip_user_data

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

        # get data about the current user
        token = _error_json['token']
        session_id = self.server.session_dict[token]
        user = self.server.sessions[session_id].user
        user = strip_user_data(user)

        if user_id == '@me':
            return _json(user)
        else:
            # If we want to be full discord-like, uncomment this
            #if not user['bot']:
            #    return _err("403: Forbidden")

            log.info(f'searching for user {user_id!r}')
            users = self.server.db['users']
            userdata = None

            # way easier using id->raw_user instead of searching through userdb
            userdata = self.server.get_raw_user(user_id)

            if userdata is None:
                return _err("user not found")
            return _json(strip_user_data(userdata))

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

        users = self.db['users']
        if email in users:
            return _err("email already used")

        discrim = await self.server.get_discrim(username)
        _salt = get_random_salt()

        new_user = {
            "id": get_snowflake(),
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

        users[email] = new_user

        self.server.db_save(['users'])

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

        # get data about the current user
        token = _error_json['token']
        session_id = self.server.session_dict[token]
        user = self.server.sessions[session_id].user
        user = strip_user_data(user)

        users = self.server.db['users']
        for user_email in users:
            user_obj = users[user_email]
            if user_obj['id'] == user['id']:
                new_username = payload['username']
                new_discrim = await self.server.get_discrim(new_username)
                user_obj['username'] = payload['username']
                user_obj['discriminator'] = new_discrim
                user_obj['avatar'] = payload['avatar']
                return _json(strip_user_data(user_obj))

        return _json({
            'code': 500,
            'message': 'Internal Server Error'
        })

    async def h_get_me_settings(self, request):
        """`GET /users/@me/settings`.

        Dummy handler.
        """
        return _json({})
