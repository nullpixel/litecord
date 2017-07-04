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

class VoiceConnection:
    """Represents a voice websocket connection.

    This looks like :class:`Connection` in some parts, but it
    handles completly different OP codes.

    Parameters
    ----------
    server: :class:`LitecordServer`
        Server instance.
    ws: `WebSocketServerProtocol`_
        Websocket.
    path: str
        Websocket path.
    """
    def __init__(self, server, ws, path):
        self.server = server
        self.ws = ws
        self.path = path

        self.identified = False

        self.udp_port = 1234

        self.op_handlers = {
            VOICE_OP.IDENTIFY: self.v_identify_handler,
            VOICE_OP.SELECT_PROTOCOL: self.v_select_proto_handler,
            VOICE_OP.READY: self.v_ready,
            VOICE_OP.HEARTBEAT: self.v_heartbeat_handler,
            VOICE_OP.SESSION_DESCRIPTION: self.v_sessdesc_handler,
            VOICE_OP.SPEAKING: self.v_speaking_handler,
        }

    async def send_anything(self, obj):
        """Send anything through the voice websocket."""
        return (await self.ws.send(obj))

    async def send_json(self, obj):
        """Send a JSON payload through the voice websocket.

        Parameters
        ----------
        obj: any
            any JSON serializable object.
        """
        return (await self.send_anything(json.dumps(obj)))

    async def send_op(self, op, data=None):
        """Send a packet through the voice websocket.

        Parameters
        ----------
        op: int
            Packet's OP code.
        data: any
            Any JSON serializable object.
        """

        if data is None:
            data = {}

        payload = {
            # op is always an int
            # data can be a dict, int or bool
            'op': op,
            'd': data,
        }
        return (await self.send_json(payload))

    async def v_select_proto_handler(self, data):
        """Handle OP 1 Select Protocol.

        Sends OP 4 Session Description.
        """

        if not self.identified:
            log.warning("client sent OP1 but it isn't identified.")
            return False

        proto = data.get('protocol')
        if proto != 'udp':
            return False

        proto_data = data.get('data')
        if proto_data is None:
            return False

        try:
            proto_data = {
                'address': proto_data['address'],
                'port': proto_data['port'],
                'mode': proto_data['mode'],
            }
        except KeyError:
            return False

        await self.send_op(VOICE_OP.SESSION_DESCRIPTION, {})

    async def v_identify_handler(self, data):
        """Handle OP 0 Identify.

        Sends OP 2 Ready.
        """

        server_id = data.get('server_id')
        user_id = data.get('user_id')
        session_id = data.get('session_id')
        token = data.get('token')

        if not server_id or not user_id or not session_id or not token:
            log.error("Erroneous OP0 Identify payload")
            return False

        #self.ssrc = self.get_ssrc()
        self.ssrc = 49134

        await self.send_op(VOICE_OP.READY, {
            'ssrc': self.ssrc,
            'port': self.udp_port,
            'modes': ["plain"],
            'heartbeat_interval': 1,
        })

    async def process_recv(self, payload):
        """Process a payload sent by the client.

        Parameters
        ----------
        payload: dict
            https://discordapp.com/developers/docs/topics/gateway#gateway-op-codespayloads
        """

        op = payload.get('op')
        data = payload.get('d')

        if op not in self.op_handlers:
            log.info("opcode not found, closing with 4001")
            await self.ws.close(4001)
            return False

        handler = self.op_handlers[op]
        return (await handler(data))

    async def run(self):
        """meme."""

        try:
            while True:
                received = await self.ws.recv()
                if len(received) > 4096:
                    await self.ws.close(4002)
                    await self.cleanup()
                    break

                try:
                    payload = json.loads(received)
                except:
                    await self.ws.close(4002)
                    await self.cleanup()
                    break

                continue_receiving = await self.process_recv(payload)

                if not continue_receiving:
                    log.info("Stopped receiving from process_recv")
                    await self.cleanup()
                    break
        except websockets.ConnectionClosed as err:
            log.info(f"[vws] closed, code {err.code!r}")
            await self.cleanup()
        except Exception as err:
            # if any error we just close with 4000
            log.error('Error while running VWS', exc_info=True)
            await self.ws.close(4000, f'vws error: {err!r}')
            await self.cleanup()
            return

        await self.ws.close(1000)

    async def cleanup(self):
        print('rip this guy')


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
