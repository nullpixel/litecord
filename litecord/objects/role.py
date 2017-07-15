from .base import LitecordObject


class Role(LitecordObject):
    """A role object.

    Parameters
    ----------
    server: :class:`LitecordServer`
        Server instance.
    guild: :class:`Guild`
        Guild that this role is from.
    _data: dict
        Raw role data.

    Attributes
    ----------
    _data: dict
        Raw role data.
    id: int
        Role ID
    guild: :class:`Guild`
        Guild that this role comes from.
    name: str
        Name of the role.
    color: int
        Role's color.
    hoist: bool
        If the role is hoisted. Hoisted roles means they'll appear seperately
        in the member list.
    position: int
        Role's position.
    permissions: int
        Role's permission number.
    managed: bool
        If this role is managed by a bot application, should be ``False``.
    mentionable: bool
        If this role can be mentioned by another users.
    """

    __slots__ = ('_data', 'id', 'guild', 'name', 'color', 'hoist', 'position',
        'position', 'permissions', 'managed', 'mentionable')

    def __init__(self, server, guild, _data):
        super().__init__(server)
        self._data = _data

        self.id = int(_data['role_id'])
        self.guild = guild

        if self.id == guild.id:
            self.name = '@everyone'
        else:
            self.name = _data['name']

        self.color = _data.get('color', 0)
        self.hoist = _data.get('hoisted', False)
        self.position = _data.get('position', 0)
        self.permissions = _data.get('permissions', 0)
        self.managed = False
        self.mentionable = _data.get('mentionable')

    @property
    def as_db(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'color': self.color,
            'hoist': self.hoist,
            'position': self.position,
            'permissions': self.permissions,
            'managed': self.managed,
            'mentionable': self.mentionable,
        }

    @property
    def as_json(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'color': self.color,
            'hoist': self.hoist,
            'position': self.position,
            'permissions': self.permissions,
            'managed': self.managed,
            'mentionable': self.mentionable,
        }

