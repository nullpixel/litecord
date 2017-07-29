import logging
import random
import subprocess

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
        self.gw_Starting = lambda: web.Response(status=503, text='Gateway is still starting')


        self.litecord_version = subprocess.check_output("git rev-parse HEAD", \
            shell=True).decode('utf-8').strip()

        self.register()

    def register(self):
        self.server.add_get('gateway', self.h_gateway)
        self.server.add_get('gateway/bot', self.h_gateway_bot)
        self.server.add_get('version', self.h_version)

    async def h_version(self, request):
        """`GET:/version`.
        
        Get the server's Git commit hash.
        """
        return _json({'version': self.litecord_version})

    async def h_gateway(self, request):
        """`GET:/gateway`.

        Get the gateway URL.
        This endpoint doesn't require authentication.
        """
        if not self.server.good.is_set():
            return self.gw_starting()

        log.info('Accepting clients: %s', self.server.accept_clients)
        if not self.server.accept_clients:
            return self.gw_down()

        return _json({'url': self.server.get_gateway_url()})

    @auth_route
    async def h_gateway_bot(self, request, user):
        """`GET:/gateway/bot`.
        
        Get the gateway URL and a recommended number of shards
        to start with.

        This endpoint requires authentication with a bot token.
        """
        if not self.server.good.is_set():
            return self.gw_starting()

        if not self.server.accept_clients:
            return self.gw_down()

        if not user.bot:
            return _err('401: Unauthorized')

        url = self.server.get_gateway_url()
        shards = await self.guild_man.shard_amount(user)
        return _json({'gateway': url, 'shards': shards})

