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
        try:
            guild_presences = self.presences[guild_id]
        except KeyError:
            self.presences[guild_id] = {}
            guild_presences = self.presences[guild_id]

        try:
            return guild_presences[user_id]
        except:
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

    async def status_update(self, guild, user, new_status=None):
        """Update a user's status in a guild.

        Dispatches PRESENCE_UPDATE events to relevant clients in the guild.
        """

        if new_status is None:
            new_status = {}

        user_id = user.id
        guild_id = guild.id

        if guild_id not in self.presences:
            self.presences[guild_id] = {}

        guild_presences = self.presences[guild_id]
        guild_presences[user_id] = Presence(guild, user, new_status)

        # TODO: just do presence.game.update if needed
        presence = guild_presences[user_id]
        presence.game.update(new_status)

        log.info(f'{user!s} : {presence!r}, updating presences')

        await guild.dispatch('PRESENCE_UPDATE', presence.as_json)

    async def global_update(self, user, new_status=None):
        """Updates an user's status, globally.

        Dispatches PRESENCE_UPDATE events to relevant clients.
        """

        if user is None:
            log.error("Can't update presence for no one.")
            return False

        if not isinstance(user, User):
            user = self.server.get_user(user_id)
            if user is None:
                log.error("[global_update] user not found")
                return

        for guild in user.guilds:
            await self.status_update(guild, user, new_status)

    async def typing_start(self, user_id, channel_id):
        """Sends a TYPING_START to relevant clients in the channel's guild."""
        typing_timestamp = int(time.time())
        channel = self.server.guild_man.get_channel(channel_id)

        # TODO: don't send events to people who can't read the channel
        #  Requires permission stuff
        await channel.dispatch('TYPING_START', {
            'channel_id': channel_id,
            'user_id': user_id,
            'timestamp': typing_timestamp,
        })
