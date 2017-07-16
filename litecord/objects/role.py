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

    def __init__(self, server, guild, _raw):
        super().__init__(server)
        self._raw = raw

        self.id = int(_raw['role_id'])
        self.guild = guild

        self.is_default = self.guild.id == self.id

        self._update(raw)

    def _update(self, raw):
        rg = raw.get
        self.name = raw.get('name') or '@everyone'

        # specific role data
        self.color = rg('color', 0)
        self.hoist = rg('hoisted', False)
        self.position = rg('position', 0)
        self.permissions = rg('permissions', 0)
        self.managed = False
        self.mentionable = rg('mentionable', False)

    def __repr__(self):
        return f'<Role id={self.id} name={self.name!r} color={self.color} hoist={self.hoist}' \
                f' permissions={self.permissions}>'

    @property
    def as_db(self):
        return {**self.as_json, **{'id': self.id}}

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

