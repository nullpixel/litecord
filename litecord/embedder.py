import aiohttp
from .embeds import Embed

async def url_to_embed(url):
    return Embed({
        'url': url,
    })
