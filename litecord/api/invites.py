import json
import logging

from aiohttp import web
from ..utils import _err, _json

log = logging.getLogger(__name__)

class InvitesEndpoint:
    def __init__(self, server):
        self.server = server
        self.guild_man = server.guild_man

    def register(self, app):
        _r = app.router
        _r.add_get('/api/invites/{invite_code}', self.h_get_invite)
        _r.add_post('/api/invites/{invite_code}', self.h_accept_invite)
        _r.add_delete('/api/invites/{invite_code}', self.h_delete_invite)

        _r.add_post('/api/channels/{channel_id}/invites', self.h_create_invite)

    async def h_get_invite(self, request):
        """`GET /invites/{invite_code}`."""

        invite_code = request.match_info['invite_code']
        invite = self.server.guild_man.get_invite(invite_code)

        if invite is None:
            return _err(errno=10006)

        return _json(invite.as_json)

    async def h_accept_invite(self, request):
        """`POST /invites/{invite_code}`.

        Accept an invite. Returns invite object.
        """

        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        invite_code = request.match_info['invite_code']
        user = self.server._user(_error_json['token'])

        invite = self.server.guild_man.get_invite(invite_code)
        if invite is None:
            return _err(errno=10006)

        if not invite.valid:
            return _err('Invalid invite')

        guild = invite.channel.guild

        try:
            member = await self.guild_man.use_invite(invite)
            if member is None:
                return _err('Error adding to the guild')

            return _json(invite.as_json)
        except:
            log.error(exc_info=True)
            return _err('Error using the invite.')

    async def h_create_invite(self, request):
        """`POST /channels/{channel_id}/invites`.

        Creates an invite to a channel.
        Returns invite object.
        """

        _error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        channel_id = request.match_info['channel_id']
        channel = self.guild_man.get_channel(channel_id)
        if channel is None:
            return _err(errno=10003)

        user = self.server._user(_error_json['token'])

        try:
            payload = await request.json()
        except:
            return _err('error parsing JSON')

        invite_payload = {
            'max_age': payload.get('max_age', 86400),
            'max_uses': payload.get('max_uses', 0),
            'temporary': payload.get('temporary', False),
            'unique': payload.get('unique', False)
        }

        invite = await self.guild_man.create_invite(channel, invite_payload)
        if invite is None:
            return _err('error making invite')

        return _json(invite.as_json)

    async def h_delete_invite(self, request):
        """`DELETE /invites/{invite_code}`.

        Delete an invite.
        """

        error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        invite_code = request.match_info['invite_code']
        user = self.server._user(_error_json['token'])

        guild = invite.channel.guild

        if guild.owner.id != user.id:
            return _err(errno=40001)

        invite = self.server.guild_man.get_invite(invite_code)
        if invite is None:
            return _err(errno=10006)

        try:
            await self.guild_man.delete_invite(invite)
            return _json(invite.as_json)
        except:
            log.error(exc_info=True)
            return _err('Error deleting invite.')
