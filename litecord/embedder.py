import aiohttp
from .embeds import Embed

class EmbedManager:
    pass

async def url_to_embed(url):
    return Embed({
        'url': url,
    })
