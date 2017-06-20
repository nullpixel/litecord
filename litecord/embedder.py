import aiohttp
import logging

from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .embeds import Embed
from .utils import _json, _err

log = logging.getLogger(__name__)

class EmbedManager:
    def __init__(self, server):
        self.server = server
        self.cache = {}

        self.parsers = {
            'xkcd.com': self.xkcd_parser,
        }

        self.server.add_get('embed', self.h_get_embed)

    async def h_get_embed(self, request):
        """Convert a page to an embed object."""
        try:
            payload = await request.json()
            url = payload['url']
        except:
            return _err('erroneous payload')

        if url not in self.cache:
            em = await self.url_to_embed(url)

            try:
                return _json(em.as_json)
            except Exception as err:
                log.error('Error generating embed', exc_info=True)
                return _err(f"Error converting to embed({em!r}, {err!r}).")

        return _json(self.cache[url].as_json)

    async def soupify(self, url):
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url) as resp:
                return BeautifulSoup(await resp.text())

    async def get(self, url):
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url) as resp:
                return resp

    async def xkcd_parser(self, urlobj):
        full_url = urlobj.geturl()
        xkcd_number = urlobj.path[1:]

        log.info(f"Making XKCD embed from {full_url!r} number {xkcd_number!r}")

        xkcd_data_url = f"https://xkcd.com/{xkcd_number}/info.0.json"

        try:
            resp = await self.get(xkcd_data_url)
            xkcd_data = await resp.json()
        except:
            log.warning("Failed to retrieve data from XKCD", exc_info=True)
            return None

        log.info(f"XKCD: {len(str(xkcd_data))} bytes")

        em = Embed(self.server, {
            'title': f'[xkcd: {xkcd_data["title"]}]({full_url})',
            'image': {
                'url': xkcd_data['img'],
            },
            'footer': {
                'text': xkcd_data['alt'],
            },
            'url': full_url,
        })

        return em

    async def url_to_embed(self, url):
        if url in self.cache:
            return self.cache[url]

        parsed = urlparse(url)
        identifier = parsed.netloc

        try:
            em = await self.parsers[identifier](parsed)
            if em is not None:
                log.info("Caching embed")
                self.cache[url] = em
            return em
        except:
            log.error('Errored while parsing website', exc_info=True)
            return None
