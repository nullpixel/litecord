'''
users.py - All handlers under /users/*
'''

import logging

from aiohttp import web

from ..utils import _err, _json
from ..snowflake import get_snowflake
from ..decorators import auth_route

log = logging.getLogger(__name__)

class UsersEndpoint:
    def __init__(self, server):
        self.server = server
        self.guild_man = server.guild_man

        self.register()

    def register(self):
        self.server.add_get('users/{user_id}', self.h_users)

        self.server.add_patch('users/@me', self.h_patch_me)

        self.server.add_get('users/@me/settings', self.h_get_me_settings)

        self.server.add_get('users/@me/guilds', self.h_users_me_guild)
        self.server.add_delete('api/users/@me/guilds/{guild_id}', self.h_leave_guild)

    @auth_route
    async def h_users(self, request, user):
        """Handle `GET /users/{user_id}`.

        Get a specific user.
        """

        user_id = request.match_info['user_id']
        log.debug(f"user={user}")

        if user_id == '@me':
            return _json(user.as_json)
        else:
            # If we want to be full discord-like, uncomment this
            #if not user.bot:
            #    return _err(errno=40001)

            log.debug(f'searching for user {user_id!r}')

            user_to_find = self.server.get_user(user_id)
            if user_to_find is None:
                return _err(errno=10013)

            return _json(user_to_find.as_json)

    @auth_route
    async def h_patch_me(self, request, user):
        """`PATCH /users/@me`.

        Changes a user.
        Returns the new user object.
        """

        try:
            payload = await request.json()
        except:
            return _err("error parsing")

        new_raw_user = {}

        new_username = payload.get('username', user.username)
        if new_username != user.username:
            new_raw_user['discriminator'] = await self.server.get_discrim(new_username)

        new_raw_user['username'] = new_username

        new_avatar_hash = await self.server.images.avatar_register(payload.get('avatar'))
        new_raw_user['avatar'] = new_avatar_hash or user._data['avatar']

        await self.server.user_db.update_one({'id': str(user.id)}, {'$set': new_raw_user})
        await self.server.userdb_update()

        return _json(user.as_json)

    @auth_route
    async def h_get_me_settings(self, request, user):
        """`GET /users/@me/settings`.

        Dummy handler.
        """
        return _json({})

    @auth_route
    async def h_users_me_guild(self, request, user):
        """`GET /users/@me/guilds`.

        Returns a list of user guild objects.

        TODO: before, after, limit parameters
        """

        user_guilds = [m.user_guild for m in user.members]
        return _json(user_guilds)

    @auth_route
    async def h_leave_guild(self, request, user):
        """`DELETE /users/@me/guilds/{guild_id}`.

        Leave guild.
        Returns empty 204 response.
        """

        guild_id = request.match_info['guild_id']

        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err(errno=10004)

        await self.guild_man.remove_member(guild, user)
        return web.Response(status=204)
