"""
voice/server.py - Litecord voice server implementation

    This file contains the necessary stuff to run an almost working
    voice implementation.
"""
import json
import logging
import asyncio

import websockets

from ..basics import VOICE_OP
from ..objects import LitecordObject
from ..err import VoiceError
from ..snowflake import get_raw_token
from ..objects import VoiceChannel, User

from .objects import VoiceChannelState, VoiceState
from .gateway import VoiceConnection

log = logging.getLogger(__name__)

class VoiceServer(LitecordObject):
    """Represents a voice server.

    Each guld gets a VoiceServer instance.
    Each voice channel gets a VoiceChannelState instance.
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
        token = await get_raw_token('litecord_vws-')
        self.tokens[token] = user_id
        return token

    async def connect(self, channel: VoiceChannel, conn) -> VoiceState:
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

        self.voice_servers = {}

        for guild in self.guild_man.all_guilds():
            self.voice_servers[guild.id] = VoiceServer(server, guild)

    def get_voiceserver(self, guild_id):
        guild_id = int(guild_id)
        return self.voice_servers.get(guild_id)

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

        async def voice_henlo(websocket, path):
            log.info("Starting websocket connection")
            v_conn = VoiceConnection(self, websocket, path)
            await v_conn.run()
            log.info("Stopped connection", exc_info=True)

            await v_conn.cleanup()

        vws = flags['server']['voice_ws']
        log.info(f'[voice_ws] running at {vws[0]}:{vws[1]}')
        self.vws_tuple = vws

        ws_server = websockets.serve(voice_henlo, host=vws[0], port=vws[1])
        await ws_server
        return True
