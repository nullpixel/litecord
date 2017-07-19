import logging

from aiohttp import web

from ..utils import _err, _json
from ..decorators import auth_route

log = logging.getLogger(__name__)

class GatewayEndpoint:
    """Gateway-related endpoints."""
    def __init__(self, server):
        self.server = server
        self.guild_man = server.guild_man

        self.gw_down = lambda: web.Response(status=404, text='Gateway it not accepting any new clients.')

        self.register()

    def register(self):
        self.server.add_get('gateway', self.h_gateway)
        self.server.add_get('gateway/bot', self.h_gateway_bot)

    async def h_gateway(self, request):
        log.info('Accepting clients: %s', self.server.accept_clients)
        if not self.server.accept_clients:
            return self.gw_down()

        return _json({'url': self.server.get_gateway_url()})

    @auth_route
    async def h_gateway_bot(self, request, user):
        if not self.server.accept_clients:
            return self.gw_down()

        if not user.bot:
            return _err('401: Unauthorized')

        url = self.server.get_gateway_url()
        shards = await self.guild_man.shard_amount(user)
        return _json({'gateway': url, 'shards': shards})

