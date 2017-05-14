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
        _r.add_get('/images/avatars/{user_id}/.{format}', self.h_get_user_avatar)

    async def h_get_user_avatar(self, request):
        """`GET /images/avatars/{user_id}`.

        Retrieve a user's avatar.
        """

        # 🤔 thinking about this part
        '''_error = await self.server.check_request(request)
        _error_json = json.loads(_error.text)
        if _error_json['code'] == 0:
            return _error

        channel_id = request.match_info['channel_id']
        user = self.server._user(_error_json['token'])'''

        user_id = request.match_info['user_id']
        user = self.server.get_user(user_id)
        if user is None:
            return _err(errno=10012)

        image = await self.images.avatar_retrieve(user.avatar_hash)
        if image is None:
            return _err('image not found')

        binary = base64.b64decode(image['data'])
        return web.Response(body=binary)
