import datetime
import logging

from .objects import LitecordObject
from .utils import dt_to_json

log = logging.getLogger(__name__)

class EmbedFooter(LitecordObject):
    def __init__(self, _data):
        self.url = _data.get('icon_url')
        self.text = _data.get('text')

    @property
    def as_json(self):
        return {
            'icon_url': self.url,
            'text': self.text,
        }

class EmbedImage(LitecordObject):
    def __init__(self, _data):
        self._data = _data
        self.url = _data.get('url')
        self.proxy_url = _data.get('proxy_url')
        self.height = _data.get('height')
        self.width = _data.get('width')

    @property
    def as_json(self):
        return {
            'url': self.url,
            'proxy_url': self.proxy_url,
            'height': self.height,
            'width': self.width,
        }

class EmbedThumbnail(LitecordObject):
    def __init__(self, _data):
        self._data = _data
        self.url = _data.get('url')
        self.proxy_url = _data.get('proxy_url', None)
        self.height = _data.get('height')
        self.width = _data.get('width')

    @property
    def as_json(self):
        return {
            'url': self.url,
            'proxy_url': self.proxy_url,
            'height': self.height,
            'width': self.width,
        }

class EmbedVideo(LitecordObject):
    def __init__(self, _data):
        self.url = _data.get('url')
        self.height = _data.get('height')
        self.width = _data.get('width')

    @property
    def as_json(self):
        return {
            'url': self.url,
            'height': self.height,
            'width': self.width,
        }

class EmbedProvider(LitecordObject):
    def __init__(self, _data):
        self.name = _data.get('name')
        self.url = _data.get('url')

    @property
    def as_json(self):
        return {
            'name': self.name,
            'url': self.url
        }

class EmbedAuthor(LitecordObject):
    def __init__(self, _data):
        self.name = _data.get('name')
        self.url = _data.get('url')
        self.icon_url = _data.get('icon_url')
        self.proxy_icon_url = _data.get('proxy_icon_url')

    @property
    def as_json(self):
        return {
            'name': self.name,
            'url': self.url,
            'icon_url': self.icon_url,
            'proxy_icon_url': self.proxy_icon_url,
        }

class EmbedField(LitecordObject):
    def __init__(self, _data):
        self.name = _data.get('name')
        self.value = _data.get('value')
        self.inline = _data.get('inline')

    @property
    def as_json(self):
        return {
            'name': self.name,
            'value': self.value,
            'inline': self.inline,
        }

class Embed(LitecordObject):
    """A general embed object.

    Attributes:
        _data: Raw embed object.
    """

    def __init__(self, server, raw_embed):
        LitecordObject.__init__(self, server)
        self._data = raw_embed
        self.title = raw_embed['title']
        self.embed_type = 'rich'
        self.description = raw_embed.get('description')
        self.url = raw_embed.get('url')
        self.timestamp = datetime.datetime.now()
        self.color = raw_embed.get('color', 0)

        _get = lambda field: raw_embed.get(field, {})

        self.footer = EmbedFooter(_get('footer'))
        self.image = EmbedImage(_get('image'))
        self.thumbnail = EmbedThumbnail(_get('thumbnail'))
        self.video = EmbedVideo(_get('video'))
        self.provider = EmbedProvider(_get('provider'))
        self.author = EmbedAuthor(_get('author'))

        self.fields = [EmbedField(raw_efield) for raw_efield in _get('fields')]

    @property
    def as_json(self):
        return {
            'title': self.title,
            'type': self.embed_type,
            'description': self.description,
            'url': self.url,
            'timestamp': dt_to_json(self.timestamp),
            'color': self.color,

            'footer': self.footer.as_json,
            'image': self.image.as_json,
            'thumbnail': self.thumbnail.as_json,
            'video': self.video.as_json,
            'provider': self.provider.as_json,
            'author': self.author.as_json,

            'fields': [field.as_json for field in self.fields],
        }
