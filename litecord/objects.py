import logging
import datetime
from .utils import strip_user_data, dt_to_json
from .snowflake import snowflake_time

log = logging.getLogger(__name__)

class LitecordObject:
    """A general Litecord object

    Attributes:
        server: A `LitecordServer` instance

    Properties:
        guild_man: Returns the server's `GuildManager`
    """
    def __init__(self, server):
        self.server = server

    @property
    def guild_man(self):
        # This property is needed for things to work
        # since guild_man is None when initializing databases
        return self.server.guild_man

    @property
    def as_json(self):
        """Return a JSON serializable object representing itself.

        NOTE: it is recommended to not give sensitive information through `as_json`
            as it is usually used to send the object to a client.
        """
        raise NotImplemented

    def iter_json(self, indexable):
        """Get all objects from an indexable, in JSON serializable form"""
        return [indexable[index].as_json for index in indexable]


class Presence:
    """A presence object.

    Presence objects are used to signal clients that someone is playing a game,
    or that someone went Online, Idle/AFK or DnD(Do not Disturb).

    Attributes:
        game: A dictionary representing the currently playing game/status.
        user: The user that this presence object is linked to.
        guild_id: An optional attribute, only used in `Presence.as_json`
    """
    def __init__(self, guild, user, status=None):
        _default = {
            'status': 'online',
            'type': 0,
            'name': None,
            'url': None,
        }

        # merge the two, with game overwriting _default
        self.game = {**_default, **status}
        self.user = user
        self.guild = guild

        if self.game['status'] not in ('online', 'offline', 'idle'):
            log.warning(f'Presence for {self.user!r} with unknown status')

    def __repr__(self):
        return f'Presence({self.user!s}, {self.game["status"]!r}, {self.game["name"]!r})'

    @property
    def as_json(self):
        return {
            # Discord sends an incomplete user object with all optional fields(excluding id)
            # we are lazy, so we send the same user object you'd receive in other normal events :^)
            'user': self.user.as_json,
            'guild_id': str(self.guild.id),
            'roles': [],
            'game': {
                'type': self.game.get('type'),
                'name': self.game.get('name'),
                'url': self.game.get('url'),
            },
            'status': self.game.get('status'),
        }


class User(LitecordObject):
    """A general user object.

    Attributes:
        _data: raw user data.
        id: The user's snowflake ID.
        username: A string denoting the user's username
        discriminator: A string denoting the user's discriminator
    """
    def __init__(self, server, _data):
        LitecordObject.__init__(self, server)
        self._data = _data
        self.id = int(_data['id'])
        self.username = self._data['username']
        self.discriminator = self._data['discriminator']

    def __str__(self):
        return f'{self.username}#{self.discriminator}'

    def __repr__(self):
        return f'User({self.id}, {self.username}#{self.discriminator})'

    @property
    def guilds(self):
        """Yield all guilds a user is in."""
        for guild in self.guild_man.all_guilds():
            if self.id in guild.member_ids:
                yield guild

    @property
    def as_json(self):
        """Remove sensitive data from `User._data` and make it JSON serializable"""
        return strip_user_data(self._data)

    @property
    def connection(self):
        """Return the user's `Connection` object, if possible

        Returns `None` when a client is offline/no connection attached.
        """
        for session_id in self.server.sessions:
            connection = self.server.sessions[session_id]
            if connection.identified:
                if connection.user.id == self.id:
                    return connection
        return None


class Member(LitecordObject):
    """A general member object.

    A member is linked to a guild.

    Attributes:
        user: A `User` instance representing this member.
        guild: A `Guild` instance which the user is on.
        id: The member's snowflake ID, Equals to the user's ID.
        nick: A string denoting the member's nickname, can be `None`
            if no nickname is set.
        joined_at: A `datetime.datetime` object representing the date
            the member joined the guild.
    """
    def __init__(self, server, guild, user):
        LitecordObject.__init__(self, server)
        self.user = user
        self.guild = guild

        self.id = self.user.id
        self.nick = None
        self.joined_at = datetime.datetime.now()
        self.voice_deaf = False
        self.voice_mute = False

    @property
    def connection(self):
        return self.user.connection

    @property
    def as_json(self):
        return {
            'user': self.user.as_json,
            'nick': self.nick,
            'roles': [],
            'joined_at': dt_to_json(self.joined_at),
            'deaf': self.voice_deaf,
            'mute': self.voice_mute,
        }


