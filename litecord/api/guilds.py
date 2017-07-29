import logging

from voluptuous import Schema, All, Any, Length, Optional, REMOVE_EXTRA
from aiohttp import web
from ..utils import _err, _json
from ..decorators import auth_route
from ..enums import ChannelType

log = logging.getLogger(__name__)

class GuildsEndpoint:
    """Manager for guild-related endpoints.

    Attributes
    ----------
    guild_edit_schema: :py:meth:`voluptuous.Schema`
        Schema for guild editing payloads.
    guild_create_schema: :py:meth:`voluptuous.Schema`
        Schema for guild create payloads.

    """
    def __init__(self, server):
        self.server = server
        self.guild_man = server.guild_man

        _o = Optional
        self.guild_edit_schema = Schema({
            _o('name'): str,
            _o('region'): str,
            _o('verification_level'): int,
            _o('default_message_notifications'): int,
            _o('afk_channel_id'): str,
            _o('afk_timeout'): int,
            _o('icon'): str,
            _o('owner_id'): str,
        }, required=True, extra=REMOVE_EXTRA)

        self.guild_create_schema = Schema({
            'name': str,
            'region': str,
            'icon': Any(None, str),
            'verification_level': int,
            'default_message_notifications': int,
        }, extra=REMOVE_EXTRA)

        self.channel_create_schema = Schema({
            'name': All(str, Length(min=2, max=100)),
            _o('type'): str,
            _o('bitrate'): int,
            _o('user_limit'): int,
            _o('permission_overwrites'): list,
        }, required=True, extra=REMOVE_EXTRA)

        self.register()

    def register(self):
        self.server.add_get('guilds/{guild_id}', self.h_guilds)
        self.server.add_get('guilds/{guild_id}/channels', self.h_get_guild_channels)
        self.server.add_get('guilds/{guild_id}/members/{user_id}', self.h_guild_one_member)
        self.server.add_get('guilds/{guild_id}/members', self.h_guild_members)
        self.server.add_post('guilds', self.h_post_guilds)
        self.server.add_patch('guilds/{guild_id}/members/@me/nick', self.h_change_nick)

        self.server.add_delete('users/@me/guilds/{guild_id}', self.h_leave_guild)
        self.server.add_delete('guilds/{guild_id}/members/{user_id}', self.h_kick_member)
        self.server.add_put('guilds/{guild_id}/bans/{user_id}', self.h_ban_member)
        self.server.add_delete('guilds/{guild_id}/bans/{user_id}', self.h_unban_member)

        self.server.add_patch('guilds/{guild_id}', self.h_edit_guild)
        self.server.add_delete('guilds/{guild_id}', self.h_delete_guild)

        self.server.add_post('guilds/{guild_id}/channels', self.h_create_channel)

    @auth_route
    async def h_guilds(self, request, user):
        """`GET /guilds/{guild_id}`.

        Returns a guild object.
        """

        guild_id = request.match_info['guild_id']

        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err(errno=10004)

        return _json(guild.as_json)

    @auth_route
    async def h_get_guild_channels(self, request, user):
        """`GET /guilds/{guild_id}/channels`.

        Returns a list of channels the guild has.
        """
        guild_id = request.match_info['guild_id']

        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err(errno=10004)

        return _json([channel.as_json for channel in guild.channels])

    @auth_route
    async def h_guild_one_member(self, request, user):
        """`GET /guilds/{guild_id}/members/{user_id}`.

        Get a specific member in a guild.
        """
        guild_id = request.match_info['guild_id']
        user_id = request.match_info['user_id']

        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err(errno=10004)

        if user.id not in guild.members:
            return _err(errno=40001)

        if user_id not in guild.members:
            return _err(errno=10004)

        return _json(guild.members[user_id].as_json)

    @auth_route
    async def h_guild_members(self, request, user):
        """`GET /guilds/{guild_id}/members`.

        Returns a list of all the members in a guild.
        """

        guild_id = request.match_info['guild_id']

        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err(errno=10004)

        if user.id not in guild.members:
            return _err(errno=40001)

        return _json([member.as_json for member in guild.members])

    @auth_route
    async def h_post_guilds(self, request, user):
        """`POST /guilds`.

        Create a guild.
        """

        _payload = await request.json()

        payload = self.guild_create_schema(_payload)
        payload['region'] = 'local'

        guild = await self.guild_man.new_guild(user, payload)
        return _json(guild.as_json)

    @auth_route
    async def h_leave_guild(self, request, user):
        """`DELETE /users/@me/guilds/{guild_id}`.

        Leave a guild.
        Fires GUILD_DELETE event.
        """

        guild_id = request.match_info['guild_id']

        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err(errno=10004)

        if user.id not in guild.members:
            return _err(errno=10004)

        await self.guild_man.remove_member(guild, user)
        return web.Response(status=204)

    @auth_route
    async def h_kick_member(self, request, user):
        """`DELETE /gulids/{guild_id}/members/{user_id}`.

        Kick a member.
        """

        guild_id = request.match_info['guild_id']
        member_id = request.match_info['user_id']

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
            return _err(f'Error kicking member: {err!r}')

    @auth_route
    async def h_change_nick(self, request, user):
        """`PATCH /guilds/{guild_id}/members/@me/nick`.

        Modify your nickname.
        Returns a 200.
        Dispatches GUILD_MEMBER_UPDATE to relevant clients.
        """

        guild_id = request.match_info['guild_id']

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

        return web.Response(status=200, text=nickname)

    @auth_route
    async def h_ban_member(self, request, user):
        """`PUT /guilds/{guild_id}/bans/{user_id}`.

        Ban a member from a guild.
        Dispatches GUILD_BAN_ADD event to relevant clients.
        """

        guild_id = request.match_info['guild_id']
        target_id = request.match_info['user_id']

        try:
            payload = await request.json()
        except:
            payload = {}

        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err(errno=10004)

        target = self.server.get_user(target_id)
        if target is None:
            return _err(errno=10013)

        try:
            await guild.ban(target, delete_days=payload.get('delete-message-days'))
            return web.Response(status=204)
        except Exception as err:
            log.error("Error banning user", exc_info=True)
            return _err('Error banning user: {err!r}')

    @auth_route
    async def h_unban_member(self, request, user):
        """`DELETE /guilds/{guild_id}/bans/{user_id}`.

        Unban a member from a guild.
        Dispatches GUILD_BAN_REMOVE event to relevant clients.
        """

        guild_id = request.match_info['guild_id']
        target_id = request.match_info['user_id']

        try:
            guild_id = int(guild_id)
            target_id = int(target_id)
        except:
            return _err('malformed url')

        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err(errno=10004)

        target = self.server.get_user(target_id)
        if target is None:
            return _err(errno=10013)

        try:
            await guild.unban(target)
            return web.Response(status=204)
        except Exception as err:
            log.error("Error banning user", exc_info=True)
            return _err('Error banning user: {err!r}')

    @auth_route
    async def h_edit_guild(self, request, user):
        """`PATCH /guilds/{guild_id}`.

        Edit a guild.
        Dispatches GUILD_UPDATE to relevant clients.
        """

        guild_id = request.match_info['guild_id']

        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err(errno=10004)

        try:
            _payload = await request.json()
        except:
            return _err('error parsing payload')

        if user.id != guild.owner_id:
            return _err(errno=40001)

        edit_payload = self.guild_edit_schema(_payload)

        try:
            new_guild = await guild.edit(edit_payload)
            return _json(new_guild.as_json)
        except Exception as err:
            return _err(f'{err!r}')

    @auth_route
    async def h_delete_guild(self, request, user):
        """`DELETE /guilds/{guild_id}`.
        
        Delete a guild. Returns the guild object on success.
        Dispatches GUILD_DELETE to all guild members.
        """
        guild_id = request.match_info['guild_id']
        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err(errno=10004)

        if user.id != guild.owner_id:
            return _err(errno=40001)

        # NOTE: I wonder how we should do the audit log
        # reason handling, tbh I don't know if we even
        # are going to implement them :thinking:
        await guild.delete()
        return _json(guild.as_json)

    @auth_route
    async def h_create_channel(self, request, user):
        """`POST /guilds/{guild_id}/channels`.

        Create a channel in a guild.
        Dispatches CHANNEL_CREATE to respective clients.
        """

        guild_id = request.match_info['guild_id']

        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return _err(errno=10004)

        payload = await request.json()
        raw_channel = self.channel_create_schema(payload)

        raw_channel['type'] = raw_channel.get('type', 'text')
        t = raw_channel['type']
        if t == 'voice':
            raw_channel['bitrate'] = raw_channel.get('bitrate', 69)
            raw_channel['user_limit'] = raw_channel.get('user_limit', 0)

        raw_channel['permission_overwrites'] = raw_channel.get('permission_overwrites', [])

        channel = await guild.create_channel(raw_channel)
        return _json(channel.as_json)
