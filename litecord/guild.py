import logging
from .objects import Guild

log = logging.getLogger(__name__)

class GuildManager:
    def __init__(self, server):
        self.server = server
        self.guild_db = server.db['guilds']
        self.guilds = {}

    def get_guild(self, guild_id):
        return self.guilds.get(guild_id)

    def get_guilds(self, user_id):
        return [self.guilds[guild_id] for guild_id in self.guilds \
            if user_id in self.guilds[guild_id].member_ids]

    def all_guilds(self):
        for guild_id in self.guilds:
            yield self.guilds(guild_id)

    def init(self):
        for guild_id in self.guild_db:
            guild_data = self.guild_db[guild_id]
            self.guilds[guild_id] = Guild(self.server, guild_data)
        return True
