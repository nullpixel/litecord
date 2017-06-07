'''
presence.py - presence management

Sends PRESENCE_UPDATE to clients when needed
'''

import logging
import time

from .objects import Presence, User

log = logging.getLogger(__name__)

class PresenceManager:
    """Manage presence objects/updates."""
    def __init__(self, server):
        self.server = server
        self.presences = {}

    def get_presence(self, guild_id, user_id):
        """Get a `Presence` object from a user's ID."""
        guild_id = int(guild_id)
        user_id = int(user_id)

        try:
            guild_presences = self.presences[guild_id]
        except KeyError:
            self.presences[guild_id] = {}
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

        if guild_id not in self.presences:
            self.presences[guild_id] = {}

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
        """Updates an user's status, globally.

        Dispatches PRESENCE_UPDATE events to relevant clients.

        Parameters
        ----------
        user: :class:`User`
            The user we are updating.
        new_status: dict, optional
            Raw presence object
        """

        if user is None:
            log.error("Can't update presence for no one.")
            return False

        for guild in user.guilds:
            await self.status_update(guild, user, new_status)

    async def typing_start(self, user_id, channel_id):
        """Sends a TYPING_START to relevant clients in the channel.

        Parameters
        ----------
        user_id: str
            User's snowflake ID.
        channel_id: str
            Channel's snowflake ID.
        """
        typing_timestamp = int(time.time())
        channel = self.server.guild_man.get_channel(channel_id)

        # TODO: don't send events to people who can't read the channel
        #  Requires permission stuff
        await channel.dispatch('TYPING_START', {
            'channel_id': channel_id,
            'user_id': user_id,
            'timestamp': typing_timestamp,
        })
