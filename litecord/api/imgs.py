import logging
import base64

from aiohttp import web
from ..utils import _err, _json, strip_user_data

log = logging.getLogger(__name__)

class ImageEndpoint:
    def __init__(self, server):
        self.server = server
        self.images = server.images

    def register(self, app):
        _r = app.router
        _r.add_get('/images/avatars/{user_id}/{avatar_hash}.{img_format}', self.h_get_user_avatar)
        #_r.add_get('/embed/avatars/{default_id}.{img_format}', self.h_get_default_avatar)

    async def h_get_user_avatar(self, request):
        """`GET /images/avatars/{user_id}/{avatar_hash}.{img_format}`.

        Retrieve a user's avatar.
        """

        user_id = request.match_info['user_id']
        avatar_hash = request.match_info['avatar_hash']

        # TODO: convert image to img_format
        img_format = request.match_info['img_format']

        user = self.server.get_user(user_id)
        if user is None:
            return _err(errno=10012)

        image = await self.images.avatar_retrieve(avatar_hash)
        if image is None:
            return _err('image not found')

        raw = base64.b64decode(image)
        return web.Response(body=raw)
