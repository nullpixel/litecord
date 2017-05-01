'''
guilds.py - All handlers under /guilds/*
'''

import json
import logging
from ..utils import _err, _json, strip_user_data

log = logging.getLogger(__name__)

class GuildsEndpoint:
    def __init__(self, server):
        self.server = server

    async def h_post_guilds(self, request):
        pass
