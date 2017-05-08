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
from .utils import chunk_list, strip_user_data

MAX_TRIES = 10

log = logging.getLogger(__name__)

session_data = {}
token_to_session = {}

valid_tokens = []

class Connection:
    """Represents a websocket connection to litecord

    Attributes:
        ws:
            The actual websocket connection
        last_seq:
            An integer representing the last event the client received.
            See `Connection.heartbeat_handler` for more details.
        token:
            The token this connection is using.
        identified:
            A boolean showing if the client had a successful IDENTIFY or not.
        properties:
            Dictionary with connection properties like OS, browser and the large_threshold.
        user:
            Becomes a raw user object if the connection is properly identified.
    """
    def __init__(self, server, ws, path):
        self.ws = ws
        self.path = path

        # last sequence sent by the server
        self._seq = 0

        # the last event client received, used for resuming
        # TODO: Resuming:
        #  check if the different between last_seq and _seq is higher than 50
        #  if it is, we do session invalidation
        self.last_seq = None

        # some stuff
        self.token = None
        self.identified = False
        self.properties = {}
        self.user = None

        # reference to LitecordServer
        self.server = server

        # reference to PresenceManager
        self.presence = server.presence

        # OP handlers
        self.op_handlers = {
            OP['HEARTBEAT']: self.heartbeat_handler,
            OP['IDENTIFY']: self.identify_handler,
            OP['STATUS_UPDATE']: self.status_handler,

            #OP['RESUME']: self.resume_handler,
            OP['REQUEST_GUILD_MEMBERS']: self.req_guild_handler,

            # Undocumented.
            OP['GUILD_SYNC']: self.guild_sync_handler,
        }

        # Event handlers
        #  Fired when a client sends an OP 0 DISPATCH
        #  NOTE: This is unlikely to happen.
        #   However we should be ready when it happens, right?
        self.event_handlers = {}

    def basic_hello(self):
        """Returns a JSON serializable OP 10 Hello packet."""
        return {
            'op': OP["HELLO"],
            'd': {
                'heartbeat_interval': 20000,
                '_trace': ["litecord-gateway-prd-1-69"],
            }
        }

    def gen_sessid(self):
        """Generate a new Session ID."""
        tries = 0
        new_id = str(uuid.uuid4().fields[-1])
        while new_id in session_data:
            if tries >= MAX_TRIES:
                return None

            new_id = str(uuid.uuid4().fields[-1])
            tries += 1

        return new_id

    async def send_json(self, obj):
        """Send a JSON payload through the websocket.

        Args:
            obj: any JSON serializable object
        """
        res = await self.ws.send(json.dumps(obj))
        return res

    async def send_op(self, op, data={}):
        """Send a packet through the websocket.

        Args:
            op: Integer representing the packet's OP
            data: any JSON serializable object
        """
        payload = {
            # op is always an int
            # data can be a dict, int or bool
            'op': op,
            'd': data,
        }
        return (await self.send_json(payload))

    async def dispatch(self, evt_name, evt_data={}):
        """Send a DISPATCH packet through the websocket.

        Args:
            evt_name: Event name, follows the same pattern as Discord's event names
            evt_data: any JSON serializable object
        """
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
        """Get the raw user that this connection represents."""
        return self.user

    async def heartbeat_handler(self, data):
        """Handle OP 1 Heartbeat packets.

        Saves the last event received by the client in `Connection.last_seq`
        Sends a OP 11 Heartbeat ACK packet

        Args:
            data: An integer or None
        """
        self.last_seq = data
        await self.send_op(OP['HEARTBEAT_ACK'], {})
        return True

    async def identify_handler(self, data):
        """Handle an OP 2 Identify sent by the client.

        Checks if the token given in the packet is valid, and if it is,
        dispatched a READY event.

        Args:
            data: A dictionary, https://discordapp.com/developers/docs/topics/gateway#gateway-identify
        """
        log.info('[identify] identifying connection')

        token = data.get('token')
        prop = data.get('properties')
        large = data.get('large_threshold')

        # check if the client isn't trying to fuck us over
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

        # do the thing with large_threshold
        all_guild_list = [guild for guild in guild_list]
        guild_list = []

        for guild in all_guild_list:
            guild_json = guild.as_json

            if len(guild.members) > large:
                guild_json['members'] = [m.as_json for m in gulid.online_members]

            guild_list.append(guild_json)

        await self.dispatch('READY', {
            'v': GATEWAY_VERSION,
            'user': strip_user_data(self.user),
            'private_channels': [],
            'guilds': guild_list,
            'session_id': self.session_id,
        })

        # only set the user to an online status AFTER we dispatched READY
        await self.presence.status_update(self.user['id'])

        return True

    async def req_guild_handler(self, data):
        """Handle OP 8 Request Guild Members.

        Sends a Guild Members Chunk event(https://discordapp.com/developers/docs/topics/gateway#guild-members-chunk).
        """
        if not self.identified:
            log.warning("Client not identified to do OP 8, closing with 4003")
            await self.ws.close(4003)
            return False

        guild_id = data.get('guild_id')
        query = data.get('query')
        limit = data.get('limit')

        if guild_id is None or query is None or limit is None:
            await self.ws.close(4001)
            return False

        if limit > 1000: limit = 1000
        if limit <= 0: limit = 1000

        all_members = [member.as_json for member in guild.members]
        member_list = []

        # NOTE: this is inneficient
        if len(query) > 0:
            for member in all_members:
                if member.user.username.startswith(query):
                    member_list.append(member)
        else:
            # if no query provided, just give it all
            member_list = all_members

        if len(member_list) > 1000:
            # we split the list into chunks of size 1000
            # and send them all in the event
            for chunk in chunk_list(member_list, 1000):
                await self.dispatch('GUILD_MEMBERS_CHUNK', {
                    'guild_id': guild_id,
                    'members': chunk,
                })
        else:
            await self.dispatch('GUILD_MEMBERS_CHUNK', {
                'guild_id': guild_id,
                'members': chunk,
            })
        return True

    async def resume_handler(self, data):
        """Dummy Handler for OP 6 Resume"""
        if not self.identified:
            log.warning("Client not identified to do OP 6, closing with 4003")
            await self.ws.close(4003)
            return True

        return True

    async def status_handler(self, data):
        """Handle OP 3 Status Update packets

        Checks the payload format and if it is OK, calls `PresenceManager.status_update`
        """

        if not self.identified:
            log.error("Client not identified to do OP 3, closing with 4003")
            await self.ws.close(4003)
            return False

        idle_since = data.get('idle_since', 'nothing')
        game = data.get('game')
        if game is not None:
            game_name = game.get('name')
            if game_name is not None:
                await self.presence.status_update(self.user['id'], {
                    'name': game_name,
                })
            return True

        return False

    async def guild_sync_handler(self, data):
        """Handle OP 12 Guild Sync packets

        This is an undocumented OP on Discord's API docs.
        This OP is sent by the client to request member and presence information.
        """

        if not self.identified:
            log.error("Client not identified to do OP 12, closing with 4003")
            await self.ws.close(4003)
            return False

        if not isinstance(data, list):
            log.error('[guild_sync] client didn\'t send a list')
            await self.ws.close(4001)
            return False

        # ASSUMPTION: data is a list of guild IDs
        for guild_id in data:
            guild = self.guilds.get_guild(guild_id)

            await self.dispatch('GUILD_SYNC', {
                'id': guild_id,
                'presences': [self.presence.get_presence(member.id) for member in guild.online_members],
                'members': [member.as_json for member in guild.online_members],
            })

        return True

    async def process_recv(self, payload):
        """Process a payload sent by the client.

        The client has to send a payload in this format:
        https://discordapp.com/developers/docs/topics/gateway#gateway-op-codespayloads
        """

        op = payload.get('op')
        data = payload.get('d')
        if op not in self.op_handlers:
            log.info("opcode not found, closing with 4001")
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

        handler = self.op_handlers[op]
        return (await handler(data))


    async def run(self):
        """Starts basic handshake with the client

        This only starts when the websocket server notices a new client.
        The server sends an OP 10 Hello packet to the client, and after that
        it relays payloads sent by the client to `Connection.process_recv`
        """
        # send OP HELLO
        log.info("Sending OP HELLO")
        await self.ws.send(json.dumps(self.basic_hello()))

        try:
            while True:
                received = await self.ws.recv()
                if len(received) > 4096:
                    await self.ws.close(4002)
                    self.cleanup()
                    break

                try:
                    payload = json.loads(received)
                except:
                    await self.ws.close(4002)
                    self.cleanup()
                    break

                continue_flag = await self.process_recv(payload)

                # if process_recv tells us to stop, we clean everything
                # process_recv will very probably close the websocket already
                if not continue_flag:
                    log.info("Stopped processing")
                    self.cleanup()
                    break
        except Exception as err:
            # if any error we just close with 4000
            log.error('Error while running the connection', exc_info=True)
            await self.ws.close(4000, f'Unknown error: {err!r}')
            self.cleanup()
            return

        await self.ws.close(1000)

    def cleanup(self):
        """Remove the connection from being found

        The cleanup only happens if the connection is identified.
        This method can only be called once.
        """
        if self.token is not None:
            token_to_session.pop(self.token)
            valid_tokens.remove(self.token)
            session_data.pop(self.session_id)
            self.token = None


async def gateway_server(app, databases):
    """Main function to start the websocket server

    This function initializes a LitecordServer object, which
    initializes databases, fills caches, etc.

    When running, for each new client, a `Connection` object is created to represent it,
    its `.run()` method is called and the connection will live forever until it gets closed.

    This function registers the `/api/auth/login` route.

    Args:
        databases: A dictionary with database path data.
            Example:
            ```
            {
                'users': 'db/users.json',
                'guilds': 'db/guilds.json',
                'messages': 'db/messages.json',
                'tokens': 'db/tokens.json',
            }
            ```
    """
    server = LitecordServer(valid_tokens, token_to_session, session_data)

    server.db_paths = databases
    if not server.init(app):
        log.error("We had an error initializing the Litecord Server.")
        sys.exit(1)

    async def henlo(websocket, path):
        log.info("Got new client, opening connection")
        conn = Connection(server, websocket, path)
        await conn.run()
        log.info("Stopped connection", exc_info=True)

        # do cleanup shit!!
        conn.cleanup()

    app.router.add_post('/api/auth/login', server.login)

    # start WS
    log.info("Starting WS")
    start_server = websockets.serve(henlo, '0.0.0.0', 12000)
    await start_server
