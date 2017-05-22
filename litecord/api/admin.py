import json
import logging

from aiohttp import web
from ..utils import _err, _json
from ..ratelimits import admin_endpoint

log = logging.getLogger(__name__)

class AdminEndpoints:
    def __init__(self, server):
        self.server = server
        self.guild_man = server.guild_man

    def register(self, app):
        _r = app.router
        _r.add_get('/api/count', self.h_get_counts)

    @admin_endpoint
    async def h_get_counts(self, request, user):
        """`GET:/counts`.

        Return some statistics.
        """
        return _json(await self.server.make_counts())
