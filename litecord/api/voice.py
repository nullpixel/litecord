import logging

from ..utils import _err, _json
from ..decorators import auth_route

log = logging.getLogger(__name__)

class VoiceEndpoint:
    """Handle specific voice stuff."""
    def __init__(self, server):
        self.server = server        
        self.register(server.app)

    def register(self, app):
        self.server.add_get('voice/regions', self.h_get_voice_regions)

    @auth_route
    async def h_get_voice_regions(self, request, user):
        """`GET /voice/regions`.

        Get available voice region objects through
        :meth:`VoiceManager.get_all_regions`
        """
        return _json([vr.as_json for vr in self.server.voice.voice_regions])
