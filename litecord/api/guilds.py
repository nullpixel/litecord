import json
import logging
from ..utils import _err, _json
from ..snowflake import get_snowflake

log = logging.getLogger(__name__)

class GuildsEndpoint:
    """Manager for guild-related endpoints."""
    def __init__(self, server):
        self.server = server

    def register(self, app):
        _r = app.router
        _r.add_get('/api/guilds/{guild_id}', self.h_guilds)
        _r.add_get('/api/guilds/{guild_id}/channels', self.h_get_guild_channels)
        _r.add_get('/api/guilds/{guild_id}/members/{user_id}', self.h_guild_one_member)
        _r.add_get('/api/guilds/{guild_id}/members', self.h_guild_members)
        _r.add_post('/api/guilds', self.h_post_guilds)

    async def h_guilds(self, request):
        """`GET /guilds/{guild_id}`

        Returns a guild object
        """
        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        guild_id = request.match_info['guild_id']

        guild = self.server.guild_man.get_guild(guild_id)
        if guild is None:
            return _err('404: Not Found')

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

        guild = self.server.guild_man.get_guild(guild_id)
        if guild is None:
            return _err('404: Not Found')

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

        guild = self.server.guild_man.get_guild(guild_id)
        if guild is None:
            return _err('404: Not Found')

        if user.id not in guild.members:
            return _err('401: Unauthorized')

        if user_id not in guild.members:
            return _err('404: Not Found')

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

        guild = self.server.guild_man.get_guild(guild_id)
        if guild is None:
            return _err('404: Not Found')

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
            new_guild = await self.server.guild_man.new_guild(user, payload)
        except:
            log.error(exc_info=True)
            return _err('error creating guild')

        return _json(new_guild.as_json)
