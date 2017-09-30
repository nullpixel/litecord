from .channel import BaseGuildChannel
from .base import LitecordObject
from .guild import BareGuild

class VoiceGuildChannel(BaseGuildChannel):
    """Represents a voice channel.

    Attributes
    ----------
    bitrate: int
        Voice channel's bitrate.
    user_limit: int
        Maximum number of users that can enter the channel.
    """

    __slots__ = ('bitrate', 'user_limit', 'parent', 'parent_id')

    def __init__(self, server, parent, raw, guild=None):
        super().__init__(guild, parent, raw)
        self.server = server
        self._update(guild, parent, raw)

    def _update(self, guild, parent, raw):
        super()._update(guild, parent, raw)
        self.bitrate = raw.get('bitrate', 69)
        self.user_limit = raw.get('user_limit', 0)

    @property
    def as_json(self):
        return {
            'id': str(self.id),
            'guild_id': str(self.guild_id),
            'name': self.name,
            'type': self.type,
            'position': self.position,
            'permission_overwrites': [],

            'bitrate': self.bitrate,
            'user_limit': self.user_limit,

            'parent_id': str(self.parent_id),
        }

class VoiceRegion(LitecordObject):
    """Represents a voice region
    
    Attributes
    ----------
    id: int
        Voice Region ID.
    name: str
        Voice Region Name.
    custom: bool
        Wheter this voice region is custom.
    """
    def __init__(self, server, _raw):
        super().__init__(server)
        self.id = int(_raw['id'])
        self.name = _raw['name']
        self.custom = _raw.get('custom', False)

    @property
    def as_json(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'sample_hostname': 'localhost',
            'sample_port': 6969,
            'vip': True,
            'optimal': False,
            'deprecated': False,
            'custom': self.custom,
        }


class DMChannel:
    """A DM channel object.
    
    Attributes
    ----------
    id: int
        DM Channel ID.
    recipients: List[:class:`User`]
        The recipients of the DM.
    text: :class:`BaseTextChannel`
        Text channel that is linked to the DM.
    voice: :class:`BaseVoiceChannel`
        Voice channel linked to the DM.
    """
    def __init__(self, recipients, raw):
        self.id = raw['id']
        self._update(recipients, raw)

    def _update(recipients, raw):
        self.recipients = recipients

        self.text = BaseTextChannel(raw)
        self.voice = BaseVoiceChannel(raw)

    async def _single_dispatch(self, user, e_name, e_data):
        """If user is a bot, dispatches to Shard 0"""
        if user.bot and user.sharded:
            shards = self.server.get_shards(user.id)
            shard = shard.get(0)
            if shard is None:
                return
            await shard.dispatch(e_name, e_data)
        else:
            await user.dispatch(e_name, e_data)

    async def dispatch(self, e_name, e_data):
        # Dispatch to both users
        await self._single_dispatch(self.recipients[0], e_name, e_data)
        await self._single_dispatch(self.recipients[1], e_name, e_data)

    @property
    def as_json(self):
        return {
            'id': str(self.id),
            'type': self.type,
            'last_message_id': self.text.last_message_id,
            'recipients': [u.as_json for u in self.recipients]
        }
