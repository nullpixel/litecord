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

    async def status_update(self, user_id, game_name):
        '''
        PresenceManager.status_update(user_id, game_name)

        Updates an user's status and sends respective PRESENCE_UPDATE events
        This is just a dummy implementation. PresenceManager.update_presence should be better.

        Returns a bool on success/failure.
        '''

        user = self.server.get_user(user_id)
        if user_id not in self.presences:
            self.presences[user_id] = Presence(user, game_name)

        presence = self.presences[user_id]

        presence.game = {
            'name': game_name,
            'type': 0,
            #'url': 'meme',
        }
        log.info(f'{user_id} is now playing {game_name}, updating presences')

        for guild in user.guilds:
            for member in guild.online_members:
                connection = member.connection
                if connection is None:
                    continue

                await connection.dispatch('PRESENCE_UPDATE', presence.as_json)
            return True

    async def update_presence(self, user_id, status):
        '''
        PresenceManager.update_presence(user_id, status)

        Updates the presence of a user.
        Sends a PRESENCE_UPDATE event to relevant clients.
        '''

        '''
        ????dummy code????

        current_presence = self.presences.get(user_id)
        new_presence = self.make_presence(status)

        # something like this lol
        user = await self.user.get_user(user_id)
        for guild_id in user.guilds:
            guild = await self.guilds.get_guild(guild_id)
            for member in guild:
                member = await self.guilds.get_member(guild_id, member_id)
                c = await self.server.get_connection(member_id)
                if c is not None:
                    await c.dispatch('PRESENCE_UPDATE', self.diff(current_presence, new_presence))
        '''

        pass
