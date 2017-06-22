import logging

from .snowflake import get_snowflake

log = logging.getLogger(__name__)

class RelationsManager:
    """Relationship manager.

    Manages relationships between users.
    A relationship can be in one of 2 types: friend or block.

    TODO: actually program it
    """
    def __init__(self, server):
        self.server = server
        self.guild_man = server.guild_man
        self.relation_db = server.relation_db

        self.relationships = {}

    async def get_relationships(self, user_id: int):
        return []

    async def add_relation(self, user, other, raw_relation):
        pass

    async def remove_relation(self, relation_id):
        pass

    async def add_block(self, user, other):
        return await self.add_relation(user, other, {'type': 'block'})

    async def init(self):
        pass
