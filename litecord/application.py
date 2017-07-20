import logging

from .utils import get_random_salt, pwd_hash
from .objects import Application
from .snowflake import get_snowflake

log = logging.getLogger(__name__)

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
        self.user_coll = server.user_coll

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

    async def create_bot(self, owner, app):
        """Create a bot user.
        
        Bot users are different in the sense
        that they don't have a password tied to them
        but they have a salt tied to them so
        token generation properly works.
        """
        app_id = get_snowflake() 
        app['app_id'] = app_id
        app['owner_id'] = owner.id

        log.info('Making a bot app: uid=%d name=%r', app_id, app['name'])

        await self.app_coll.insert_one(app)

        discrim = await self.server.get_discrim(app['name'])
        salt = await get_random_salt()

        bot_user = {
            'user_id': app_id,
            'username': app['name'],
            'discriminator': discrim,
            'password': {
                'hash': pwd_hash('', salt),
                'salt': salt,
            },
            'avatar': '',
            'bot': True,
            'verified': True,
        }
        await self.user_coll.insert_one(bot_user)

        return Application(owner, app)

