from .base import LitecordObject

class Emoji(LitecordObject):
    def __init__(self, server, guild, raw):
        super().__init__(server)
        self._raw = raw
        self.id = int(raw['emoji_id'])

        self._update(guild, raw)

    def _update(self, guild, raw):
        self.guild = guild

        self.name = raw['name']
        self.role_ids = raw['role_ids']
        self.roles = []

        for role_id in self.role_ids:
            role = self.server.get_role(role_id)
            self.roles.append(role)

        self.require_colons = raw['require_colons']
        self.managed = raw['managed']

    @property
    def as_json(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'roles': self.role_ids,
            'require_colons': self.require_colons,
            'managed': self.managed,
        }

