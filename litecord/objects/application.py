
class Application:
    def __init__(self, owner, raw):
        self.id = raw['app_id']
        self.owner_id = raw['owner_id']
        self._update(owner, raw)

    def _update(self, owner, raw):
        self._raw = raw
        self.owner = owner
        self.name = raw['name']
        self.description = raw.get('description')

    @property
    def as_json(self):
        return {
            'id': str(self.id),
            'owner_id': str(self.owner_id),
            'description': self.description,
            'name': self.name,
            'owner': self.owner.as_json,
        }

