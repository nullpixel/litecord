'''
presence.py - presence management

Sends PRESENCE_UPDATE to clients when needed
'''

class PresenceManager:
    def __init__(self, server):
        self.server = server

    async def status_update(self, user_id, game_name):
        '''
        PresenceManager.status_update(user_id, game_name)

        Updates an user's status and sends respective PRESENCE_UPDATE events
        This is just a dummy implementation. PresenceManager.update_presence should be better.
        '''

        user = await self.server.get_user(user_id)
        for guild in user.guilds:
            guild_members = guild.members
            if len(guild_members) < 2:
                return

            for member in guild_members:
                connection = member.connection
                if connection is None:
                    continue

                await connection.dispatch('PRESENCE_UPDATE', {
                    'user': user.as_json,
                    'roles': [],
                    'game': {
                        'name': game_name
                        'type': 0
                        #'url': 'meme',
                    },
                    'guild_id': guild.id,
                    'status': 'online',
                })

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
