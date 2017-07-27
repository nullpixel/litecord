"""
voice/gateway.py - voice websocket implementaiton

    This contains the implementation for a voice websocket
    that runs in a specific endpoint.
"""

from ..enums import VOICE_OP
from ..ws import WebsocketConnection, handler, StopConnection

class VoiceConnection(WebsocketConnection):
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
    def __init__(self, ws, **kwargs):
        super().__init__(ws)
        self.v_server = kwargs['server']
        self.path = kwargs['path']

        self.identified = False

        self.udp_port = 1234

    @handler(VOICE_OP.SELECT_PROTOCOL)
    async def v_select_proto_handler(self, data):
        """Handle OP 1 Select Protocol.

        Sends OP 4 Session Description.
        """

        if not self.identified:
            raise StopConnection(4003, 'Not identified')

        proto = data.get('protocol')
        if proto != 'udp':
            raise StopConnection(4001, 'Invalid protocol')

        proto_data = data.get('data')
        if proto_data is None:
            raise StopConnection(4001, 'proto data not found')

        try:
            proto_data = {
                'address': proto_data['address'],
                'port': proto_data['port'],
                'mode': proto_data['mode'],
            }
        except KeyError:
            raise StopConnection(4001, 'Invalid protocol data')

        await self.send_op(VOICE_OP.SESSION_DESCRIPTION, {})

    @handler(VOICE_OP.IDENTIFY)
    async def v_identify_handler(self, data):
        """Handle OP 0 Identify.

        Sends OP 2 Ready.
        """

        server_id = data.get('server_id')
        user_id = data.get('user_id')
        session_id = data.get('session_id')
        token = data.get('token')

        if not server_id or not user_id or not session_id or not token:
            raise StopConnection(4001, 'Invalid payload')

        #self.ssrc = self.get_ssrc()
        self.ssrc = 49134

        await self.send_op(VOICE_OP.READY, {
            'ssrc': self.ssrc,
            'port': self.udp_port,
            'modes': ["plain"],
            'heartbeat_interval': 1,
        })

    async def cleanup(self):
        print('rip this guy')
