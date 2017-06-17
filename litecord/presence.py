'''
presence.py - presence management

Sends PRESENCE_UPDATE to clients when needed
'''

import asyncio
import collections
import logging
import time

import websockets

from .objects import Presence, User
from .ext.op import OP
from .ext.conn import JSONConnection

log = logging.getLogger(__name__)

class PresenceManager:
    """Manage presence objects/updates."""
    def __init__(self, server):
        self.server = server
        self.presence_db = server.presence_db
        self.presences = collections.defaultdict(dict)

    def get_presence(self, guild_id, user_id):
        """Get a `Presence` object from a guild + user ID pair."""
        guild_id = int(guild_id)
        user_id = int(user_id)

        guild_presences = self.presences[guild_id]

        try:
            return guild_presences[user_id]
        except KeyError:
            log.warning(f"Presence not found for {user_id}")
            return None

    def offline(self):
        """Return a presence dict object for offline users"""
        return {
            'status': 'offline',
            'type': 0,
            'name': None,
            'url': None,
        }

    async def presence_count(self, guild_id):
        """Count the approximate amount of presence objects for a guild.

        Parameters
        ----------
        guild_id: int
            ID of the guild to search.

        Returns
        -------
        int:
            Approximate amount of presence objects in a guild.
        """

        guild_id = int(guild_id)
        guild_presences = self.presences.get(guild_id, {})
        return len(guild_presences.keys())

    async def count_all(self):
        """Return a count for all available presence objects."""

        return sum([await self.presence_count(guild_id) for guild_id in \
            self.server.guild_man.guilds.keys()])

    async def status_update(self, guild, user, new_status=None):
        """Update a user's status in a guild.

        Dispatches PRESENCE_UPDATE events to relevant clients in the guild.

        Parameters
        ----------
        guild: :class:`Guild`
            The guild that we want to update our presence on.
        user: :class:`User`
            The user we want to update presence from.
        new_status: dict, optional
            New raw presence data.

        Returns
        -------
        ``None``

        """

        if new_status is None:
            new_status = {}

        user_id = user.id
        guild_id = guild.id

        guild_presences = self.presences[guild_id]

        if user_id not in guild_presences:
            guild_presences[user_id] = Presence(guild, user, new_status)

        user_presence = guild_presences[user_id]

        differences = set(user_presence.game.values()) ^ set(new_status.values())
        log.debug(f"presence for {user!r} has {len(differences)} diffs")

        if len(differences) > 0:
            user_presence.game.update(new_status)
            log.info(f'[presence] {guild!r} -> {user!s} -> {user_presence!r}, updating')
            await guild.dispatch('PRESENCE_UPDATE', user_presence.as_json)

    async def global_update(self, user, new_status=None):
        """Updates a user's status, globally.

        Dispatches PRESENCE_UPDATE to all guilds the user is in.

        Parameters
        ----------
        user: :class:`User`
            The user we are updating.
        new_status: dict, optional
            Raw presence object.
        """

        if user is None:
            return

        for guild in user.guilds:
            await self.status_update(guild, user, new_status)

    async def typing_start(self, user_id, channel_id):
        """Dispatches a TYPING_START to relevant clients in the channel.

        Parameters
        ----------
        user_id: str
            User's snowflake ID.
        channel_id: str
            Channel's snowflake ID.
        """
        typing_timestamp = int(time.time())
        channel = self.server.guild_man.get_channel(channel_id)

        await channel.dispatch('TYPING_START', {
            'channel_id': channel_id,
            'user_id': user_id,
            'timestamp': typing_timestamp,
        })

class ExternalPresenceManager:
    """An external presence manager, running on another computer in the network
    
    This class has the same methods as :class:`PresenceManager`, but they route
    packets to the external machine running the ``presence_maanager`` node.

    NOTE: This is incomplete.
    """
    def __init__(self, server):
        self.server = server
        self.local_presence = PresenceManager(server)

    async def status_update(self, guild, user, new_status=None):
        if new_status is None:
            new_status = {}

        user_id = user.id
        guild_id = guild.id

        guild_presences = await self.get_presences(guild_id)

        if user_id not in guild_presences:
            await self.set_presence(guild_id, user_id, new_status)

        user_presence = await self.get_presence(guild_id, user_id)

        # Dispatching follows the same strategy as PresenceManager
        differences = set(user_presence.game.values()) ^ set(new_status.values())
        log.debug(f"presence for {user!r} has {len(differences)} diffs")

        if len(differences) > 0:
            user_presence.game.update(new_status)
            await self.set_presence(guild_id, user_id, user_presence.game)

            log.info(f'[presence] {guild!r} -> {user!s} -> {user_presence!r}, updating')
            await guild.dispatch('PRESENCE_UPDATE', user_presence.as_json)

    async def typing_start(self, user_id: int, channel_id: int):
        return await self.local_presence.typing_start(user_id, channel_id)

class PresenceManagerNode:
    """A presence manager node
    
    This is incomplete.
    """
    def __init__(self):
        self.handlers = {
            'SET_PRESENCE': self.set_presence,
            'GET_PRESENCE': self.get_presence,
        }
        self.presence

    async def set_presence(self, conn, data):
        try:
            user_id = data['user_id']
            guild_id = data['guild_id']
            game = data['game']
        except KeyError:
            await conn.ws.close(4001)
            return

    async def new_connection(self, websocket, path):
        conn = JSONConnection(websocket)

        await conn.handshake()

        while True:
            j = await conn.recv()

            op = j['op']
            if op == OP.CALL:
                evt_name = j['t']
                await self.handlers.get(evt_name, lambda x: x)(conn, j['d'])

    def run(self, config, loop=None):
        """Starts the node"""
        if loop is None:
            loop = asyncio.get_event_loop()

        ws_server = websockets.server(self.new_connection, '', )
        loop.run_until_complete(ws_server)
        log.info('[node:presence] starting loop')
        loop.run_forever()
