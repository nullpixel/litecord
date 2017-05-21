import aiohttp

from bs4 import BeautifulSoup

from .embeds import Embed
from .utils import _json, _err

class EmbedManager:
    def __init__(self, server):
        self.server = server
        self.cache = {}

    def init(self, app):
        _r = app.router

        _r.add_get('/embed', self.h_get_embed)

    async def h_get_embed(self, request):
        """Convert a page to an embed object."""
        try:
            payload = await request.json()
        except:
            return _err('erroneous payload')

        url = payload['url']

        if url not in self.cache:
            return _json((await self.url_to_embed(url)).as_json)

        return _json(self.cache[url].as_json)

    async def url_to_embed(url):
        soup = None

        if url in self.cache:
            return self.cache[url]

        async with aiohttp.ClientSession() as sess:
            async with sess.get(url) as resp:
                soup = BeautifulSoup(await resp.text())

        em = Embed({
            'url': url,
        })

        self.cache[url] = em
        return em
