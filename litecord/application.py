
from .objects import Application

class ApplicationManager:
    """Manage Litecord Applications.
    
    Attributes
    ----------
    server: :class:`LitecordServer`
    """
    def __init__(self, server):
        self.server = server
        self.guild_man = server.guild_man
        self.app_coll = server.app_coll

    async def get_app(self, app_id):
        """Get an application"""
        raw_app = await self.app_coll.find_one({'app_id': int(app_id)})
        if raw_app is None: return

        owner = self.server.get_user(raw_app['owner_id'])
        return Application(owner, raw_app)

    async def get_apps(self, user):
        """Get a list of applications"""
        cur = self.app_coll.find({'owner_id': user.id})
        return [Application(user, raw) for raw in await cur.to_list(length=None)]
