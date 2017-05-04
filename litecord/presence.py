'''
presence.py - presence management

Sends PRESENCE_UPDATE to clients when needed
'''

import logging

from .objects import Presence

log = logging.getLogger(__name__)

class PresenceManager:
    def __init__(self, server):
        log.info('PresenceManager: init')
        self.server = server
        self.presences = {}

    def get_presence(self, user_id):
        try:
            log.warning(f'Presence not found for user {user_id}')
            print(self.presences)
            return self.presences[user_id]
        except KeyError:
            return None

    def add_presence(self, user_id, game=None):
        user = self.server.get_user(user_id)
        self.presences[user_id] = Presence(user, game)

    async def status_update(self, user_id, new_status=None):
        '''
        PresenceManager.status_update(user_id, new_status)

        Updates an user's status and sends respective PRESENCE_UPDATE events to relevant clients.
        '''

        if new_status is None:
            new_status = {}

        user = self.server.get_user(user_id)
        if user_id not in self.presences:
            self.presences[user_id] = Presence(user, new_status)

        # TODO: just do presence.game.update if needed
        presence = self.presences[user_id]
        presence.game.update(new_status)

        log.info(f'{user_id} is now playing {presence.game["name"]}, updating presences')

        for guild in user.guilds:
            for member in guild.online_members:
                connection = member.connection
                if connection is not None:
                    await connection.dispatch('PRESENCE_UPDATE', presence.as_json)
