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

        # sequence stuff
        self._seq = 0

        # the last event client received, used for resuming
        # TODO: Resuming:
        #  check if the different between last_seq and _seq is higher than 50
        #  if it is, we do session invalidation
        self.last_seq = None

        # token the connection is using
        self.token = None

        # flag that says if the connection is a good connection and it is identified
        self.identified = False

        # connection properties
        self.properties = {}

        # the user the connection currently represents
        self.user = None

        # reference to LitecordServer
        self.server = server
        self.presence = server.presence

        # OP handlers
        self.op_handlers = {
            OP['HEARTBEAT']: self.heartbeat_handler,
            OP['IDENTIFY']: self.identify_handler,
            OP['REQUEST_GUILD_MEMBERS']: self.req_guild_handler,
            OP['STATUS_UPDATE']: self.status_handler,
        }

        # Event handlers
        #  Fired when a client sends an OP 0 DISPATCH
        self.event_handlers = {}

    def basic_hello(self):
        '''Returns a valid OP 10 Hello packet'''
        return {
            'op': OP["HELLO"],
            'd': {
                'heartbeat_interval': 20000,
                '_trace': [],
            }
        }

    def gen_sessid(self):
        '''Generate a Session ID for a new connection'''
        tries = 0
        new_id = str(uuid.uuid4().fields[-1])
        while new_id in session_data:
            if tries >= MAX_TRIES:
                return None

            new_id = str(uuid.uuid4().fields[-1])
            tries += 1

        return new_id

    async def send_json(self, obj):
        '''Send a JSON object through the websocket connection'''
        res = await self.ws.send(json.dumps(obj))
        return res

    async def send_op(self, op, data={}):
        '''Send an arbritary OP through the websocket connection'''
        payload = {
            # op is always an int
            # data can be a dict, int or bool
            'op': op,
            'd': data,
        }
        return (await self.send_json(payload))

    async def dispatch(self, evt_name, evt_data={}):
        '''Send a DISPATCH packet through the websocket connection'''
        payload = {
            'op': OP["DISPATCH"],

            # always an int
            's': self._seq,
            # always a str
            't': evt_name,

            'd': evt_data,
        }
        self._seq += 1
        return (await self.send_json(payload))

    async def get_myself(self):
        return self.user

    async def heartbeat_handler(self, data):
        '''
        Connection.heartbeat_handler(data)

        Handles HEARTBEAT packets, sends a OP 11 Heartbeat ACK
        '''
        self.last_seq = data
        await self.send_op(OP['HEARTBEAT_ACK'], {})
        return True

    async def identify_handler(self, data):
        '''
        Connection.identify_handler(data)

        Handle an OP 2 Identify from a client.
        It checks the token given by the client, and if it is valid,
        the server creates the session and dispatches a READY event to the client.
        '''
        log.info('[identify] got identify')

        token = data.get('token')
        prop = data.get('properties')
        large = data.get('large_threshold')

        # sanity test
        if (token is None) or (prop is None) or (large is None):
            log.warning('Erroneous IDENTIFY')
            await self.ws.close(4001)
            return

        # get DB objects
        db_tokens = self.server.db['tokens']
        db_users = self.server.db['users']

        if token not in db_tokens:
            log.warning('Invalid token, closing with 4004')
            await self.ws.close(4004, 'Authentication failed..')
            return

        user_object = None
        token_user_id = db_tokens[token]

        # check if the token is valid
        for user_email in db_users:
            user_id = db_users[user_email]['id']
            if token_user_id == user_id:
                # We found a valid token
                user_object = db_users[user_email]

        if user_object is None:
            log.warning('No users related to that token')
            await self.ws.close(4004, 'Authentication failed..')
            return

        self.user = user_object
        self.session_id = self.gen_sessid()
        self.token = token

        try:
            valid_tokens.index(self.token)
        except:
            valid_tokens.append(self.token)

        # lol properties
        self.properties['token'] = self.token
        self.properties['os'] = prop.get('$os')
        self.properties['browser'] = prop.get('$browser')
        self.properties['large'] = large

        session_data[self.session_id] = self
        token_to_session[self.token] = self.session_id

        # set identified to true so we know this connection is 👌 good 👌
        self.identified = True
        guild_list = self.server.guild_man.get_guilds(self.user['id'])

        log.info("New session %s", self.session_id)

        # self.presence.update_presence(PRESENCE.online)
        await self.presence.status_update(self.user['id'], 'meme')
        await self.dispatch('READY', {
            'v': GATEWAY_VERSION,
            'user': self.user,
            'private_channels': [],
            'guilds': [guild.as_json for guild in guild_list],
            'session_id': self.session_id,
        })

        return True

    async def req_guild_handler(self, data):
        '''
        Connection.req_guild_handler(data)

        Dummy handler for OP 8 Request Guild Members
        '''
        guild_id = data.get('guild_id')
        query = data.get('query')
        limit = data.get('limit')
        if guild_id is None or query is None or limit is None:
            await self.ws.close(4001)
            return False

        await self.dispatch('GUILD_MEMBERS_CHUNK', {
            'guild_id': guild_id,
            #'members': await self.presence.offline_members(guild_id),
            'members': [],
        })

    async def process_recv(self, payload):
        '''
        Connection.process_recv(payload)

        Process a payload received by the client.
        The format for payloads in the websocket goes as follows
        ```
        {
            "op": op number,
            "d": data for that op,
            "s": sequence number, //optional
            "t": event name, //optional
        }
        ```
        '''

        # first, we get data we actually need
        op = payload.get('op')
        data = payload.get('d', 'NO_DATA')
        if (op is None) or (data == 'NO_DATA'):
            log.info("Got erroneous data from client, closing with 4001")
            await self.ws.close(4001)
            return False

        sequence_number = payload.get('s')
        event_name = payload.get('t')

        if op == OP['DISPATCH']:
            # wooo, we got a DISPATCH
            if event_name in self.event_handlers:
                evt_handler = self.event_handlers[op]
                return (await evt_handler(data, sequence_number, event_name))
            else:
                # don't even try to check in op_handlers.
                return True

        if op in self.op_handlers:
            handler = self.op_handlers[op]
            return (await handler(data))

        # if the op is non existant, we just ignore
        return True

    async def status_handler(self, data):
        '''
        Connection.status_handler(data)

        Handles OP 3 Status Update packets
        '''

        idle_since = data.get('idle_since', 'nothing')
        game = data.get('game')
        if game is not None:
            game_name = game.get('name')
            if game_name is not None:
                await self.presence.status_update(self.user['id'], game_name)
                return True

    async def run(self):
        '''
        Connection.run()

        Runs the websocket and sends messages
        to be processed by `Connection.process_recv`
        '''
        # send OP HELLO
        log.info("Sending OP HELLO")
        await self.ws.send(json.dumps(self.basic_hello()))

        try:
            while True:
                # receive something from WS
                payload = json.loads(await self.ws.recv())

                # process it
                continue_flag = await self.process_recv(payload)

                # if process_recv tells us to stop, we clean everything
                if not continue_flag:
                    log.info("Stopped processing")

                    if self.token is not None:
                        token_to_session.pop(self.token)
                        valid_tokens.remove(self.token)
                        session_data.pop(self.session_id)

                    break
        except Exception as err:
            # if any error we just close with 4000
            log.error('Error at run()', exc_info=True)
            await self.ws.close(4000, 'Unexpected error')
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
    app.router.add_get('/api/users/{user_id}', server.users_endpoint.h_users)

    app.router.add_post('/api/users/add', server.users_endpoint.h_add_user)
    app.router.add_patch('/api/users/@me', server.users_endpoint.h_patch_me)

    #app.router.add_get('/api/users/@me/guilds', server.h_users_me_guild)
    #app.router.add_delete('/api/users/@me/guilds/{guild_id}', server.h_users_guild_delete)

    # start WS
    log.info("Starting WS")
    start_server = websockets.serve(henlo, '0.0.0.0', 12000)
    await start_server
