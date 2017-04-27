import json
import websockets
import logging
import asyncio
import uuid
import traceback
import json
import sys

from .basics import OP, GATEWAY_VERSION
from .server import LitecordServer

MAX_TRIES = 10

log = logging.getLogger(__name__)

session_data = {}
token_to_session = {}

valid_tokens = []

class Connection:
    def __init__(self, server, ws, path):
        self.ws = ws
        self.path = path
        self._seq = 0

        self.token = None
        self.identified = False

        self.properties = {}
        self.user = None
        self.server = server

    def basic_hello(self):
        return {
            'op': OP["HELLO"],
            'd': {
                'heartbeat_interval': 20000,
                '_trace': [],
            }
        }

    def gen_sessid(self):
        tries = 0
        new_id = str(uuid.uuid4().fields[-1])
        while new_id in session_data:
            if tries >= MAX_TRIES:
                return None

            new_id = str(uuid.uuid4().fields[-1])
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
        return self.user

    async def process_recv(self, payload):
        op = payload.get('op')
        data = payload.get('d')
        if (op is None) or (data is None):
            log.info("Got erroneous data from client")
            await self.ws.close(4001)
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
                await self.ws.close(4001)
                return

            db_tokens = self.server.db['tokens']
            db_users = self.server.db['users']

            if token not in db_tokens:
                log.warning('Invalid token, closing with 4004')
                await self.ws.close(4004, 'Authentication failed..')
                return

            user_object = None
            token_user_id = db_tokens[token]

            for user_email in db_users:
                user_id = db_users[user_email]['id']
                if token_user_id == user_id:
                    # We found a valid token
                    user_object = db_users[user_email]

            self.user = user_object
            self.session_id = self.gen_sessid()
            self.token = token

            try:
                valid_tokens.index(self.token)
            except:
                valid_tokens.append(self.token)

            self.properties['token'] = token
            self.properties['os'] = prop['$os']
            self.properties['browser'] = prop['$browser']
            self.properties['large'] = large

            session_data[self.session_id] = self
            token_to_session[self.token] = self.session_id

            self.identified = True
            guild_list = await self.server.guild_man.get_guilds(self.user['id'])

            log.info("New session %s", self.session_id)

            await self.send_dispatch('READY', {
                'v': GATEWAY_VERSION,
                'user': self.user,
                'private_channels': [],
                'guilds': guild_list,
                'session_id': self.session_id,
            })

        elif op == OP['RESUME']:
            await self.ws.close(4001, 'Resuming not implemented')
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

                    if self.token is not None:
                        token_to_session.pop(self.token)
                        valid_tokens.remove(self.token)
                        session_data.pop(self.session_id)

                    break
        except Exception as err:
            log.error('Error at run()', exc_info=True)
            await self.ws.close(4000)
            return

        await self.ws.close(4000)

async def gateway_server(app, databases):
    server = LitecordServer(valid_tokens, token_to_session, session_data)

    server.db_paths = databases
    if not server.init():
        log.error("We had an error initializing the Litecord Server.")
        sys.exit(1)

    async def henlo(websocket, path):
        log.info("Got new client, opening connection")
        connection = Connection(server, websocket, path)
        await connection.run()
        log.info("Stopped connection", exc_info=True)

    #app.add_route('/api/channels', self.channel_handler)
    app.router.add_post('/api/auth/login', server.login)
    app.router.add_get('/api/users/{user_id}', server.h_users)

    app.router.add_post('/api/users/add', server.h_add_user)
    app.router.add_patch('/api/users/@me', server.h_patch_me)

    #app.router.add_get('/api/users/@me/guilds', server.h_users_me_guild)
    #app.router.add_delete('/api/users/@me/guilds/{guild_id}', server.h_users_guild_delete)

    # start WS
    log.info("Starting WS")
    start_server = websockets.serve(henlo, '0.0.0.0', 12000)
    await start_server
