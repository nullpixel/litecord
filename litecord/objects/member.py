import datetime

from .base import LitecordObject
from ..utils import dt_to_json

class Member(LitecordObject):
    """A general member object.

    A member is linked to a guild.

    Parameters
    ----------
    server: :class:`LitecordServer`
        server instance.
    guild: :class:`Guild`
        The guild this member is from.
    user: :class:`User`
        The user this member represents.
    raw_member: dict
        Raw member data.

    Attributes
    ----------
    _raw: dict
        Raw member data.
    user: :class:`User`
        The user this member represents.
    guild: :class:`Guild`
        The guild this member is from.
    id: int
        The member's snowflake ID. This is the same as :py:meth:`User.id`.
    owner: bool
        If the member is the guild owner.
    nick: str
        Member's nickname, becomes :py:const:`None` if no nickname is set.
    joined_at: datetime.datetime
        The date where this member was created in the guild
    roles: List[:class:`Role`]
        List of roles this member has.
    voice_deaf: bool
        If the member is deafened on the guild.
    voice_mute: bool
        If the member is muted on the guild.
    """

    __slots__ = ('_raw', 'user', 'guild', 'id', 'owner', 'nick', 'joined_at',
        'roles', 'voice_deaf', 'voice_mute')

    def __init__(self, server, guild, user, raw):
        super().__init__(server)
        self._raw = raw
        self._update(guild, user, raw)

    def _update(self, guild, user, raw):
        self.user = user
        self.guild = guild

        self.id = self.user.id
        self.is_owner = (self.id == self.guild.owner_id)
        self.nick = raw.get('nick')

        joined_timestamp = raw.get('joined')
        if joined_timestamp is not None:
            self.joined_at = datetime.datetime.strptime(joined_timestamp, \
                "%Y-%m-%dT%H:%M:%S.%f")
        else:
            log.warning("Member without joined timestamp.")

        self.roles = raw.get('roles', [])

        self.voice_deaf = False
        self.voice_mute = False

    def __repr__(self):
        return f'Member({self.user!r}, {self.guild!r})'

    def update(self, new_data):
        """Update a member object based on new data."""
        self.nick = new_data.get('nick') or self.nick

    @property
    def connections(self):
        """Yield the user's connections."""
        return self.user.connections

    async def dispatch(self, evt_name, evt_data):
        """Dispatch an event to a member.

        Dispatches an event in the same way :py:meth:`User.dispatch` does.
        """
        conns = list(self.connections)
        if len(conns) < 1:
            return

        c = self.user.connections[0]
        if c.sharded:
            wanted_shard = self.guild_man.get_shard(self.guild.id)
            shards = self.server.get_shards(self.user)

            shard = shards.get(wanted_shard)
            if shard is None:
                log.warning('[member:dispatch] Shard %d not found', wanted_id)
                return

            return await shard.dispatch(evt_name, evt_data)
        else:
            return await self.user.dispatch(evt_name, evt_data)

    @property
    def as_json(self):
        return {
            'user': self.user.as_json,
            'nick': self.nick,
            'roles': self.roles,
            'joined_at': dt_to_json(self.joined_at),
            'deaf': self.voice_deaf,
            'mute': self.voice_mute,
        }

    @property
    def as_invite(self):
        """Returns a version to be used in :py:meth:`Invite.as_json`."""
        return {
            'username': self.user.username,
            'discriminator': str(self.user.discriminator),
            'id': str(self.user.id),
            'avatar': self.user.avatar_hash,
        }

    @property
    def user_guild(self):
        return {
            'id': str(self.guild.id),
            'name': self.guild.name,
            'icon': self.guiild.icons['icon'],
            'owner': self.owner,
            'permissions': 0,
        }

