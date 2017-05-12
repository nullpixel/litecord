import base64
import hashlib

class Images:
    """Images - image manager.

    `Images` manages profile pictures and message attachments.
    """
    def __init__(self, server, config):
        self.server = server
        self.config = config

    async def avatar_register(self, avatar_data):
        # TODO: parse data
        return ''

    async def avatar_retrieve(self, avatar_hash):
        return ''
