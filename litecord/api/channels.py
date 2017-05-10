import json
import logging
from aiohttp import web
from ..utils import _err, _json, strip_user_data
from ..snowflake import get_snowflake
from ..objects import Message

log = logging.getLogger(__name__)

class ChannelsEndpoint:
    """Handle channel/message related endpoints"""
    def __init__(self, server):
        self.server = server

    def register(self, app):
        _r = app.router
        _r.add_get('/api/channels/{channel_id}', self.h_get_channel)

        _r.add_get('/api/channels/{channel_id}/messages', self.h_get_messages)
        _r.add_get('/api/channels/{channel_id}/messages/{message_id}', self.h_get_single_message)

        _r.add_post('/api/channels/{channel_id}/messages', self.h_post_message)
        #_r.add_patch('/api/channels/{channel_id}/messages/{message_id}',
        #               self.h_patch_message)

        _r.add_delete('/api/channels/{channel_id}/messages/{message_id}',
                        self.h_delete_message)

        _r.add_post('/api/channels/{channel_id}/typing', self.h_post_typing)

    async def h_get_channel(self, request):
        """`GET /channels/{channel_id}`.

        Returns a channel object
        """

        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        channel_id = request.match_info['channel_id']
        user = self.server._user(_error_json['token'])

        channel = self.server.guild_man.get_channel(channel_id)
        if channel is None:
            return _err(errno=10003)

        guild = channel.guild

        if user.id not in guild.members:
            return _err('401: Unauthorized')

        return _json(channel.as_json)

    async def h_post_typing(self, request):
        """`POST /channels/{channel_id}/typing`.

        Dispatches TYPING_START events to relevant clients.
        Returns a HTTP empty response with status code 204.
        """

        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        channel_id = request.match_info['channel_id']
        user = self.server._user(_error_json['token'])

        channel = self.server.guild_man.get_channel(channel_id)
        if channel is None:
            return _err('404: Not found')

        if user.id not in channel.guild.members:
            return _err('401: Unauthorized')

        await self.server.presence.typing_start(user.id, channel_id)
        return web.Response(status=204)

    async def h_post_message(self, request):
        """`POST /channels/{channel_id}/messages/`.

        Send a message.
        Dispatches MESSAGE_CREATE events to relevant clients.
        """

        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        channel_id = request.match_info['channel_id']
        user = self.server._user(_error_json['token'])

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
            content = payload['content']
            if len(content) > 2000:
                return web.response(status=400)
        except:
            return _err('no useful content provided')

        tts = payload.get('tts', False)

        _data = {
            'id': get_snowflake(),
            'author_id': user.id,
            'content': content,
        }

        new_message = await self.server.guild_man.new_message(channel, user, _data)
        return _json(new_message.as_json)

    async def h_get_single_message(self, request):
        """`GET /channels/{channel_id}/messages/{message_id}`.

        Get a single message by its snowflake ID.
        """

        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        channel_id = request.match_info['channel_id']
        message_id = request.match_info['message_id']

        user = self.server._user(_error_json['token'])
        channel = self.server.guild_man.get_channel(channel_id)

        if channel is None:
            return _err(errno=10003)

        if user.id not in channel.guild.members:
            return _err(errno=40001)

        message = channel.get_message(message_id)
        if message is None:
            return _err(errno=10008)

        return _json(message.as_json)

    async def h_get_messages(self, request):
        """`GET /channels/{channel_id}/messages`.

        Returns a list of messages.
        """

        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        channel_id = request.match_info['channel_id']

        user = self.server._user(_error_json['token'])
        channel = self.server.guild_man.get_channel(channel_id)

        if channel is None:
            return _err(errno=10003)

        if user.id not in channel.guild.members:
            return _err(errno=40001)

        # get data from payload
        # this is ugly.
        data = request.query_string.split('=')
        limit = 50
        if len(data) == 2:
            key, val = data
            if key == 'limit':
                try:
                    limit = int(val)
                except:
                    limit = 50

        if limit > 300:
            meme

        # TODO: understand these
        #around = request.query.get('around', 50)
        #before = request.query.get('before', 50)
        #after = request.query.get('after', 50)

        message_list = await channel.last_messages(limit)
        return _json([m.as_json for m in message_list])

    async def h_delete_message(self, request):
        """`DELETE /channels/{channel_id}/messages/{message_id}`.

        Delete a message sent by the user.
        """

        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        channel_id = request.match_info['channel_id']
        message_id = request.match_info['message_id']

        user = self.server._user(_error_json['token'])
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
