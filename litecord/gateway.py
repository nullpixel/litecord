"""
gateway.py - Manages a websocket connection

    This file is considered one of the most important, since it loads
    LitecordServer and tells it to initialize the databases.
"""
import logging
import asyncio
import uuid
import random
import hashlib
import collections
import urllib.parse as urlparse

import websockets

from voluptuous import Schema, Optional, REMOVE_EXTRA

from .basics import GATEWAY_VERSION
from .enums import OP
from .server import LitecordServer
from .utils import chunk_list
from .err import VoiceError
from .ratelimits import ws_ratelimit

from .ws import WebsocketConnection, handler, StopConnection, get_data_handlers

# Maximum amount of tries to generate a session ID.
MAX_TRIES = 20

# Heartbeating intervals, actual heartbeating interval is random value
# between HB_MIN_MSEC and HB_MAX_MSEC
HB_MIN_MSEC = 40000
HB_MAX_MSEC = 42000

# The maximum amount of events you can lose before your session gets invalidated.
RESUME_MAX_EVENTS = 60

log = logging.getLogger(__name__)

SERVERS = {
    'hello': [f'litecord-hello-{random.randint(1, 99)}'],
    'ready': [f'litecord-session-{random.randint(1, 99)}'],
    'resume': [f'litecord-resumer{random.randint(1, 99)}'],
}


def random_sid():
    """Generate a new random Session ID."""
    return hashlib.md5(str(uuid.uuid4().fields[-1]).encode()).hexdigest()


