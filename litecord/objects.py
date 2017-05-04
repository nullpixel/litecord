import logging
import datetime
from .utils import strip_user_data, dt_to_json
from .snowflake import snowflake_time

log = logging.getLogger(__name__)

class LitecordObject:
    def __init__(self, server):
        self.server = server

    @property
    def guild_man(self):
        # This property is needed for things to work
        # since guild_man is None when initializing databases
        return self.server.guild_man

class Presence:
    def __init__(self, user, game=None, guild_id=None):
        self.game = game
        self.user = user
        self.guild_id = guild_id

    @property
    def as_json(self):
        return {
            'user': self.user.as_json,
            'roles': [],
            'game': self.game or None,
            'guild_id': self.guild_id,
            'status': 'online',
        }

class User(LitecordObject):
    def __init__(self, server, _user):
        LitecordObject.__init__(self, server)
        self._user = _user
        self.id = _user['id']

    @property
    def guilds(self):
        '''Get all guilds a user is in'''
        for guild in self.guild_man.all_guilds():
            if self.id in guild.member_ids:
                yield guild

    @property
    def as_json(self):
        '''Return the user as ready for JSON dump'''
        return strip_user_data(self._user)

    @property
    def connection(self):
        '''Get the user's `Connection` if any'''
        for session_id in self.server.sessions:
            connection = self.server.sessions[session_id]
            if connection.identified:
                if connection.user['id'] == self.id:
                    return connection
        return None

class Member(LitecordObject):
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
    '''
    Channel - represents a Text Channel
    '''
    def __init__(self, server, _channel):
        LitecordObject.__init__(self, server)
        self._data = _channel
        self.id = _channel['id']
        self.guild_id = _channel['guild_id']
        self.name = _channel['name']
        self.type = _channel['type']
        self.position = _channel['position']
        self.is_private = False
        self.topic = _channel['topic']

        # TODO: messages
        self.last_message_id = -1

    @property
    def as_json(self):
        return {
            'id': self.id,
            'guild_id': self.guild_id,
            'name': self.name,
            'type': self.type,
            'position': self.position,
            'is_private': self.is_private,
            'permission_overwrites': [],
            'topic': self.topic,
            'last_message_id': self.last_message_id,

            # NOTE: THIS IS VOICE, WON'T BE USED.
            #'bitrate': self.bitrate,
            #'user_limit': self.user_limit,
        }

class Guild(LitecordObject):
    def __init__(self, server, _guild_data):
        LitecordObject.__init__(self, server)
        self._data = _guild_data
        self.id = _guild_data['id']
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

            channel = Channel(server, channel_data)
            self.channels[channel_id] = channel

        # list of snowflakes
        self.member_ids = _guild_data['members']
        self.members = {}

        for member_id in self.member_ids:
            user = self.server.get_user(member_id)
            if user is None:
                log.warning(f"user {member_id} not found")
            member = Member(server, self, user)
            self.members[member_id] = member

        self.large = len(self.members) > 100
        self.member_count = len(self.members)
        self.presences = []

    @property
    def online_members(self):
        '''Get all members that have a connection'''
        for member_id in self.members:
            member = self.members[member_id]
            if member.user.connection is not None:
                yield member

    @property
    def as_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'icon': self.icons['icon'],
            'splash': self.icons['splash'],
            'owner_id': self.owner_id,
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

            # those events are only in GUILD_CREATE
            # but we can send them anyways :DDDDDD

            'joined_at': dt_to_json(self.created_at),
            'large': self.large,
            'unavailable': False,
            'member_count': self.member_count,
            'voice_states': [],

            # arrays of stuff
            'members': [self.members[member_id].as_json for member_id in self.members],
            'channels': [self.channels[channel_id].as_json for channel_id in self.channels],

            'presences': [self.server.presence.get_presence(member.id).as_json \
                for member in self.online_members],
        }

class Message:
    def __init__(self, server, channel, user, _message_data):
        LitecordObject.__init__(self, server)
        self._data = _message_data

        self.id = _message_data['id']
        self.timestamp = datetime.datetime.fromtimestamp(snowflake_time(self.id))

        self.channel = channel
        self.channel_id = channel.id

        self.user = user
        self.member = self.channel.server.members.get(self.user.id)

        if self.member is None:
            log.warning("Message being created with invalid userID")

        self.content = _message_data['content']
        self.edited_at = None

    def edit(self, new_content, timestamp=None):
        if timestamp is None:
            timestamp = datetime.datetime.now()

        self.edited_at = timestamp
        self.content = new_content

    @property
    def as_json(self):
        return {
            'id': str(self.id),
            'channel_id': str(self.channel_id),
            'author': self.user.as_json,
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
