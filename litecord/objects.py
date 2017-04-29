from .utils import strip_user_data

class LitecordObject:
    def __init__(self, server):
        self.server = server

class Guild(LitecordObject):
    def __init__(self, server):
        LitecordObject.__init__(self, server)
        self.members = []

class User(LitecordObject):
    def __init__(self, server, _user):
        LitecordObject.__init__(self, server)
        self._user = _user
        self.user_id = _user['id']

    @property
    def guilds(self):
        for guild in []:
            yield guild

    @property
    def as_json(self):
        return strip_user_data(self._user)

    @property
    def connection(self):
        for session_id in self.server.session_data:
            connection = self.server.session_data[session_id]
            if connection.identified:
                if connection.user['id'] == self.user_id:
                    return connection
        return None

class Member(LitecordObject, User):
    def __init__(self, server, _user):
        LitecordObject.__init__(self, server)
        User.__init__(self, server, _user)
        # self.guild = gulild