class Channel(LitecordObject):
    """A general text channel object

    Attributes:
        _data: Raw channel data.
        id: The channel's snowflake ID.
        guild_id: The guild's ID this channel is in.
        guild: A `Guild` object, follows the same as `guild_id`.
        name: A string denoting the channel's name.
        type: A string representing the channel's type, usually it is `"text"`.
        position: Integer starting from 0. Channel's position on the guild.
        is_private: Boolean, should be False.
        topic: A string, the channel topic/description.

        TODO: last_message_id: A snowflake, the last message in the channel.
    """
    def __init__(self, server, _channel, guild=None):
        LitecordObject.__init__(self, server)
        self._data = _channel
        self.id = int(_channel['id'])
        self.guild_id = int(_channel['guild_id'])

        if guild is None:
            self.guild = self.guild_man.get_guild(self.guild_id)
        else:
            self.guild = guild

        if self.guild is None:
            log.warning("Creating an orphaned Channel")

        self.name = _channel['name']
        self.type = _channel['type']
        self.position = _channel['position']
        self.is_private = False
        self.topic = _channel['topic']

        # TODO: messages
        self.last_message_id = 0

    def get_message(self, message_id):
        """Get a single message from a channel."""
        try:
            m = self.server.guild_man.get_message(message_id)
            if m.channel.id == self.id:
                return m
        except AttributeError:
            pass
        return None

    async def last_messages(self, limit=50):
        """Get the last messages from a channel.

        Returns an ordered list of `Message` objects.
        """
        res = []
        cursor = self.server.message_db.find({'channel_id': self.id}).sort('message_id')

        for raw_message in reversed(await cursor.to_list(length=limit)):
            if len(res) > limit: break
            m_id = raw_message['message_id']

            if m_id in self.guild_man.messages:
                res.append(self.guild_man.messages[m_id])
            else:
                m = Message(self.server, self, raw_message)
                self.guild_man.messages[m_id] = m

                res.append(m)

        return res

    @property
    def as_json(self):
        return {
            'id': str(self.id),
            'guild_id': str(self.guild_id),
            'name': self.name,
            'type': self.type,
            'position': self.position,
            'is_private': self.is_private,
            'permission_overwrites': [],
            'topic': self.topic,
            'last_message_id': str(self.last_message_id),

            # NOTE: THIS IS VOICE, WON'T BE USED.
            #'bitrate': self.bitrate,
            #'user_limit': self.user_limit,
        }


