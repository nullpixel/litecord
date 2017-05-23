import json
import logging

from aiohttp import web
from ..utils import _err, _json

log = logging.getLogger(__name__)

class GuildsEndpoint:
    """Manager for guild-related endpoints."""
    def __init__(self, server):
        self.server = server
        self.guild_man = server.guild_man

    def register(self, app):
        self.server.add_get('guilds/{guild_id}', self.h_guilds)
        self.server.add_get('guilds/{guild_id}/channels', self.h_get_guild_channels)
        self.server.add_get('guilds/{guild_id}/members/{user_id}', self.h_guild_one_member)
        self.server.add_get('guilds/{guild_id}/members', self.h_guild_members)
        self.server.add_post('guilds', self.h_post_guilds)

        self.server.add_delete('users/@me/guilds/{guild_id}', self.h_leave_guild)
        self.server.add_delete('guilds/{guild_id}/members/{user_id}', self.h_kick_member)
        self.server.add_patch('guilds/{guild_id}/members/@me/nick', self.h_change_nick)

    async def h_guilds(self, request):
        """`GET /guilds/{guild_id}`

        Returns a guild object
        """
        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        guild_id = request.match_info['guild_id']

        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err(errno=10004)

        return _json(guild.as_json)

    async def h_get_guild_channels(self, request):
        """`GET /guilds/{guild_id}/channels`

        Returns a list of channels the guild has.
        """
        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        guild_id = request.match_info['guild_id']

        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err(errno=10004)

        return _json([channel.as_json for channel in guild.channels])

    async def h_guild_one_member(self, request):
        """`GET /guilds/{guild_id}/members/{user_id}`

        Get a specific member in a guild.
        """

        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        guild_id = request.match_info['guild_id']
        user_id = request.match_info['user_id']
        user = self.server._user(_error_json['token'])

        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err(errno=10004)

        if user.id not in guild.members:
            return _err('401: Unauthorized')

        if user_id not in guild.members:
            return _err(errno=10004)

        return _json(guild.members[user_id].as_json)

    async def h_guild_members(self, request):
        """`GET /guilds/{guild_id}/members`

        Returns a list of all the members in a guild.
        """

        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        guild_id = request.match_info['guild_id']
        user = self.server._user(_error_json['token'])

        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err(errno=10004)

        if user.id not in guild.members:
            return _err('401: Unauthorized')

        return _json([member.as_json for member in guild.members])

    async def h_post_guilds(self, request):
        """`POST /guilds`.

        Create a guild.
        """

        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        user = self.server._user(_error_json['token'])

        try:
            _payload = await request.json()
        except:
            return _err('error parsing')

        # we ignore anything else client sends.
        try:
            payload = {
                'name': _payload['name'],
                'region': _payload['region'],
                'icon': _payload['icon'],
                'verification_level': _payload.get('verification_level', -1),
                'default_message_notifications': _payload.get('default_message_notifications', -1),
                'roles': [],
                'channels': [],
                'members': [str(user.id)],
            }
        except KeyError:
            return _err('incomplete payload')

        try:
            new_guild = await self.guild_man.new_guild(user, payload)
        except:
            log.error(exc_info=True)
            return _err('error creating guild')

        return _json(new_guild.as_json)

    async def h_leave_guild(self, request):
        """`DELETE /users/@me/guilds/{guild_id}`.

        Leave a guild.
        Fires GUILD_DELETE event.
        """

        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        guild_id = request.match_info['guild_id']
        user = self.server._user(_error_json['token'])

        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err(errno=10004)

        if user.id not in guild.members:
            return _err(errno=10004)

        await self.guild_man.remove_member(guild, user)
        return web.Response(status=204)

    async def h_kick_member(self, request):
        """`DELETE /gulids/{guild_id}/members/{user_id}`.

        Kick a member.
        """

        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        guild_id = request.match_info['guild_id']
        member_id = request.match_info['user_id']

        user = self.server._user(_error_json['token'])

        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err(errno=10004)

        if user.id not in guild.members:
            return _err(errno=10004)

        member = guild.members.get(member_id)
        if member is None:
            return _err(errno=10007)

        try:
            res = await self.guild_man.kick_member(member)
            if not res:
                return _err("Kicking failed.")
            return web.Response(status=204)
        except Exception as err:
            log.error("Error kicking member", exc_info=True)
            return _err('Error kicking member: {err!r}')

    async def h_change_nick(self, request):
        """`PATCH /guilds/{guild_id}/members/@me/nick`.

        Modify your nickname.
        Returns a 200.
        Dispatches GUILD_MEMBER_UPDATE to relevant clients.
        """

        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        guild_id = request.match_info['guild_id']
        user = self.server._user(_error_json['token'])

        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err(errno=10004)

        if user.id not in guild.members:
            return _err(errno=10004)

        member = guild.members.get(user.id)

        try:
            payload = await request.json()
        except:
            return _err('error parsing payload')

        nickname = str(payload.get('nick', ''))

        if len(nickname) > 32:
            return _err('Nickname is over 32 chars.')

        await self.guild_man.edit_member(member, {
            'nick': nickname,
        })

        return web.response(status=200, text=nickname)