class Connection(WebsocketConnection):
    """Represents a websocket connection to Litecord.

    .. _the documentation about it here: https://discordapp.com/developers/docs/topics/gateway
    .. _WebSocketServerProtocol: https://websockets.readthedocs.io/en/stable/api.html#websockets.server.WebSocketServerProtocol

    This connection only handles A mix of Discord's gateway version 5 and 6,
    it adheres with the docs which are v5, but handles some stuff from v6(see :py:meth:`Connection.guild_sync_handler`)
    you can find `the documentation about it here`_.

    Attributes
    ----------
    ws: `WebSocketServerProtocol`_
        The actual websocket connection.
    options: dict
        Websocket options, encoding, gateway version.

    encoder: function
        Encoder function that convers objects to the provided encoding over :attr:`Connection.options`
    decoder: function
        Decoder function that converts messages from the websocket to objects.

    events: dict
        If the connection is identified, this becomes a reference to
        `LitecordServer.event_cache[connection.user.id]`.
    hb_interval: int
        Amount, in milliseconds, of the client's heartbeat period.
    wait_task: `asyncio.Task` or None
        Check :meth:`Connection.hb_wait_task` for more details.
    token: str or None
        The token this connection is using.
    session_id: str or None
        The session ID this connection is using.
    identified: bool
        Connection had a successful `IDENTIFY` or not.
    properties: dict
        Connection properties like OS, browser and the large_threshold.
    ratelimit_tasks: dict
        Tasks that clean the specified ratelimit bucket in a period of time.
    request_counter: dict
        A request counter for ratelimit buckets.
    
    user: :class:`User`
        Becomes a user object if the connection is properly identified.

    """
    def __init__(self, ws, **kwargs):
        super().__init__(ws)
        self.ws = ws
        self.loop = ws.loop
        self.options = kwargs['config']
        self.server = kwargs['server']

        self._encoder, self._decoder = get_data_handlers(self.options[1])

        # Last sequence sent by the client, last sequence received by it, and a registry of dispatched events are here
        self.events = None

        # Client's heartbeat interval, chose at random between 40 and 42sec
        self.hb_interval = random.randint(HB_MIN_MSEC, HB_MAX_MSEC)
        self.wait_task = None

        # Things that properly identify the client
        self.session_id = None
        self.token = None
        self.session_id = None
        self.compress_flag = False
        self.properties = {}

        # ratelimiting tasks that clean the request counter
        self.ratelimit_tasks = {}
        self.request_counter = {} 

        # some flags for the client etc
        self.identified = False
        self.dispatch_lock = asyncio.Lock()

        # user objects, filled oncce the client is identified
        self.user = None

        # references to objects
        self.guild_man = self.server.guild_man
        self.presence = self.server.presence
        self.relations = self.server.relations
        self.settings = self.server.settings

        # identify schema
        _o = Optional
        self.identify_schema = Schema({
            'token': str,
            'properties': dict,
            _o('compress'): bool,
            'large_threshold': int,
            'shard': list,
        }, extra=REMOVE_EXTRA)

    def __repr__(self):
        if getattr(self, 'session_id', None) is None:
            return f'Connection()'
        return f'Connection(sid={self.session_id} u={self.user!r})'

    def get_identifiers(self, module):
        return SERVERS.get(module, ['litecord-general-1'])

    def basic_hello(self) -> dict:
        """Returns a JSON serializable OP 10 Hello packet."""
        return {
            'op': OP.HELLO,
            'd': {
                'heartbeat_interval': self.hb_interval,
                '_trace': self.get_identifiers('hello'),
            }
        }

    def gen_sessid(self) -> str:
        """Generate a new Session ID.
        
        Tries to generate available session ids, if it reaches MAX_TRIES, returns `None`.
        """
        tries = 0

        new_id = random_sid()
        while new_id in self.server.sessions:
            if tries >= MAX_TRIES:
                return None

            new_id = random_sid()
            tries += 1

        return new_id
    
    def _register_payload(self, sent_seq, payload):
        """Register a sent payload.
        
        Ignores certain kinds of payloads and events
        """
        self.events['sent_seq'] = sent_seq

        op = payload['op']
        if op not in (OP.DISPATCH, OP.STATUS_UPDATE):
            return

        t = payload.get('t')
        if t in ('READY', 'RESUMED'):
            return

        self.events['events'][sent_seq] = payload

    async def dispatch(self, evt_name, evt_data=None):
        """Send a DISPATCH packet through the websocket.

        Saves the packet in the `LitecordServer`'s event cache(:meth:`LitecordServer.events`).

        Parameters
        ----------
        evt_name: str
            Follows the same pattern as Discord's event names.
        evt_data: any
            Any JSON serializable object.
            If this has an `as_json` property, it gets called.
        """

        await self.dispatch_lock

        if evt_data is None:
            evt_data = {}

        if hasattr(evt_data, 'as_json'):
            evt_data = evt_data.as_json

        try:
            sent_seq = self.events['sent_seq']
        except TypeError:
            log.warning("[dispatch] can't dispatch event to unidentified connection")
            self.dispatch_lock.release()
            return -1

        sent_seq += 1

        payload = {
            'op': OP.DISPATCH,
            's': sent_seq,
            't': evt_name,
            'd': evt_data,
        }

        amount = None

        # dude fuck discord.js (2)
        # This compress_flag is required to be used only on READY
        # because d.js is weird with its compression and ETF at the same time.
        if evt_name == 'READY':
            amount = await self.send(payload, compress=self.compress_flag)
        else:
            amount = await self.send(payload)

        log.info(f'[dispatch] {evt_name}, {amount} bytes, compress: {self.compress_flag}')
        self._register_payload(sent_seq, payload)

        self.dispatch_lock.release()
        return amount

    @property
    def is_atomic(self):
        """Returns boolean."""
        return self.server.atomic_markers.get(self.session_id, False)

    async def hb_wait_task(self):
        """This task automatically closes clients that didn't heartbeat in time."""
        try:
            log.debug(f'Waiting for heartbeat {(self.hb_interval / 1000) + 3}s')
            await asyncio.sleep((self.hb_interval / 1000) + 3)
            log.info(f'Heartbeat expired for sid=%s', self.session_id)
            #raise StopConnection(4000, 'Heartbeat expired')
            await self.ws.close(4000, 'Heartbeat expired')
        except asyncio.CancelledError:
            log.debug("[heartbeat_wait] cancelled")

    @handler(OP.HEARTBEAT)
    async def heartbeat_handler(self, data):
        """Handle OP 1 Heartbeat packets.
        Sends a OP 11 Heartbeat ACK packet.

        Parameters
        ----------
        data: int or :py:const:`None`
            Sequence number to be saved in ``Connection.events['recv_seq']``
        """
        try:
            self.wait_task.cancel()
        except AttributeError: pass

        try:
            self.events['recv_seq'] = data
        except AttributeError: pass

        self.wait_task = self.loop.create_task(self.hb_wait_task())
        await self.send_op(OP.HEARTBEAT_ACK, {})

    async def check_token(self, token: str) -> tuple:
        """Check if a token is valid and can be used for proper authentication.
        
        Returns
        -------
        tuple
            with 3 items:
            - A boolean describing the success of the operation,
            - A :class:`User` object(:py:meth:`None` if operation failed).
        """
        token_user_id = await self.server.token_find(token)
        if token_user_id is None:
            log.warning("Token not found")
            return

        user = self.server.get_user(token_user_id)
        if user is None:
            log.warning('User not found')
            return

        return user

    def check_shard(self, shard):
        """Checks the validity of the shard payload.
        
        Raises
        ------
        StopConnection
            With error code 4001 and a reason for the error.
        """

        try:
            shard = list(map(int, shard))
        except ValueError:
            raise StopConnection(4010, 'Invalid shard payload(int).')

        if len(shard) != 2:
            raise StopConnection(4010, 'Invalid shard payload(length).')

        shard_id, shard_count = shard
        if shard_count < 1:
            raise StopConnection(4010, 'Invalid shard payload(shard_count=0).')

        if shard_id > shard_count:
            raise StopConnection(4010, 'Invalid shard payload(id > count).')

    @handler(OP.IDENTIFY)
    @ws_ratelimit('identify')
    async def identify_handler(self, data):
        """Handle an OP 2 Identify sent by the client.

        Checks if the token given in the packet is valid, and if it is,
        dispatched a READY event.

        Information on the input payload is at:
        https://discordapp.com/developers/docs/topics/gateway#gateway-identify
        """
        if self.identified:
            await self.ws.close(4005, 'Already authenticated')
            return

        try:
            data = self.identify_schema(data)
        except Exception as err:
            log.warning(f'Erroneous IDENTIFY: {err!r}')
            raise StopConnection(4001, f'Erroneous IDENTIFY: {err!r}')

        token, prop = data['token'], data['properties']
        large = data.get('large_threshold', 50)
        self.compress_flag = data.get('compress', False)

        user = await self.check_token(token)
        if user is None:
            raise StopConnection(4004, 'Authentication failed...')

        shard = data.get('shard', [0, 1])
        self.check_shard(shard)

        self.shard_id, self.shard_count = shard
        self.sharded = self.shard_count > 1

        # NOTE: If we ever implement sharding, remove this piece of code
        if self.shard_count > 1:
            log.warning('Failing request for sharding: %r', shard)
            raise StopConnection(4010, 'Sharding not available')

        self.user = user

        # NOTE: When sharding, uncomment this code.
        #if self.sharded and (not self.user.bot):
        #    raise StopConnection(4010, 'Sharding not allowed for user accounts.')

        self.session_id = self.gen_sessid()
        if self.session_id is None:
            # NOTE: If we get into a reconnection loop
            # this might be the culprit! check your session ID generation.

            # possible order of events for the loop:
            #  > client identifies
            #  > gateway closes with 4009 
            #  > client reconnects

            #await self.invalidate(False)
            raise StopConnection(4009, 'Session timeout')

        guild_count = await self.guild_man.guild_count(self.user)
        if guild_count > 2500 and self.user.bot and (not self.sharded):
            raise StopConnection(4011, 'Sharding required')

        # check if current shard is with too many guilds
        gm = self.guild_man

        self.guild_ids = []
        def f(guild):
            self.guild_ids.append(guild.id)
            return gm.get_shard(guild.id, self.shard_count)

        shard_guild = map(f, gm.yield_guilds(self.user.id))

        count = collections.Counter(shard_guild)
        for shard_id, guild_count in count.most_common():
            if shard_id != self.shard_id: continue

            if guild_count > 2500:
                raise StopConnection(4010, f'Shard {shard_id} is with too many guilds({guild_count} > 2500)')

        log.debug('guild ids: %r', self.guild_ids)

        self.request_counter = self.server.request_counter[self.session_id]
        self.token = token

        prop = {}
        prop['os'] = prop.get('$os')
        prop['browser'] = prop.get('$browser')
        prop['large'] = large
        self.properties = prop

        self.server.add_connection(self.user.id, self)
        self.events = self.server.event_cache[self.session_id]

        self.events['properties'] = self.properties
        self.events['shard_id'] = self.shard_id

        # NOTE: Always set user presence before calculating the guild list!
        # If we set presence after sending READY, PresenceManager
        # falls apart because it tries to get presence data(for READY)
        # for a user that is still connecting (the client right now)

        # TODO: maybe store presences between client logon/logoff
        # like idle and dnd?
        await self.presence.global_update(self)

        # I'm happy :)
        self.identified = True

        # the actual list of guilds to be sent to the client
        guild_list = []

        for guild in self.guild_man.yield_guilds(self.user.id):
            if not self.is_atomic:
                guild.mark_watcher(self.user.id)

            jguild = guild.as_json

            if guild.member_count > large:
                jguild['members'] = [m.as_json for m in guild.online_members]

            guild_list.append(jguild)

        log.info('[ready:new_session] sid=%s, len_guilds=%d', self.session_id, len(guild_list)) 

        user_settings = await self.settings.get_settings(self.user.id)
        user_relationships = await self.relations.get_relationships(self.user.id)
        user_guild_settings = await self.settings.get_guild_settings(self.user.id)

        # Everyone gets this one.
        ready_packet = {
            '_trace': self.get_identifiers('ready'),
            'v': self.options[0],

            'user': self.user.as_json,
            'private_channels': [],

            'guilds': guild_list,
            'session_id': self.session_id,
        }

        if not self.user.bot:
            friend_presences = [self.presence.get_global_presence(r.u_to.uid) \
                for r in user_relationships]

            user_ready = {
                # the following fields are for user accounts
                # and user accounts only.
                # but I give them regardless of you're a bot or not
                # because I'm lazy.

                'relationships': user_relationships,
                'user_settings': user_settings,
                'user_guild_settings': user_guild_settings,

                # I don't think we are going to have
                # Youtube/Twitch/whatever connections
                'connected_accounts': [],

                # Only you can access those
                # They are handled under another endpoint
                'notes': [],
                'friend_suggestion_count': 0,

                # Assuming this is used for relationships
                # so you get presences for your friends on READY
                # (notice Discord opens your friend list on startup)
                'presences': friend_presences,

                # This might relate with /channels/:id/ack, somehow.
                # I don't know
                'read_state': [],
            
                # ??????
                'analytics_token': 'insert a token here',
                'experiments': [],
                'guild_experiments': [],
                'required_action': 'do something',
            }

            ready_packet.update(user_ready)

        # If its a real bot(non selfbot), we do guild streaming
        # which is sending unavailable guild objects in READY and then
        # dispatching GUILD_CREATE events for all guilds
        if self.user.bot:
            ready_packet['guilds'] =  [{'id': jguild['id'], 'unavailable': True} for jguild in guild_list]

            await self.dispatch('READY', ready_packet)
            for raw_guild in guild_list:
                await self.dispatch('GUILD_CREATE', raw_guild)
        else:
            await self.dispatch('READY', ready_packet)

    @handler(OP.REQUEST_GUILD_MEMBERS)
    async def req_guild_handler(self, data):
        """Handle OP 8 Request Guild Members.

        Dispatches GUILD_MEMBERS_CHUNK (https://discordapp.com/developers/docs/topics/gateway#guild-members-chunk).
        """
        if not self.identified:
            raise StopConnection(4003, 'Not identified to do operation.')

        guild_id = data.get('guild_id')
        query = data.get('query')
        limit = data.get('limit')

        if guild_id is None or query is None or limit is None:
            raise StopConnection(4001, 'Invalid payload')

        if limit > 1000: limit = 1000
        if limit <= 0: limit = 1000

        guild = self.guild_man.get_guild(guild_id)
        if guild is None:
            return

        all_members = [m.as_json for m in guild.members]
        member_list = []

        # NOTE: this is inneficient as hell
        # but that's life I guess..
        if query is not None:
            for member in all_members:
                if member.user.username.startswith(query):
                    member_list.append(member)
        else:
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
                'members': chunk[:limit],
            })

    async def invalidate(self, flag=False, session_id=None):
        """Invalidates a session.

        Parameters
        ----------
        flag: bool
            Flags the session as resumable/not resumable.
        session_id: str, optional
            Session ID.
        """
        log.info(f"Invalidated, can resume: {flag}")
        await self.send_op(OP.INVALID_SESSION, flag)
        if not flag:
            try:
                self.server.event_cache.pop(self.session_id or session_id)
              
                # TODO: Make this work with ratelimits
                # since discord sends you OP 9 + ws close
                if flag is None:
                    raise StopConnection(4000, 'Invalidated session')
            except Exception:
                log.warning('Failed to invalidate session', exc_info=True)

    @handler(OP.RESUME)
    async def resume_handler(self, data):
        """Handler for OP 6 Resume.

        This replays events to the connection.
        """

        log.info('[resume] Resuming a connection')

        try:
            token = data['token']
            session_id = data['session_id']
            replay_seq = data['seq']
        except KeyError:
            raise StopConnection(4001, 'Invalid resume payload')

        try:
            event_data = self.server.event_cache[session_id]
        except KeyError:
            log.warning('[resume] invalidated from session_id not found')
            await self.invalidate(False)

        user = await self.check_token(token)
        if user is None:
            log.warning('[resume] invalidated @ check_token')
            await self.invalidate(session_id=session_id)

        # man how can i resume from the future
        sent_seq = event_data['sent_seq']
        if replay_seq > sent_seq:
            log.warning(f'[resume] invalidated from replay_seq > sent_seq {replay_seq} {sent_seq}')
            raise StopConnection(4007, 'Invalid sequence')

        # if the session lost more than RESUME_MAX_EVENTS
        # events while it was offline, invalidate it.
        if abs(replay_seq - sent_seq) > RESUME_MAX_EVENTS:
            log.warning('[resume] invalidated from seq delta')
            await self.invalidate(False, session_id=session_id)

        seqs_to_replay = range(replay_seq, sent_seq + 1)
        total_seqs = len(seqs_to_replay)
        log.info(f'Replaying {total_seqs} events to {user!r}')

        # NOTE: DON'T CALL self.dispatch in this try block. DON'T. EVER.
        # it will actually hang the dispatch call indefinetly
        # because the dispatch_lock is well... locked
        # and self.dispatch waits for the lock to be released.
        await self.dispatch_lock
        try:
            presences = []

            for seq in seqs_to_replay:
                try:
                    evt = event_data['events'][seq]
                except KeyError:
                    continue

                t = evt.get('t')
                if t == 'PRESENCE_UPDATE':
                    presences.append(evt.get('d'))
                else:
                    await self.send(evt)
        except Exception:
            log.error('Error while resuming', exc_info=True)
            await self.invalidate(True)
        finally:
            self.dispatch_lock.release()

        # Intuition here... Litecord wasn't supposed to be
        # as fault-tolerant as Discord is, Litecord sure
        # doesn't crash on any error, but if the server
        # crash, eventually everything crashes(single point of failure).
        
        # I don't think PRESENCES_REPLACE is even supposed to be
        # used in this non-fault-tolerant scenario... but I added it anyways
        # so whatever.
        if len(presences) > 0:
            await self.dispatch('PRESENCES_REPLACE', presences)

        self.user = user
        self.session_id = session_id

        self.shard_id = event_data['shard_id']
        self.shard_count = event_data['shard_count']
        self.sharded = self.shard_count > 1

        self.guild_ids = []
        f = lambda g: self.guild_ids.append(g.id)

        # we had to fill guild_ids, that is my way
        for guild in self.guild_man.yield_guilds(self.user.id):
            f(guild)

        self.request_counter = self.server.request_counter[self.session_id]
        self.token = token
        self.properties = event_data['properties']

        self.events = self.server.event_cache[self.session_id]
        self.server.add_connection(self.user.id, self)

        self.identified = True

        await self.presence.global_update(self)
        await self.dispatch('RESUMED', {
            '_trace': self.get_identifiers('resume')
        })

    @handler(OP.STATUS_UPDATE)
    @ws_ratelimit('presence_updates')
    async def status_handler(self, data):
        """Handle OP 3 Status Update."""

        if not self.identified:
            raise StopConnection(4003, 'Not Identified')

        try:
            status = data['status']
            afk = data['afk']
        except KeyError:
            return

        idle_since = data.get('since')

        game = data.get('game')
        game_name = None
        if game is not None:
            game_name = game.get('name')

        if afk or idle_since:
            status = 'afk'

        await self.presence.global_update(self, {
            'name': game_name,
            'status': status,
        })

    @handler(OP.GUILD_SYNC)
    async def guild_sync_handler(self, data):
        """Handle OP 12 Guild Sync.

        This is an undocumented OP on Discord's API docs.
        This OP is sent by the client to request member and presence information.
        """

        if not self.identified:
            raise StopConnection(4003, 'Not identified')

        if not isinstance(data, list):
            log.warning('[gateway:guild_sync] Invalid data type')
            return

        # ASSUMPTION: data is a list of guild IDs
        for guild_id in data:
            guild = self.server.guild_man.get_guild(guild_id)
            if guild is None:
                continue

            if self.user.id not in guild.members:
                continue

            if self.is_atomic:
                guild.mark_watcher(self.user.id)

            await self.dispatch('GUILD_SYNC', {
                'id': str(guild_id),
                'presences': [p for p in guild.presences],
                'members': [m.as_json for m in guild.online_members],
            })

        return True

    @handler(OP.VOICE_STATE_UPDATE)
    async def v_state_update_handler(self, data):
        """Handle OP 4 Voice State Update.

        Requests VoiceServer to generate a VoiceState for the connection.
        Dispatches VOICE_STATE_UPDATE and VOICE_SERVER_UPDATE events to the connection.
        """

        guild_id = data.get('guild_id')
        channel_id = data.get('channel_id')
        self_mute = data.get('self_mute', False)
        self_deaf = data.get('self_deaf', False)

        if guild_id is None or channel_id is None:
            log.warning("[vsu] missing params")
            return

        guild = self.server.guild_man.get_guild(guild_id)
        if guild is None:
            log.warning("[vsu] unknown guild")
            return

        channel = guild.channels.get(channel_id)
        if channel is None:
            log.warning("[vsu] unknown channel")
            return

        if channel.str_type != 'voice':
            log.warning("[vsu] not voice channel")
            return

        # We request a VoiceState from the voice manager
        try:
            v_state = await channel.voice_request(self, self_mute, self_deaf)
        except VoiceError:
            log.error('error while requesting VoiceState', exc_info=True)
            return

        log.info(f"{self.user!r} => voice => {channel!r} => {v_state!r}")

        await self.dispatch('VOICE_STATE_UPDATE', v_state.as_json)
        await self.dispatch('VOICE_SERVER_UPDATE', v_state.server_as_json)

    @handler(OP.VOICE_SERVER_PING)
    async def v_ping_handler(self, data):
        """Handle OP 5 Voice Server Ping."""
        log.info(f'VOICE_SERVER_PING with {data!r}')

    @ws_ratelimit('all')
    async def process(self, payload):
        """Process a payload sent by the client.

        Parameters
        ----------
        payload: dict
            https://discordapp.com/developers/docs/topics/gateway#gateway-op-codespayloads
        """
        return await self._process(payload) 

    async def run(self):
        """Starts basic handshake with the client

        The server sends an OP 10 Hello packet to the client and then
        waits in an infinite loop for payloads sent by the client.
        """
        await self.send(self.basic_hello())
        self.wait_task = self.loop.create_task(self.hb_wait_task())
        await self._run()

    async def cleanup(self):
        """Remove the connection from being found by :class:`LitecordServer` functions.

        The cleanup only happens if the connection is open and identified.
        This method only works in the 1st time it is called.
        """

        self.identified = False
        try:
            self.hb_wait_task.cancel()
        except AttributeError:
            pass

        if self.ws.open:
            log.warning("Cleaning up a connection while it is open")

        if self.token is not None:
            try:
                self.server.remove_connection(self.session_id)
                log.debug(f'Success cleaning up sid={self.session_id!r}')
            except Exception:
                log.warning('Error while detaching the connection.', exc_info=True)

            # client is only offline if there's no connections attached to it
            amount_conns = self.server.count_connections(self.user.id)
            log.info(f"{self.user!r} now with {amount_conns} connections")
            if amount_conns < 1:
                await self.presence.global_update(self, self.presence.offline())

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
    except Exception:
        pass

