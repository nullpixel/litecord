import datetime
import logging

from .base import LitecordObject
from .channel import TextChannel
from .voice import VoiceChannel
from .member import Member
from .role import Role
from ..snowflake import snowflake_time
from ..utils import dt_to_json

log = logging.getLogger(__name__)


class Guild(LitecordObject):
    """A general guild.

    Parameters
    ----------
    server: :class:`LitecordServer`
        Server instance.
    _guild_data: dict
        Raw gulid data.

    Attributes
    ----------
    _data: dict
        Raw guild data.
    _channel_data: list(raw channel)
        Raw channel data for the guild.
    _role_data: list(:class:`Role`)
        Raw role data for the guild.

    id: int
        The guild's snowflake ID.
    name: str
        Guild's name.
    icons: dict
        Contains two keys: ``"icon"`` and ``"splash"``.
    created_at: datetime.datetime
        Guild's creation date.
    owner_id: int
        Guild owner's ID.
    region: str
        Guild's voice region.
    features: list(str)
        Features this guild has.
    channels: dict
        Channels this guild has.
    member_ids: list(int)
        Guild member ids.
    members: dict
        Members this guild has.
    member_count: int
        Amount of members in this guild.
    banned_ids: list(str)
        User IDs that are banned in this guild.
    _viewers: list(int)
        List of user IDs that are viewers of this guild and will have specific
        guild events dispatched to them.

    TODO:
        roles: A list of `Role` objects.
        emojis: A list of `Emoji` objects.
    """

    __slots__ = ('_data', 'channel_data', '_role_data', 'id', 'name', 'icons',
        'created_at', 'owner_id', 'features', 'channels', 'member_ids',
        'members', 'member_count', 'roles', 'emojis', 'banned_ids', '_viewers')

    def __init__(self, server, _guild_data):
        super().__init__(server)
        self._data = _guild_data
        self.id = int(_guild_data['id'])
        self.name = _guild_data['name']
        self.icons = {
            'icon': _guild_data['icon'],
            'splash': '',
        }

        creation_timestamp = snowflake_time(self.id)
        self.created_at = datetime.datetime.fromtimestamp(creation_timestamp)

        self.owner_id = int(_guild_data['owner_id'])
        self.region = _guild_data['region']
        self.emojis = []
        self.features = _guild_data['features']

        self._channel_data = _guild_data['channels']
        self.channels = {}

        for raw_channel in self._channel_data:
            raw_channel['guild_id'] = self.id
            channel_type = raw_channel['type']
            channel = None

            if channel_type == 'text':
                channel = TextChannel(server, raw_channel, self)
            elif channel_type == 'voice':
                channel = VoiceChannel(server, raw_channel, self)
            else:
                raise Exception(f'Invalid type for channel: {channel_type}')

            self.channels[channel.id] = channel

        # list of snowflakes
        self.member_ids = [int(member_id) for member_id in _guild_data['members']]
        self.members = {}

        for member_id in self.member_ids:
            member_id = int(member_id)

            user = self.server.get_user(member_id)
            if user is None:
                log.warning(f"user {member_id} not found")
                continue

            raw_member = server.guild_man.get_raw_member(self.id, user.id)

            member = Member(server, self, user, raw_member)
            self.members[member.id] = member

        self.owner = self.members.get(self.owner_id)
        if self.owner is None:
            log.error("Guild without owner!")

        self._role_data = _guild_data['roles']
        self.roles = {}

        for raw_role in self._role_data:
            role = Role(server, self, raw_role)
            self.roles[role.id] = role

        self.banned_ids = _guild_data.get('bans', [])

        self.member_count = len(self.members)
        self._viewers = []

    def __repr__(self):
        return f'Guild({self.id}, {self.name!r})'

    def mark_watcher(self, user_id):
        """Mark a user ID as a viewer in that guild, meaning it will receive
        events from that gulid using :py:meth:`Guild.dispatch`.
        """
        user_id = int(user_id)
        try:
            self._viewers.index(user_id)
        except:
            self._viewers.append(user_id)
            log.debug(f'Marked {user_id} as watcher of {self!r}')

    def unmark_watcher(self, user_id):
        """Unmark user from being a viewer in this guild."""
        user_id = int(user_id)
        try:
            self._viewers.remove(user_id)
            log.debug(f'Unmarked {user_id} as watcher of {self!r}')
        except:
            pass

    def all_channels(self):
        """Yield all channels from a guild"""
        for channel in self.channels.values():
            yield channel

    @property
    def voice_channels(self):
        """Yield all voice channels from a guild."""
        for channel in self.all_channels():
            if channel.str_type == 'voice':
                yield channel

    def all_members(self):
        """Yield all members from a guild"""
        for member in self.members.values():
            yield member

    @property
    def viewers(self):
        """Yield all members that are viewers of this guild.

        Keep in mind that :py:meth:`Guild.viewers` is different from :py:meth:`Guild.online_members`.

        Members are viewers automatically, but if they are Atomic-Discord clients,
        they only *are* viewers if they send a OP 12 Guild Sync(:py:meth:`Connection.guild_sync_handler`)
        to the gateway.
        """
        for member in self.members.values():
            try:
                self._viewers.index(member.id)
                yield member
            except:
                pass

    @property
    def online_members(self):
        """Yield all members that have an identified connection"""
        for member in self.members.values():
            if member.user.online:
                yield member

    @property
    def presences(self):
        """Returns a list of :class:`Presence` objects for all online members."""
        return [self.server.presence.get_presence(self.id, member.id).as_json \
            for member in self.online_members]

    async def dispatch(self, evt_name, evt_data):
        """Dispatch an event to all guild viewers.

        Parameters
        ----------
        evt_name: str
            Event name.
        evt_data: dict
            Event data.

        Returns
        -------
        int:
            Total number of members that this event was dispatched to.
        """
        total, dispatched = 0, 0

        for member in self.viewers:
            success = await member.dispatch(evt_name, evt_data)

            if not success:
                self.unmark_watcher(member.id)
            else:
                dispatched += 1
            total += 1

        log.debug(f'Dispatched {evt_name} to {dispatched}/{total} gulid viewers')

        return dispatched

    async def add_member(self, user):
        """Add a :class:`User` to a guild.

        Returns
        -------
        :class:`Member`.
        """

        return (await self.guild_man.add_member(self, user))

    async def ban(self, user, delete_days=None):
        """Ban a user from the guild.

        Raises
        ------
        Exception on failure.
        """
        await self.guild_man.ban_user(self, user, delete_days)

    async def unban(self, user):
        """Unban a user from the guild.

        Raises
        ------
        Exception on failure.
        """
        await self.guild_man.unban_user(self, user)

    async def edit(self, edit_payload):
        """Edit a guild.

        Returns
        -------
        :class:`Guild`
            The edited guild as a object.
        """
        return await self.guild_man.edit_guild(self, edit_payload)

    async def create_channel(self, chan_create_payload):
        """Create a channel in a guild.

        Returns
        -------
        :class:`Channel`
            New channel.
        """
        return await self.guild_man.create_channel(self, chan_create_payload)

    async def delete(self):
        """Delete a guild."""
        return await self.guild_man.delete_guild(self)

    @property
    def as_json(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'icon': self.icons['icon'],
            'splash': self.icons['splash'],
            'owner_id': str(self.owner_id),
            'region': self.region,

            # voice things aka NOT USABLE
            'afk_channel_id': '00000000000',
            'afk_timeout': None,

            # TODO: how are these supposed to even work?
            'embed_enabled': None,
            'embed_channel_id': None,

            'verification_level': 0, # TODO
            'default_message_notifications': -1, # TODO
            'roles': self.iter_json(self.roles),
            'emojis': self.emojis,
            'features': self.features,
            'mfa_level': -1, # TODO

            # those fields are only in the GUILD_CREATE event
            # but we can send them anyways :')
            # usually clients ignore this, so we don't need to worry

            'joined_at': dt_to_json(self.created_at),
            'large': self.member_count > 250,
            'unavailable': False,
            'member_count': self.member_count,
            'voice_states': [],

            # arrays of stuff
            'members': self.iter_json(self.members),
            'channels': self.iter_json(self.channels),
            'presences': self.presences,
        }

    @property
    def as_invite(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'icon': self.icons['icon'],
            'splash': self.icons['splash'],
        }