class Guild(LitecordObject):
    """A general guild.

    Attributes:
        _data: Raw guild data.
        _channel_data: Raw channel data for the guild.

        id: The guild's snowflake ID.
        name: The guild's name.
        icons: A dictionary with two keys: `"icon"` and `"splash"`
        created_at: `datetime.datetime` object, the guild's creation date
        owner_id: A snowflake, the guild owner's ID.
        TODO: region: A string.
        TODO: roles: A list of `Role` objects.
        TODO: emojis: A list of `Emoji` objects.
        features: A list of strings denoting the features this guild has.
        channels: A dictionary relating channel ID to its `Channel` object.
        member_ids: A list of snowflakes, contains the IDs for all the guild's members.
        members: A dictionary relating user ID to its `Member` object.
        large: A boolean, `True` if the gulid has more than 150 members.
        member_count: An integer, the number of members in this guild.
    """
    def __init__(self, server, _guild_data):
        LitecordObject.__init__(self, server)
        self._data = _guild_data
        self.id = int(_guild_data['id'])
        self.name = _guild_data['name']
        self.icons = {
            'icon': '',
            'splash': '',
        }

        creation_timestamp = snowflake_time(self.id)
        self.created_at = datetime.datetime.fromtimestamp(creation_timestamp)

        self.owner_id = _guild_data['owner_id']
        self.region = _guild_data['region']
        self.roles = []
        self.emojis = []
        self.features = _guild_data['features']

        self._channel_data = _guild_data['channels']
        self.channels = {}

        for channel_id in self._channel_data:
            channel_data = _guild_data['channels'][channel_id]
            channel_data['guild_id'] = self.id
            channel_data['id'] = channel_id

            channel = Channel(server, channel_data, self)
            self.channels[channel_id] = channel

        # list of snowflakes
        self.member_ids = [int(member_id) for member_id in _guild_data['members']]
        self.members = {}

        for member_id in self.member_ids:
            member_id = int(member_id)

            user = self.server.get_user(member_id)
            if user is None:
                log.warning(f"user {member_id} not found")
            member = Member(server, self, user)
            self.members[member_id] = member

        self.large = len(self.members) > 150
        self.member_count = len(self.members)

    def all_channels(self):
        """Yield all channels from a guild"""
        for channel in self.channels.values():
            yield channel

    def all_members(self):
        """Yield all members from a guild"""
        for member in self.members.values():
            yield member

    @property
    def online_members(self):
        """Yield all members that have an identified connection"""
        for member in self.members.values():
            conn = member.user.connection
            if conn is not None:
                if conn.identified:
                    yield member

    @property
    def presences(self):
        """Returns a list of `Presence` objects for all online members."""
        return [self.server.presence.get_presence(self.id, member.id).as_json \
            for member in self.online_members]

    @property
    def as_json(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'icon': self.icons['icon'],
            'splash': self.icons['splash'],
            'owner_id': str(self.owner_id),
            'region': self.region,

            # voice things aka NOT USABLE
            'afk_channel_id': '6666666',
            'afk_timeout': -1,

            # TODO: how are these supposed to even work?
            'embed_enabled': None,
            'embed_channel_id': None,

            'verification_level': 0, # TODO
            'default_message_notifications': -1, # TODO
            'roles': self.roles,
            'emojis': self.emojis,
            'features': self.features,
            'mfa_level': -1, # TODO

            # those fields are only in the GUILD_CREATE event
            # but we can send them anyways :')
            # usually clients ignore this, so we don't need to worry

            'joined_at': dt_to_json(self.created_at),
            'large': self.large,
            'unavailable': False,
            'member_count': self.member_count,
            'voice_states': [],

            # arrays of stuff
            'members': self.iter_json(self.members),
            'channels': self.iter_json(self.channels),
            'presences': self.presences,
        }


class Message:
    """A general message object.

    Attributes:
        _data: Raw message data.
        id: The message's snowflake ID.
        author_id: The message author's snowflake ID.
        channel_id: The message channel's snowflake ID.

        timestamp: A `datetime.datetime` object, the message's creation time.
        channel: A `Channel` object, which channel the message comes from.
        author: A `User` object, the user that made the message, can be `None`.
        member: A `Member` object, the member that made the message, can be `None`.
        content: A string, the message content.
        edited_at: If the message was edited, this is set to a
            `datetime.datetime` representing the time at which the message was edited.
    """
    def __init__(self, server, channel, _message_data):
        LitecordObject.__init__(self, server)
        self._data = _message_data

        self.id = int(_message_data['id'])
        self.author_id = int(_message_data['author_id'])
        self.channel_id = channel.id

        self.timestamp = datetime.datetime.fromtimestamp(snowflake_time(self.id))

        self.channel = channel
        self.author = self.server.get_user(self.author_id)
        self.member = self.channel.guild.members.get(self.author_id)

        if self.member is None:
            log.warning("Message being created with invalid userID [member not found]")

        self.content = _message_data['content']
        self.edited_at = None

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
            'edited_timestamp': self.edited_at or None,
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
