from ..decorators import auth_route
from ..utils import _err, _json

class WebhookEndpoints:
    def __init__(self, server):
        self.server = server
        self.guild_man = server.guild_man

        self.webhook_coll = server.webhook_coll
        #self.register()

    def register(self):
        self.server.add_post('channels/{channel_id}/webhooks', self.h_create_webhook)
        self.server.add_get('channels/{channel_id}/webhooks', self.h_channel_webhooks)
        self.server.add_get('guilds/{guild_id}/webhooks', self.h_all_webhooks)

        self.server.add_get('webhooks/{webhook_id}', self.h_get_webhook)
        self.server.add_get('webhooks/{webhook_id}/{webhook_token}', self.h_get_webhook_t)

        self.server.add_patch('webhooks/{webhook_id}', self.patch_webhook)
        self.server.add_patch('webhooks/{webhook_id}/{webhook_token}', self.patch_webhook_t)

        self.server.add_delete('webhooks/{webhook_id}', self.h_delete_webhook)
        self.server.add_delete('webhooks/{webhook_id}/{webhook_tyoken}', self.h_delete_webhook_t)

        self.server.add_post('webhooks/{webhook_id}/{webhook_token}', self.h_execute)
        self.server.add_post('webhooks/{webhook_id}/{webhook_token}/slack', self.h_execute_slack)
        self.server.add_post('webhooks/{webhook_id}/{webhook_token}/github', self.h_execute_github)

    @auth_route
    async def h_all_webhooks(self, request, user):
        """`GET:/guilds/{guild_id}/webhooks`.
        
        Get all webhooks in a guild.
        """
        guild_id = request.match_info['guild_id']
        guild = self.guild.get_guild(guild_id)
        if guild is None:
            return _err(errno='something')

        if user.id not in guild.members:
            return _err(errno='something')

        return _json([w.as_json for w in guild.webhooks])

