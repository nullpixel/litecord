'''
guilds.py - All handlers under /guilds/*
'''

import json
import logging
from ..utils import _err, _json, strip_user_data

log = logging.getLogger(__name__)

class GuildsEndpoint:
    def __init__(self, server):
        self.server = server

    async def h_post_guilds(self, request):
        pass

    async def h_guilds(self, request):
        '''
        GuildsEndpoint.h_guilds

        Handle `GET /guilds/{guild_id}`
        '''
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
        '''
        GuildsEndpoint.h_get_guild_channels

        `GET /guilds/{guild_id}/channels`
        '''
        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        guild_id = request.match_info['guild_id']

        return _json('Not Implemented')
