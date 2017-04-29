import logging
from .utils import strip_user_data

log = logging.getLogger(__name__)

class LitecordObject:
    def __init__(self, server):
        self.server = server

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

class Channel(LitecordObject):
    def __init__(self, server, _channel):
        LitecordObject.__init__(self, server)
        self._data = _channel

class Guild(LitecordObject):
    def __init__(self, server, _guild_data):
        LitecordObject.__init__(self, server)
        self._data = _guild_data

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

        self.owner_id = _guild_data['owner_id']

    @property
    def get_online_members(self):
        '''Get all members that have a connection'''
        for member in self.members:
            if member.connection is not None:
                yield member
