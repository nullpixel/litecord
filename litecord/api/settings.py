import logging

from ..utils import _err, _json
from ..decorators import auth_route

log = logging.getLogger(__name__)

class SettingsEndpoints:
    def __init__(self, server):
        self.server = server
        self.guild_man = server.guild_man
        self.settings = server.settings

        self.register()

    def register(self):
        self.server.add_get('@me/settings', self.h_get_settings)
        self.server.add_patch('@me/settings', self.h_update_settings)
        
    @auth_route
    async def h_get_settings(self, request, user):
        """`GET /@me/settings`.
        Get user settings.
        """
        settings = await user.get_settings()
        return _json(settings)

    @auth_route
    async def h_update_settings(self, request, user):
        """`PATCH /@me/settings`.
        Update user settings.

        This handler trusts the user to not send
        malformed data, no schema-checking here.
        """
        try:
            payload = await request.json()
        except:
            return _err('error parsing json')

        new_settings = await self.settings.update(user, payload)
        return _json(new_settings)
