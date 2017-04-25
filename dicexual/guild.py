import logging

log = logging.getLogger(__name__)

class GuildManager:
    def __init__(self, server):
        self.server = server

    def get_guild(self, guild_id):
        return None

    def init(self):
        log.warning("Nothing implemented in Guild management")
        return False
