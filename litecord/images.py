import logging
import base64
import hashlib

from .err import ImageError

log = logging.getLogger(__name__)

AVATAR_MIMETYPES = [
    'image/jpeg', 'image/jpg', 'image/png',
    #'image/gif'
]

class Images:
    """Images - image manager.

    `Images` manages profile pictures and message attachments.
    """
    def __init__(self, server, config):
        self.server = server
        self.config = config

        self.image_db = server.litecord_db['images']
        self.attach_db = server.litecord_db['attachments']

    def extract_uri(self, data):
        try:
            sp = data.split(',')
            data_string = sp[0]
            encoded_data = sp[1]
            mimetype = data_string.split(';')[0].split(':')[1]
        except:
            raise ImageError('error decoding image data')

        return encoded_data, mimetype

    async def raw_add_image(self, data, img_type='avatar'):
        """Add an image.

        Returns a string, representing the image hash.
        The image hash can be used in `Images.image_retrieve` to get
        raw binary data.
        """

        try:
            encoded_data, mimetype = self.extract_uri(data)
        except ImageError as err:
            raise err

        try:
            AVATAR_MIMETYPES.index(mimetype)
        except:
            raise ImageError(f'Invalid MIME type {mimetype!r}')

        try:
            dec_data = base64.b64decode(encoded_data)
        except:
            raise ImageError('Error decoding Base64 data')

        data_hash = hashlib.sha256(dec_data).hexdigest()
        log.info(f'Inserting {len(dec_data)}-bytes image.')

        await self.image_db.insert_one({
            'type': img_type,
            'hash': data_hash,
            'data': encoded_data,
        })

        return data_hash

    async def avatar_register(self, avatar_data):
        """Registers an avatar in the avatar database."""
        return (await self.raw_add_image(avatar_data))

    async def add_attachment(self, data):
        return (await self.raw_add_image(data, 'attachment'))

    async def avatar_retrieve(self, avatar_hash):
        img = await self.image_db.find_one({'type': 'avatar', 'hash': avatar_hash})
        try:
            return img.get('data')
        except:
            return None

    async def image_retrieve(self, img_hash):
        img = await self.image_db.find_one({'type': 'attachment', 'hash': img_hash})
        try:
            return img.get('data')
        except:
            return None
