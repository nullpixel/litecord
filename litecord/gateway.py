import json
import websockets
import logging
import asyncio
import uuid
import json
import sys
import pprint
import random
import zlib

from .basics import OP, GATEWAY_VERSION
from .server import LitecordServer
from .utils import chunk_list, strip_user_data

MAX_TRIES = 10
HB_MIN_MSEC = 4000
HB_MAX_MSEC = 6000

log = logging.getLogger(__name__)

class Connection:
    """Represents a websocket connection to Litecord.

    Attributes:
        ws:
            The actual websocket connection.
        events:
            If the connection is identified, this becomes a reference to
            `LitecordServer.event_cache[connection.user.id]`.
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

        # Last sequence sent by the client and last sequence received by the client
        # will be here
        self.events = None
        self.hb_interval = random.randint(HB_MIN_MSEC, HB_MAX_MSEC)
        self.wait_task = None

        # some stuff
        self.token = None
        self.session_id = None
        self.compress_flag = False
        self.properties = {}

        # flags
        self.identified = False
        self.resume_count = 0
        # TODO: self.replay_lock = asyncio.Lock()

        # user objects
        self.user = None
        self.raw_user = None

        # reference to LitecordServer
        self.server = server

        # reference to PresenceManager
        self.presence = server.presence

        # OP handlers
        self.op_handlers = {
            OP['HEARTBEAT']: self.heartbeat_handler,
            OP['IDENTIFY']: self.identify_handler,
            OP['STATUS_UPDATE']: self.status_handler,

            OP['RESUME']: self.resume_handler,
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
                'heartbeat_interval': self.hb_interval,
                '_trace': ["litecord-gateway-prd-1-69"],
            }
        }

    def gen_sessid(self):
        """Generate a new Session ID."""
        tries = 0
        new_id = str(uuid.uuid4().fields[-1])
        while new_id in self.server.sessions:
            if tries >= MAX_TRIES:
                return None

            new_id = str(uuid.uuid4().fields[-1])
            tries += 1

        return new_id

    async def send_anything(self, obj):
        """Send anything through the websocket."""

        return (await self.ws.send(obj))

    async def send_json(self, obj):
        """Send a JSON payload through the websocket.

        Args:
            obj: any JSON serializable object
        """
        return (await self.send_anything(json.dumps(obj)))

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

        Saves the packet in the `LitecordServer`'s event cache.

        Args:
            evt_name: Event name, follows the same pattern as Discord's event names
            evt_data: any JSON serializable object
        """
        try:
            sent_seq = self.events['sent_seq']
        except:
            log.warning("[dispatch] can't dispatch event to unidentified connection")
            return

        sent_seq += 1

        payload = {
            'op': OP["DISPATCH"],

            # always an int
            's': sent_seq,

            # always a str
            't': evt_name,
            'd': evt_data,
        }

        to_send = json.dumps(payload)

        if evt_name == 'READY':
            if self.compress_flag:
                to_send = zlib.compress(json.dumps(payload).encode())
            log.info(f"READY: Dispatching {len(str(to_send))} bytes, compress={self.compress_flag}")

        res = await self.send_anything(to_send)
        self.events['events'][sent_seq] = payload
        self.events['sent_seq'] = sent_seq

        return res

    async def get_myself(self):
        """Get the raw user that this connection represents."""
        return self.raw_user

    async def hb_wait_task(self):
        try:
            await asyncio.sleep((self.hb_interval) / 1000)
            await asyncio.sleep(3)
            log.info("Closing client for lack of heartbeats")
            await self.ws.close(4000)
        except asyncio.CancelledError:
            log.debug("[hb_wait_task] Cancelled")
            pass

    async def heartbeat_handler(self, data):
        """Handle OP 1 Heartbeat packets.

        Saves the last sequence number received by the
        client in `Connection.events['recv_seq']`.
        Sends a OP 11 Heartbeat ACK packet.

        Args:
            data: An integer or None.
        """
        try:
            self.wait_task.cancel()
        except:
            pass

        try:
            self.events['recv_seq'] = data
        except:
            log.warning("Received OP 1 Heartbeat from unidentified connection")

        await self.send_op(OP['HEARTBEAT_ACK'], {})
        self.wait_task = self.server.loop.create_task(self.hb_wait_task())
        return True

    async def check_token(self, token):
        token_user_id = await self.server.token_find(token)
        if token_user_id is None:
            log.warning("Token not found")
            return False, None, None

        raw_user = self.server.get_raw_user(token_user_id)
        if raw_user is None:
            log.warning("(token, user) pair not found")
            return False, None, None

        user = self.server.get_user(raw_user['id'])
        return True, raw_user, user

    async def identify_handler(self, data):
        """Handle an OP 2 Identify sent by the client.

        Checks if the token given in the packet is valid, and if it is,
        dispatched a READY event.

        Args:
            data: A dictionary, https://discordapp.com/developers/docs/topics/gateway#gateway-identify
        """
        token = data.get('token')
        prop = data.get('properties')
        large = data.get('large_threshold')
        self.compress_flag = data.get('compress', False)

        # check if the client isn't trying to fuck us over
        if (token is None) or (prop is None) or (large is None):
            log.warning('Erroneous IDENTIFY')
            await self.ws.close(4001)
            return

        valid, user_object, user = await self.check_token(token)
        if not valid:
            await self.ws.close(4004, 'Authentication failed...')
            return False

        self.raw_user = user_object
        self.user = user

        self.session_id = self.gen_sessid()
        self.token = token

        try:
            self.server.valid_tokens.index(self.token)
        except:
            self.server.valid_tokens.append(self.token)

        # lol properties
        _prop = self.properties
        _prop['token'] = self.token
        _prop['os'] = prop.get('$os')
        _prop['browser'] = prop.get('$browser')
        _prop['large'] = large

        self.server.sessions[self.session_id] = self
        self.server.session_dict[self.token] = self.session_id

        if self.session_id not in self.server.event_cache:
            self.server.event_cache[self.session_id] = {
                'sent_seq': 0,
                'recv_seq': 0,
                'events': {},
            }

        self.events = self.server.event_cache[self.session_id]

        # set user status before even calculating guild data to be sent
        # if we do it *after* READY, the presence manager errors since it tries
        # to get presence stuff for a member that is still connecting
        await self.presence.global_update(self.user)

        # set identified to true so we know this connection is 👌 good 👌
        self.identified = True

        all_guild_list = self.server.guild_man.get_guilds(self.user.id)

        # the actual list of guilds to be sent to the client
        guild_list = []

        for guild in all_guild_list:
            guild_json = guild.as_json

            if guild.member_count > large:
                guild_json['members'] = [m.as_json for m in gulid.online_members]

            guild_list.append(guild_json)

        stripped_user = strip_user_data(self.raw_user)

        log.info("New session %s, sending %d guilds", self.session_id, len(guild_list))

        await self.dispatch('READY', {
            'v': GATEWAY_VERSION,
            'user': stripped_user,
            'private_channels': [],
            'guilds': guild_list,
            'session_id': self.session_id,
        })

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

    async def invalidate(self, flag=False, session_id=None):
        log.info(f"Invalidated, can resume: {flag}")
        await self.send_op(OP['INVALID_SESSION'], flag)
        if not flag:
            try:
                self.server.event_cache.pop(self.session_id or session_id)
                await self.ws.close(4001)
            except:
                pass

    async def resume_handler(self, data):
        """Handler for OP 6 Resume.

        TODO: fix this implementaiton.
        """

        log.info("[resume] Resuming a connection...")

        self.resume_count += 1
        if self.resume_count > 3:
            await self.ws.close(4001)
            return

        # get shit client sends
        token = data.get('token')
        session_id = data.get('session_id')
        replay_seq = data.get('seq')

        if replay_seq is None or session_id is None or token is None:
            await self.ws.close(4001)
            return False

        if session_id not in self.server.event_cache:
            log.warning("[resume] invalidated from session_id")
            await self.invalidate(True)
            return True

        event_data = self.server.event_cache[session_id]

        valid, raw_user, user = await self.check_token(token)
        if not valid:
            log.warning("[resume] invalidated @ check_token")
            await self.invalidate(session_id=session_id)
            return False

        # man how can i resume from the future
        sent_seq = event_data['sent_seq']

        if replay_seq > sent_seq:
            log.warning(f"[resume] invalidated from replay_seq > sent_set {replay_seq} {sent_seq}")
            await self.invalidate(True)
            return True

        # if the client loses more than 20 events while its offline,
        # invalidate it.
        if abs(replay_seq - sent_seq) > 20:
            log.warning("[resume] invalidated from seq delta")
            await self.invalidate(False, session_id=session_id)
            return

        seqs_to_replay = range(replay_seq, sent_seq + 1)
        log.info(f"Replaying {len(seqs_to_replay)} events to {user!r}")

        for seq in seqs_to_replay:
            try:
                await self.send_json(event_data['events'][seq])
            except KeyError:
                log.info(f"Event {seq} not found")

        self.raw_user = raw_user
        self.user = user

        self.token = token
        self.session_id = session_id

        if self.session_id not in self.server.event_cache:
            self.server.event_cache[self.session_id] = {
                'sent_seq': 0,
                'recv_seq': 0,
                'events': {},
            }

        self.events = self.server.event_cache[self.session_id]

        self.identified = True

        await self.dispatch('RESUMED', {
            '_trace': ['litecord-gateway-prd-1-666']
        })

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
                await self.presence.global_update(self.user, {
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
                'presences': [self.presence.get_presence(guild_id, member.id) \
                    for member in guild.online_members],
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
        except websockets.ConnectionClosed as err:
            # signal clients that this one is offline
            log.info(f"[ws] closed, code {err.code!r}")
            self.cleanup()
            await self.presence.global_update(self.user, self.presence.offline())
        except Exception as err:
            # if any error we just close with 4000
            log.error('Error while running the connection', exc_info=True)
            await self.ws.close(4000, f'Unknown error: {err!r}')
            self.cleanup()
            return

        await self.ws.close(1000)

    def cleanup(self):
        """Remove the connection from being found

        The cleanup only happens if the connection is open and identified.
        This method can only be called once in a connection.
        """

        self.identified = False
        try:
            self.hb_wait_task.cancel()
        except:
            pass

        if self.ws.open:
            log.warning("Cleaning up a connection while it is open")

        if self.token is not None:
            log.debug(f'cleaning up session ID {self.session_id!r}')
            try:
                self.server.session_dict.pop(self.token)
                self.server.valid_tokens.remove(self.token)
                self.server.sessions.pop(self.session_id)
            except:
                log.warning("Error while cleaning up the connection.")
            self.token = None


_load_lock = asyncio.Lock()

# Modification of
# https://github.com/Rapptz/discord.py/blob/bed2e90e825f9cf90fc1ecbae3f49472de05ad3c/discord/client.py#L520
def _stop(loop):
    pending = asyncio.Task.all_tasks(loop=loop)
    gathered = asyncio.gather(*pending, loop=loop)
    try:
        gathered.cancel()
        loop.run_until_complete(gathered)
        gathered.exception()
    except:
        pass

async def http_server(app, flags):
    """Main function to start the HTTP server.

    This function waits for `gateway_server` to finish(using locks).

    That is needed since `gateway_server` initializes server state and registers
    all API routes, and in aiohttp, you need to register
    routes **before** the app starts.
    """
    await _load_lock.acquire()
    http = flags['server']['http']

    log.info(f'[http] starting at {http[0]}:{http[1]}')

    handler = app.make_handler()
    f = app.loop.create_server(handler, http[0], http[1])
    await f

async def gateway_server(app, flags, loop=None):
    """Main function to start the websocket server

    This function initializes a LitecordServer object, which
    initializes databases, fills caches, etc.

    When running, for each new websocket client, a `Connection` object is
    created to represent it, its `.run()` method is called and the
    connection will stay alive forever until it gets closed or the client
    stops heartbeating with us.
    """
    await _load_lock.acquire()

    if loop is None:
        loop = asyncio.get_event_loop()

    try:
        server = LitecordServer(flags, loop)
    except:
        log.error("We had an error loading the litecord server")
        _stop(loop)
        return

    if not (await server.init(app)):
        log.error("We had an error initializing the Litecord Server.")
        _stop(loop)
        return

    async def henlo(websocket, path):
        log.info("Opening connection")
        conn = Connection(server, websocket, path)
        await conn.run()
        log.info("Stopped connection", exc_info=True)

        # do cleanup shit!!
        conn.cleanup()

    # start WS
    _load_lock.release()
    ws = flags['server']['ws']
    log.info(f'[ws] running at {ws[0]}:{ws[1]}')

    ws_server = websockets.serve(henlo, host=ws[0], port=ws[1])
    await ws_server
    return True
