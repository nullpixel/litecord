import datetime

from .base import LitecordObject
from ..snowflake import snowflake_time


class Message(LitecordObject):
    """A general message object.

    Parameters
    ----------
    server: :class:`LitecordServer`
        Server instance.
    channel: :class:`Channel`
        Channel that this message comes from.
    _message_data: dict
        Raw message data.

    Attributes
    ----------
    _data: dict
        Raw message data.
    id: int
        Message's snowflake ID.
    author_id: int
        Message author's snowflake ID.
    channel_id: int
        Message channel's snowflake ID.
    timestamp: `datetime.datetime`
        Message's creation time.
    channel: :class:`Channel`
        Channel where this message comes from.
    author: :class:`User`
        The user that made the message, can be :py:const:`None`.
    member: :class:`Member`
        Member that made the message, can be :py:const:`None`..
    content: str
        Message content.
    edited_at: `datetime.datetime`
        Default is :py:const:`None`.
        If the message was edited, this is set to the time at which this message was edited.
    """

    __slots__ = ('_data', 'id', 'author_id', 'channel_id', 'timestamp', 'channel',
        'author', 'member', 'content', 'edited_at')

    def __init__(self, server, channel, _message_data):
        super().__init__(server)
        self._data = _message_data

        self.id = int(_message_data['id'])
        self.author_id = int(_message_data['author_id'])
        if channel is None:
            log.warning(f"Orphaned message {self.id}")
            return

        self.channel_id = channel.id

        self.timestamp = datetime.datetime.fromtimestamp(snowflake_time(self.id))

        self.channel = channel
        self.author = self.server.get_user(self.author_id)
        self.member = self.channel.guild.members.get(self.author_id)

        if self.member is None:
            log.warning("Message being created with invalid userID [member not found]")

        self.content = _message_data['content']
        self.edited_at = _message_data.get('edited_timestamp', None)

    def edit(self, new_content, timestamp=None):
        """Edit a message object"""
        if timestamp is None:
            timestamp = datetime.datetime.now()

        self.edited_at = timestamp
        self.content = new_content

    @property
    def as_db(self):
        return {
            'message_id': int(self.id),
            'channel_id': int(self.channel_id),
            'author_id': int(self.author.id),

            'edited_timestamp': dt_to_json(self.edited_at),

            'content': str(self.content),
        }

    @property
    def as_json(self):
        return {
            'id': str(self.id),
            'channel_id': str(self.channel_id),
            'author': self.author.as_json,
            'content': self.content,
            'timestamp': dt_to_json(self.timestamp),
            'edited_timestamp': dt_to_json(self.edited_at),
            'tts': False,
            'mention_everyone': '@everyone' in self.content,

            'mentions': [], # TODO
            'mention_roles': [], # TODO?
            'attachments': [], # TODO
            'embeds': [], # TODO
            'reactions': [], # TODO
            'pinned': False, # TODO
            #'webhook_id': '',
        }
