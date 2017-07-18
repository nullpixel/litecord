from .channel import BaseChannel
from .base import LitecordObject

class VoiceChannel(BaseChannel):
    """Represents a voice channel.

    Attributes
    ----------
    bitrate: int
        Voice channel's bitrate.
    user_limit: int
        Maximum number of users that can enter the channel.
    """

    __slots__ = ('bitrate', 'user_limit')

    def __init__(self, server, raw, guild=None):
        super().__init__(server, raw, guild)
        self._update(guild, raw)

    def _update(self, guild, raw):
        BaseChannel._update(self, guild, raw)
        self.bitrate = raw.get('bitrate', 69)
        self.user_limit = raw.get('user_limit', 0)

    async def voice_request(self, connection):
        """Request a voice state from the voice manager."""
        return await self.server.voice.link_connection(connection, self)

    @property
    def as_json(self):
        return {
            'id': str(self.id),
            'guild_id': str(self.guild_id),
            'name': self.name,
            'type': self.type,
            'position': self.position,
            'is_private': self.is_private,
            'permission_overwrites': [],

            'bitrate': self.bitrate,
            'user_limit': self.user_limit,
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
