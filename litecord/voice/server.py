"""
voice/server.py - Litecord voice server implementation

    This file contains the necessary stuff to run an almost working
    voice implementation.
"""
import json
import logging
import asyncio

import websockets

from ..enums import VoiceOP
from ..objects import LitecordObject
from ..err import VoiceError
from ..objects import VoiceGuildChannel, User, VoiceRegion

from .objects import VoiceChannelState, VoiceState
from .gateway import VoiceConnection

log = logging.getLogger(__name__)


class VoiceGuildManager:
    """Represents a voice guild manager.
    
    This manager has VoiceChannelState obejcts
    it can query upon.
    """
    def __init__(self, vs, guild):
        self.vserver = vs
        self.guild = guild

        self.state = []
        for v_channel in guild.voice_channels:
            #self.state.append(VoiceChannelState(v_channel))
            pass

    def get_state(self, channel_id: int):
        """Get a VoiceChannelState object."""
        for vc_state in self.state:
            if vc_state.id == channel_id:
                return vc_state
        return None

class VoiceServer(LitecordObject):
    """Represents a voice server.

    Each guld gets a VoiceGuildManager instance.
    Each voice channel gets a VoiceChannelState instance, tied to the VoiceGuildManager of the guild.
    Each connection to the voice channel gets a VoiceState instance.

    Attributes
    ----------
    guild: :class:`Guild`
        The guild this server is referring to.
    channels: dict
        Relates Channel IDs to :class:`VoiceChannelState` objects.
    endpoint: str
        Address of the Voice Websocket.
    tokens: dict
        Relates tokens(str) to User ID.
    global_staet: dict
        Relates User IDs to :class:`VoiceState`, if they're connected to the Voice server.
    """
    def __init__(self, server, guild):
        LitecordObject.__init__(self, server)

        self.guild = guild

        self.states = {}
        for v_channel in guild.voice_channels:
            self.states[v_channel.id] = VoiceChannelState(self.server, v_channel)

        vws = server.flags['server']['voice_ws']
        self.endpoint = f'{vws[0]}:{vws[1]}'

        self.tokens = {}
        self.global_state = {}

    async def make_token(self, user_id: int) -> str:
        # HOW TO FIX
        token = await howtofixthis('litecord_vws-')
        self.tokens[token] = user_id
        return token

    async def connect(self, channel: VoiceGuildChannel, conn) -> VoiceState:
        """Create a :class:`VoiceState`"""
        vc_state = self.states[channel.id]
        if vc_state is None:
            return None

        v_state = vc_state.create_state(conn.user.id)
        if v_state is None:
            return None

        self.global_state[user_id] = vc_state
        return v_state

    async def disconnect(self, v_state: VoiceState):
        """Disconnect a user from the channel."""
        vc_state.remove_state(v_state)
        self.global_state.pop(v_state.user.id)

    def get_json(self, token: str) -> dict:
        """Get a JSON serializable dict to send in a VOICE_SERVER_UDPATE event."""
        user_id = self.tokens[token]
        vc_state = self.global_state[user_id]
        return {
            'token': token,
            'guild_id': str(vc_state.channel.guild.id),

            # That is the endpoint for VWS.
            'endpoint': self.endpoint,
        }

    async def handle_udp(self, client):
        """Handler for UDP voice data."""
        pass

class VoiceManager:
    """Voice management for Litecord.

    Parameters
    ----------
    server: :class:`LitecordServer`
        Server instance.

    """
    def __init__(self, server):
        self.server = server
        self.guild_man = server.guild_man

        self.voice_regions = [
            VoiceRegion(server, {'id': 0, 'name': 'Brazeel'}),
            VoiceRegion(server, {'id': 1, 'name': 'The Wall'}),
            VoiceRegion(server, {'id': 2, 'name': 'Whorehouse', 'custom': True}),
        ]

        self.vg_managers = []

    async def __load(self):
        async for guild in self.guild_man.all_guilds():
            self.vg_managers.append(VoiceGuildManager(self, guild))

    async def kill_voice(self, vg):
        vcs_count = 0
        for vcs in vg.vc_states:
            try:
                await vcs.kill()
                vcs_count += 1
            except:
                log.error('Error shutting down %r', vcs, exc_info=True)

        log.info('Shutted down %d voice servers', vcs_count)

    async def __unload(self):
        for vg in self.vg_managers:
            await self.kill_voice(vg)

    def get_vgmanager(self, guild_id: int):
        for vg_manager in self.vg_managers:
            if vg_manager.guild.id == guild_id:
                return vg_manager
        return None

    async def connect(self, channel, conn):
        """Create a :meth:`VoiceState` object for a connection
        that is going to connect to the voice websocket.
        """

        vstate = await vg_man.connect(channel, conn)
        return vstate

    async def disconnect(self, guild, conn):
        """Disconnect a client from voice"""
        vg_man = self.get_vgmanager(guild.id)
        if vg_man is None:
            return

        await vg_man.disconnect(conn)
        return True

    async def link_connection(self, conn, channel):
        if channel.str_type != 'voice':
            raise VoiceError('Channel is not a voice channel')

        v_server = self.get_vserver(channel.guild.id)
        if v_server is None:
            raise VoiceError('No voice server found')

        v_state = await v_server.connect(channel, conn)
        return v_state

    async def init_task(self, flags):
        """dude people are gonna send voice packets of them crying"""

        async def voice_henlo(ws, path):
            log.info(f'[vws] new connection at {path}')

            v_conn = VoiceConnection(ws, server=self, path=path)
            await v_conn.run()

        vws = flags['server']['voice_ws']
        log.info(f'[voice_ws] running at {vws[0]}:{vws[1]}')
        self.vws_tuple = vws

        ws_server = websockets.serve(voice_henlo, host=vws[0], port=vws[1])
        await ws_server
        return True
