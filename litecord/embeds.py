import datetime
import logging

from .objects import LitecordObject

log = logging.getLogger(__name__)

class EmbedFooter(LitecordObject):
    pass

class EmbedImage(LitecordObject):
    pass

class EmbedThumbnail(LitecordObject):
    pass

class EmbedVideo(LitecordObject):
    pass

class EmbedProvider(LitecordObject):
    pass

class EmbedAuthor(LitecordObject):
    pass

class EmbedField(LitecordObject):
    pass

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
