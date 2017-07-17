import logging

from aiottp import web

from ..utils import _err, _json
from ..decorators import auth_route

log = logging.getLogger(__name__)

class GatewayEndpoint:
    """Gateway-related endpoints."""
    def __init__(self, server):
        self.server = server
        self.guild_man = server.guild_man

        self.gw_down_response = web.Response(status=404, text='Gateway is not accepting any new clients.')

        self.register()

    def register(self):
        self.server.add_get('gateway', self.h_gateway)
        self.server.add_get('gateway/bot', self.h_gateway_bot)

    async def h_gateway(self, request):
        if self.server.accept_clients:
            return self.gw_down_response 

        return _json({'gateway': self.server.get_gateway_url()})

    @auth_route
    async def h_gateway_bot(self, request, user):
        if self.server.accept_clients:
            return self.gw_down_response

        url = self.server.get_gateway_url()
        shards = await self.guild_man.shard_amount(user)
        return _json({'gateway': url, 'shards': shards})

