import logging
from .objects import LitecordObject, VoiceChannel, User

log = logging.getLogger(__name__)

class VoiceState(LitecordObject):
    """Represents a voice state.

    You should only get VoiceState objects through `VoiceChannelState.create_state`,
    :meth:`VoiceServer.connect` or :meth:`VoiceManager.link_connection`.

    Attributes
    ----------
    v_man: :class:`VoiceManager`
        Voice manager instance.
    v_server: :class:`VoiceServer`
        Voice server instance.
    vc_state: :class:`VoiceChannelState`
        Voice channel state this user state is referring to.
    channel: :class:`VoiceChannel`
        Voice channel this state is referring to.
    guild: :class:`Guild`
        Guild this state is referring to
    conn: :class:`Connection`
        The connection this state is referring to
    session_id: str
        Session ID of this voice state.
    """
    def __init__(self, server, v_channel_state, channel: VoiceChannel, conn):
        LitecordObject.__init__(self, server)

        self.v_man = server.voice
        self.v_server = v_channel_state.v_server
        self.vc_state = v_channel_state

        self.channel = channel
        self.guild = channel.guild
        self.conn = conn

        self.session_id = v_server.get_session_id(conn.user.id)

        self.deaf = False
        self.mute = False
        self.self_deaf = False
        self.self_mute = False
        self.supress = False

    def get_json(self, display_sess_id=False) -> dict:
        res = {
            'guild_id': str(self.guild.id),
            'channel_id': str(self.channel.id),
            'user_id': str(self.user.id),
            'session_id': str(self.session_id),
            'deaf': self.deaf,
            'mute': self.mute,
            'self_deaf': self.self_deaf,
            'self_mute': self.self_mute,
            'supress': self.supress,
        }

        if not display_sess_id:
            res.pop('session_id')

        return res


class VoiceChannelState(LitecordObject):
    """Represents a voice channel's state.

    With instances of this class, it is possible to instantiate
    :class:`VoiceState` objects, and make a successful connection to VWS(Voice Websocket).

    Attributes
    ----------
    v_channel: :class:`VoiceChannel`
        Voice channel this state is referring to.
    states: dict
        Relates User IDs to :class:`VoiceState` objects.
    """
    def __init__(self, server, v_channel):
        super().__init__(server)
        if not isinstance(v_channel, VoiceChannel):
            log.error(f'[VChannelState] received a non-voice channel')

        self.v_channel = v_channel

        self.states = {}

    async def create_state(self, user: User, **kwargs) -> VoiceState:
        """Create a new :class:`VoiceState` to this user.

        Returns
        -------
        The new VoiceState.
        """

        if user.id in self.states:
            # remove old state
            self.states.pop(user.id)

        v_state = VoiceState(self.server, self.v_channel.v_server, user)
        self.states[user.id] = v_state
        return v_state

    async def remove_state(self, v_state: VoiceState):
        """Remove a VoiceState from VoiceChannelState"""
        if v_state.channel.id != self.v_channel.id:
            return None

        self.states.pop(v_state.user.id)
