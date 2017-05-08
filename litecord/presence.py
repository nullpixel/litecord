'''
presence.py - presence management

Sends PRESENCE_UPDATE to clients when needed
'''

import logging
import time

from .objects import Presence

log = logging.getLogger(__name__)

class PresenceManager:
    """Manage presence objects/updates."""
    def __init__(self, server):
        log.info('PresenceManager: init')
        self.server = server
        self.presences = {}

    def get_presence(self, user_id):
        """Get a `Presence` object from a user's ID."""
        try:
            log.warning(f'Presence not found for user {user_id}')
            print(self.presences)
            return self.presences[user_id]
        except KeyError:
            return None

    def add_presence(self, user_id, game=None):
        """Overwrite someone's presence."""
        user = self.server.get_user(user_id)
        self.presences[user_id] = Presence(user, game)

    def offline(self):
        """Return a presence dict object for offline users"""
        return {
            'status': 'offline',
            'type': 0,
            'name': None,
            'url': None,
        }

    async def status_update(self, user_id, new_status=None):
        """Updates an user's status.

        Dispatches PRESENCE_UPDATE events to relevant clients.
        """

        if new_status is None:
            new_status = {}

        user = self.server.get_user(user_id)
        if user_id not in self.presences:
            self.presences[user_id] = Presence(user, new_status)

        # TODO: just do presence.game.update if needed
        presence = self.presences[user_id]
        presence.game.update(new_status)

        log.info(f'{user_id} : {presence}, updating presences')

        for guild in user.guilds:
            for member in guild.online_members:
                conn = member.connection
                if conn:
                    await conn.dispatch('PRESENCE_UPDATE', presence.as_json)

    async def typing_start(self, user_id, channel_id):
        """Sends a TYPING_START to relevant clients."""
        typing_timestamp = int(time.time())
        channel = self.server.guild_man.get_channel(channel_id)

        # TODO: don't send events to people who can't read the channel
        #  Requires permission stuff
        for member in channel.guild.online_members:
            conn = member.connection
            if conn:
                await conn.dispatch('TYPING_START', {
                    'channel_id': channel_id,
                    'user_id': user_id,
                    'timestamp': typing_timestamp,
                })
