import json
import websockets
import logging
import asyncio
import uuid
import traceback

from .basics import OP, GATEWAY_VERSION

log = logging.getLogger(__name__)

sessions = {}
_valid_tokens = []

class Connection:
    def __init__(self, ws, path):
        self.ws = ws
        self.path = path
        self._seq = 0
        self.properties = {}

    def basic_hello(self):
        return {
            'op': OP["HELLO"],
            'd': {
                'heartbeat_interval': 3000,
                '_trace': [],
            }
        }

    def gen_sessid(self):
        tries = 0
        new_id = str(uuid.uuid4().fields[-1])[:5]
        while new_id in sessions:
            if tries >= TWEETID_MAX_TRIES:
                return None

            new_id = str(uuid.uuid4().fields[-1])[:5]
            tries += 1

        return new_id

    async def send_json(self, obj):
        res = await self.ws.send(json.dumps(obj))
        return res

    async def send_op(self, op, data={}):
        payload = {
            'op': op,
            'd': data,
        }
        return (await self.send_json(payload))

    async def send_dispatch(self, evt_name, evt_data={}):
        payload = {
            'op': OP["DISPATCH"],
            's': self._seq,
            't': evt_name,
            'd': evt_data,
        }
        self._seq += 1
        return (await self.send_json(payload))

    async def get_myself(self):
        return {
            'id': 1,
            'username': 'fucker',
            'discriminator': '6969',
            'avatar': 'fuck',
            'bot': True,
            'mfa_enabled': False,
        }

    async def process_recv(self, payload):
        op = payload.get('op')
        data = payload.get('d')
        if (op is None) or (data is None):
            log.info("Got erroneous data from client")
            self.ws.close(4001)
            return False

        seq = payload.get('s')
        evt = payload.get('t')

        if op == OP['HEARTBEAT']:
            log.debug('[hb] Sending ACK')
            await self.send_op(OP['HEARTBEAT_ACK'], {})
        elif op == OP['IDENTIFY']:
            log.info('[identify] got identify')
            token = data.get('token')
            prop = data.get('properties')
            large = data.get('large_threshold')

            if (token is None) or (prop is None) or (large is None):
                log.warning('Erroneous IDENTIFY')
                self.ws.close(4001)
                return

            self.properties['token'] = token
            self.properties['os'] = prop['$os']
            self.properties['browser'] = prop['$browser']
            self.properties['large'] = large

            self.user = await self.get_myself()
            self.session_id = self.gen_sessid()
            sessions[self.session_id] = self

            log.info("New session %s", self.session_id)

            await self.send_dispatch('READY', {
                'v': GATEWAY_VERSION,
                'user': self.user,
                'private_channels': [],
                'guilds': [],
                'session_id': self.session_id,
            })

        elif op == OP['RESUME']:
            log.warning("We don't suport RESUMEs yet")
            self.ws.close(4001)
            return False

        return True

    async def run(self):
        # send OP HELLO
        log.info("Sending OP HELLO")
        await self.ws.send(json.dumps(self.basic_hello()))

        try:
            while True:
                payload = json.loads(await self.ws.recv())
                continue_processing = await self.process_recv(payload)
                if not continue_processing:
                    log.info("Stopped processing")
                    break
        except:
            print(traceback.format_exc())
            self.ws.close(4000)
            return

        self.ws.close(4000)

async def gateway_server(app):
    async def hello(websocket, path):
        log.info("Got new client, opening connection")
        connection = Connection(websocket, path)
        await connection.run()
        log.info("Stopped connection", exc_info=True)

    log.info("Starting websocket server")
    #app.add_route('/channels/{channel_id}/messages', )
    start_server = websockets.serve(hello, '0.0.0.0', 12000)
    await start_server
    log.info("Finished gateway")
