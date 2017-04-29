
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
    def connection(self):
        for session_id in self.server.session_data:
            connection = self.server.session_data[session_id]
            if conneciton.identified:
                return connection
