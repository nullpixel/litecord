from .channel import BaseChannel

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

    def __init__(self, server, raw_channel, guild=None):
        super().__init__(server, raw_channel, guild)

        self.bitrate = raw_channel.get('birtate', 69)
        self.user_limit = raw_channel.get('user_limit', 0)

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

