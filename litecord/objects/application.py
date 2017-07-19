
class Application:
    def __init__(self, owner, raw):
        self.id = raw['app_id']
        self.owner_id = raw['owner_id']

    def _update(self, owner, raw):
        self._raw = raw
        self.owner = owner
        self.token = raw['token']
        self.raw_user = raw['user']

    @property
    def as_json(self):
        return {
            'id': str(self.id),
            'owner_id': str(self.owner_id),
            'owner': self.owner.as_json,
            'token': self.token,
            'raw_user': self.raw_user,
        }

