
class SettingsManager:
    """User settings manager.
    
    Provides functions for users to change their settings and retrieve them back.

    Attributes
    ----------
    server: :class:`LitecordServer`
        Litecord server instance.
    settings_coll: `mongo collection`
        User settings MongoDB collection.
    """
    def __init__(self, server):
        self.server = server
        self.guild_man = server.guild_man

        self.settings_coll = self.server.settings_coll

    async def get_settings(self, user):
        """Get a settings object from a User ID.
        
        Parameters
        ----------
        user_id: :class:`User`
            User ID to be get settings from.
        """
        if user.bot:
            return {}

        settings = await self.settings_coll.find_one({'user_id': user.id})
        if settings is None:
            settings = {}
        return settings

    async def get_guild_settings(self, user):
        """Get a User Guild Settings object to be used
        in READY payloads.
        
        Parameters
        ----------
        user_id: :class:`User`
            User ID to get User Guild Settings payload for.

        Returns
        -------
        list
            The User Guild Settings payload.
        """
        if user.bot:
            return []

        res = []
        default_gsetting = {
            'suppress_everyone': False,
            'muted': False,
            'mobile_push': False,
            'message_notifications': 1,
            'guild_id': None,
            'channel_overrides': [],
        }

        async for guild in self.guild_man.yield_guilds(user.id):
            res.append({**default_gsetting, **{'guild_id': str(guild.id)}})

        return res