async def server_sentry(server):
    log.info('Starting sentry')
    try:
        while True:
            log.debug('ws sockets: %s', server.ws_server.websockets)

            check_data = await server.check()

            if not check_data.get('good', False):
                log.warning('[sentry] we are NOT GOOD.')

            log.info(f"[sentry] Mongo ping: {check_data['mongo_ping']}msec")

            #log.info(f"[sentry] HTTP throughput: {check_data['http_throughput']}requests/s")
            #log.info(f"[sentry] WS throughput: {check_data['ws_throughput']}packets/s")

            await asyncio.sleep(10)
    except asyncio.CancelledError:
        pass
    except Exception:
        log.error('fug', exc_info=True)


def init_server(app, flags, loop=None):
    """Load the LitecordServer instance."""

    try:
        server = LitecordServer(flags, loop)
    except Exception as err:
        log.error(f'We had an error loading the litecord server. {err!r}')
        raise err # bump

    success = asyncio.ensure_future(server.init(app))
    if not success:
        log.error('We had an error initializing the Litecord Server.')
        raise Exception('Error initializing LitecordServer')

    app.litecord_server = server
    return True


async def on_connection(server, ws, path):
    log.info(f'[ws] New client at {path!r}')
    if not server.accept_clients:
        await ws.close(1000, 'Server is not accepting new clients.')
        return

    params = urlparse.parse_qs(urlparse.urlparse(path).query)

    gw_version = params.get('v', [6])[0]
    encoding = params.get('encoding', ['json'])[0]

    try:
        gw_version = int(gw_version)
    except ValueError:
        gw_version = 6

    if encoding not in ('json', 'etf'):
        await ws.close(4000, f'encoding not supported: {encoding!r}')
        return

    if gw_version != GATEWAY_VERSION:
        await ws.close(4000, f'gw version not supported: {gw_version}')
        return

    conn = Connection(ws, config=(gw_version, encoding), server=server)

    # this starts an infinite loop waiting for payloads from the client
    await conn.run()

async def start_all(app):
    """Start Gateway and HTTP."""

    server = app.litecord_server
    flags = server.flags

    await server.good.wait()

    async def henlo(ws, path):
        return await on_connection(server, ws, path)

    # start HTTP
    http = server.flags['server']['http']

    handler = app.make_handler()
    server.http_server = app.loop.create_server(handler, http[0], http[1])
    log.info(f'[http] http://{http[0]}:{http[1]}')

    # start ws
    ws = flags['server']['ws']

    server.ws_server = websockets.serve(henlo, host=ws[0], port=ws[1])
    log.info(f'[ws] ws://{ws[0]}:{ws[1]} {f"-> ws://{ws[2]}:{ws[1]}" if len(ws) > 2 else ""}')

    return True
