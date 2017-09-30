import logging

log = logging.getLogger(__name__)

from aiohttp import web

from ..utils import _err, _json
from ..decorators import auth_route

class MockEndpoints:
    """Mocked endpoints gathered from the official client"""
    def __init__(self, server):
        self.server = server
        self.register()

    def register(self):
        self.server.add_post('track', self.h_mock_track)

    async def h_mock_track(self, request):
        """Mock implemenation of `POST /api/track`"""
        return web.Response(status=204, headers={
            'Access-Control-Allow-Headers': 'Authorization, Content-Type, X-Super-Properties, X-Failed-Requests'
        })

