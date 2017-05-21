import aiohttp

from bs4 import BeautifulSoup

from .embeds import Embed

class EmbedManager:
    def __init__(self, server):
        self.server = server
        self.cache = {}

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
