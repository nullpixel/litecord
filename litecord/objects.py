import logging
import datetime
from .utils import strip_user_data, dt_to_json

log = logging.getLogger(__name__)

class LitecordObject:
    def __init__(self, server):
        self.server = server

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
        self.user_id = _user['id']

    @property
    def guilds(self):
        '''Get all guilds a user is in'''
        for guild in []:
            yield guild

    @property
    def as_json(self):
        '''Return the user as ready for JSON dump'''
        return strip_user_data(self._user)

    @property
    def connection(self):
        '''Get the user's `Connection` if any'''
        for session_id in self.server.session_data:
            connection = self.server.session_data[session_id]
            if connection.identified:
                if connection.user['id'] == self.user_id:
                    return connection
        return None

class Member(LitecordObject):
    def __init__(self, server, guild, user):
        LitecordObject.__init__(self, server)
        self.user = user
        self.guild = guild

        self.id = self.user['id']
        self.nick = None
        self.joined_at = datetime.datetime.now()
        self.voice_deaf = False
        self.voice_mute = False

    @property
    def as_json(self):
        return {
            'user': strip_user_data(self.user),
            'nick': self.nick,
            'roles': [],
            'joined_at': dt_to_json(self.joined_at),
            'deaf': self.voice_deaf,
            'mute': self.voice_mute,
        }

class Channel(LitecordObject):
    def __init__(self, server, _channel):
        LitecordObject.__init__(self, server)
        self._data = _channel

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

        self.owner_id = _guild_data['owner_id']
        self.region = _guild_data['region']
        self.roles = []
        self.emojis = []
        self.features = _guild_data['features']

        self._channel_data = _guild_data['channels']
        self.channels = {}

        for channel_id in self._channel_data:
            channel_data = _guild_data['channels'][channel_id]
            channel = Channel(server, channel_data)
            self.channels[channel_id] = channel

        # list of snowflakes
        self.member_ids = _guild_data['members']
        self.members = {}

        for member_id in self.member_ids:
            user = self.server.get_user(member_id)
            member = Member(server, self, user)
            self.members[member_id] = member

        self.large = len(self.members) > 100
        self.member_count = len(self.members)
        self.presences = []

    @property
    def online_members(self):
        '''Get all members that have a connection'''
        for member in self.members:
            if member.connection is not None:
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

            # only in GUILD_CREATE but we can send them in testing env
            # TODO: 'joined_at': self.created_at,
            'large': self.large,
            'unavailable': self.,
            'member_count': self.,
            'voice_states': [],

            # arrays of stuff
            'members': [self.members[member_id].as_json for member_id in self.members],
            'channels': [self.channels[channel_id].as_json for channel_id in self.channels],

            'presences': [self.server.presence.get_presence(member.id).as_json \
                for member in self.online_members],
        }
