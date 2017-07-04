"""
voice/gateway.py - voice websocket implementaiton

    This contains the implementation for a voice websocket
    that runs in a specific endpoint.
"""

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
