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


class BareGuild:
    def __init__(self, guild_id):
        self.id = guild_id


class Guild(LitecordObject):
    """A general guild.

    Parameters
    ----------
    server: :class:`LitecordServer`
        Server instance.
    raw: dict
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

    __slots__ = ('raw', 'channel_ids', 'role_ids', 'id', 'name', 'icons',
        'created_at', 'owner_id', 'features', 'channels', 'member_ids',
        'members', 'member_count', 'roles', 'emojis', 'banned_ids', '_viewers')

    def __init__(self, server, raw):
        super().__init__(server)
        self.raw = raw
        self.id = int(raw['guild_id'])
        self.created_at = self.to_timestamp(self.id)

        self.members = {}
        self.roles = {}
        self.channels = {}
        self.icons = {'splash': None}

        # one day... one day.
        self.emojis = {}

        self._viewers = []
        self._from_raw(raw)

    def _update_caches(self, raw):
        for channel_id in self.channel_ids:
            channel = self.guild_man.get_channel(channel_id)
            self.channels[channel.id] = channel
            channel.guild = self

        for member_id in self.member_ids:
            user = self.server.get_user(member_id)
            if user is None:
                log.warning('user %d not found', user_id)
                continue

            raw_member = self.guild_man.raw_members[self.id][user.id]
            member = Member(self.server, self, user, raw_member)
            self.members[member.id] = member
        
        for role_id in self.role_ids:
            role = self.guild_man.get_role(role_id)
            self.roles[role.id] = role
            role.guild = self

    def _from_raw(self, raw):
        self.name = raw['name']
        self.icons['icon'] = raw['icon']
        self.owner_id = int(raw['owner_id'])

        self.region = raw['region']
        self.features = raw['features']

        self.channel_ids = raw['channel_ids']
        self.member_ids = raw['member_ids']
        self.role_ids = raw['role_ids']
        self.banned_ids = raw.get('bans', [])
        self._update_caches(raw)

        self.member_count = len(self.members)
        self.owner = self.members.get(self.owner_id)
        if self.owner is None:
            log.error('Guild %d without owner(%d)!', self.id, self.owner_id)

    def __repr__(self):
        return f'<Guild id={self.id} name={self.name!r} owner={self.owner.user!r} region={self.region} ' \
                'member_count={self.member_count}>'

    def __eq__(self, other):
        return isinstance(other, Guild) and other.id == self.id

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

