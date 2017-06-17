import json
import logging

from aiohttp import web

from ..utils import _err, _json
from ..snowflake import get_snowflake
from ..ratelimits import ratelimit
from ..decorators import auth_route

log = logging.getLogger(__name__)

class ChannelsEndpoint:
    """Handle channel/message related endpoints."""
    def __init__(self, server, app):
        self.server = server
        self.register(app)

    def register(self, app):

        self.server.add_get('channels/{channel_id}', self.h_get_channel)

        self.server.add_get('channels/{channel_id}/messages', self.h_get_messages)
        self.server.add_get('channels/{channel_id}/messages/{message_id}', self.h_get_single_message)

        self.server.add_post('channels/{channel_id}/messages', self.h_post_message)
        self.server.add_patch('channels/{channel_id}/messages/{message_id}',
                       self.h_patch_message)

        self.server.add_delete('channels/{channel_id}/messages/{message_id}',
                        self.h_delete_message)

        self.server.add_post('channels/{channel_id}/typing', self.h_post_typing)

        #self.server.add_put('channels/{channel_id}', self.h_edit_channel)
        #self.server.add_patch('channels/{channel_id}', self.h_edit_channel)

        #self.server.add_delete('channels/{channel_id}', self.h_delete_channel)

    @auth_route
    async def h_get_channel(self, request, user):
        """`GET /channels/{channel_id}`.

        Returns a channel object
        """

        channel_id = request.match_info['channel_id']

        channel = self.server.guild_man.get_channel(channel_id)
        if channel is None:
            return _err(errno=10003)

        guild = channel.guild

        if user.id not in guild.members:
            return _err('401: Unauthorized')

        return _json(channel.as_json)

    @auth_route
    async def h_post_typing(self, request, user):
        """`POST /channels/{channel_id}/typing`.

        Dispatches TYPING_START events to relevant clients.
        Returns a HTTP empty response with status code 204.
        """

        channel_id = request.match_info['channel_id']

        channel = self.server.guild_man.get_channel(channel_id)
        if channel is None:
            return _err(errno=10003)

        if user.id not in channel.guild.members:
            return _err(errno=40001)

        await self.server.presence.typing_start(user.id, channel_id)
        return web.Response(status=204)

    @auth_route
    async def h_post_message(self, request, user):
        """`POST /channels/{channel_id}/messages/`.

        Send a message.
        Dispatches MESSAGE_CREATE events to relevant clients.
        """

        channel_id = request.match_info['channel_id']
        channel = self.server.guild_man.get_channel(channel_id)

        if channel is None:
            return _err(errno=10003)

        if user.id not in channel.guild.members:
            return _err(errno=40001)

        try:
            payload = await request.json()
        except:
            return _err("error parsing")

        try:
            content = str(payload['content'])
            if len(content) < 1:
                return _err(errno=50006)

            if len(content) > 2000:
                return web.response(status=400)
        except:
            return _err('no useful content provided')

        _data = {
            'id': get_snowflake(),
            'author_id': user.id,
            'content': content,
        }

        new_message = await self.server.guild_man.new_message(channel, user, _data)
        return _json(new_message.as_json)

    @auth_route
    async def h_get_single_message(self, request, user):
        """`GET /channels/{channel_id}/messages/{message_id}`.

        Get a single message by its snowflake ID.
        """

        channel_id = request.match_info['channel_id']
        message_id = request.match_info['message_id']

        channel = self.server.guild_man.get_channel(channel_id)

        if channel is None:
            return _err(errno=10003)

        if user.id not in channel.guild.members:
            return _err(errno=40001)

        message = channel.get_message(message_id)
        if message is None:
            return _err(errno=10008)

        return _json(message.as_json)

    @auth_route
    async def h_get_messages(self, request, user):
        """`GET /channels/{channel_id}/messages`.

        Returns a list of messages.
        """

        channel_id = request.match_info['channel_id'] 
        channel = self.server.guild_man.get_channel(channel_id)

        if channel is None:
            return _err(errno=10003)

        if user.id not in channel.guild.members:
            return _err(errno=40001)

        limit = request.query.get('limit', 50)

        try:
            limit = int(limit)
        except:
            return _err('limit is not a integer')

        if not ((limit >= 1) and (limit <= 100)):
            return _err(f'limit not in 1-100 range, {limit}')

        around = request.query.get('around', -1)
        before = request.query.get('before', -1)
        after = request.query.get('after', -1)

        try:
            around = int(around)
            before = int(before)
            after = int(after)
        except:
            return _err('parameters are not integers')

        message_list = await channel.last_messages(limit)

        if around != -1:
            avg = int(limit / 2)
            before = around + avg
            after = around - avg

            message_list = [m for m in message_list if (m.id < before) and (m.id > after)]

        elif before != -1:
            message_list = [m for m in message_list if (m.id < before)]

        elif after != -1:
            message_list = [m for m in message_list if (m.id > after)]

        return _json([m.as_json for m in message_list])

    @auth_route
    async def h_delete_message(self, request, user):
        """`DELETE /channels/{channel_id}/messages/{message_id}`.

        Delete a message sent by the user.
        """

        channel_id = request.match_info['channel_id']
        message_id = request.match_info['message_id']

        channel = self.server.guild_man.get_channel(channel_id)

        if channel is None:
            return _err(errno=10003)

        if user.id not in channel.guild.members:
            return _err(errno=40001)

        message = channel.get_message(message_id)
        if message is None:
            return _err(errno=10008)

        if user.id != message.author.id:
            return _err(errno=40001)

        await self.server.guild_man.delete_message(message)
        return web.Response(status=204)

    @auth_route
    async def h_patch_message(self, request, user):
        """`PATCH /channels/{channel_id}/messages/{message_id}`.

        Update a message sent by the current user.
        """

        channel_id = request.match_info['channel_id']
        message_id = request.match_info['message_id']

        channel = self.server.guild_man.get_channel(channel_id)

        if channel is None:
            return _err(errno=10003)

        if user.id not in channel.guild.members:
            return _err(errno=40001)

        message = channel.get_message(message_id)
        if message is None:
            return _err(errno=10008)

        if user.id != message.author.id:
            return _err(errno=50005)

        try:
            payload = await request.json()
        except:
            return _err("error parsing")

        _data = {
            'content': str(payload.get('content', None)),
        }

        if _data['content'] is None:
            return _err('Erroneous payload')

        await self.server.guild_man.edit_message(message, _data)
        return _json(message.as_json)
