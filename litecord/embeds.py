import datetime
import logging

from .objects import LitecordObject

log = logging.getLogger(__name__)

class EmbedFooter(LitecordObject):
    def __init__(self, _data):
        self.url = _data['url']
        self.text = _data['text']

    @property
    def as_json(self):
        return {
            'icon_url': self.url,
            'text': self.text,
        }

class EmbedImage(LitecordObject):
    def __init__(self, _data):
        self._data = _data
        self.url = _data['url']
        self.proxy_url = _data.get('proxy_url', None)
        self.height = _data['height']
        self.width = _data['width']

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
        self.url = _data['url']
        self.proxy_url = _data.get('proxy_url', None)
        self.height = _data['height']
        self.width = _data['width']

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
        self.url = _data['url']
        self.height = _data['height']
        self.width = _data['width']

    @property
    def as_json(self):
        return {
            'url': self.url,
            'height': self.height,
            'width': self.width,
        }

class EmbedProvider(LitecordObject):
    def __init__(self, _data):
        self.name = _data['name']
        self.url = _data['url']

    @property
    def as_json(self):
        return {
            'name': self.name,
            'url': self.url
        }

class EmbedAuthor(LitecordObject):
    def __init__(self, _data):
        self.name = _data['name']
        self.url = _data['url']
        self.icon_url = _data['icon_url']
        self.proxy_icon_url = _data['proxy_icon_url']

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
        self.name = _data['name']
        self.value = _data['value']
        self.inline = _data['inline']

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
        self.embed_type = raw_embed['type']
        self.description = raw_embed['description']
        self.url = raw_embed['url']
        self.timestamp = datetime.datetime.now()
        self.color = raw_embed['color']

    @property
    def as_json(self):
        return {
            'title': self.title,
            'type': self.embed_type,
            'description': self.description,
            'url': self.url,
            'timestamp': dt_to_json(self.timestamp),
            'color': self.color,
        }
