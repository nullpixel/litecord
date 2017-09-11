import logging

from voluptuous import Schema

from ..utils import _err, _json
from ..decorators import auth_route

log = logging.getLogger(__name__)

class EmojiEndpoint:
    def __init__(self, server):
        self.server = server
        self.guild_man = server.guild_man

        self.register()

    def register(self):
        #self.server.add_get('guilds/{guild_id}/emojis', self.h_get_emojis)
        #self.server.add_get('guilds/{guild_id}/emojis/{emoji_id}', self.h_get_single_emoji)
        #self.server.add_post('guilds/{guild_id}/emojis', self.h_create_emoji)
        #self.server.add_patch('guilds/{guild_id}/emojis/{emoji_id}', self.h_edit_emoji)
        #self.server.add_delete('guilds/{guild_id}/emojis/{emoji_id}', self.h_delete_emoji)

    @auth_route
    async def h_get_emojis(self, user, request):
        pass

    @auth_route
    async def h_get_single_emoji(self, user, request):
        pass

    @auth_route
    async def h_create_emoji(self, user, request):
        pass

    @auth_route
    async def h_edit_emoji(self, user, request):
        pass

    @auth_route
    async def h_delete_emoji(self, user, request):
        pass

