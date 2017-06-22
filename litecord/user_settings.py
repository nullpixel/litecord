
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

        self.settings_coll = self.server.settings_coll

    async def get_settings(self, user_id: int):
        """Get a settings object from a User ID.
        
        Parameters
        ----------
        user_id: int
            User ID to be get settings from.
        """
        settings = self.settings_coll.find_one({'user_id': user_id})
        if settings is None:
            settings = {}
        return settings

