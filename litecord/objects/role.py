import discord
from .base import LitecordObject

Permissions = discord.Permissions

class Role(LitecordObject):
    """A role object.

    Parameters
    ----------
    server: :class:`LitecordServer`
        Server instance.
    guild: :class:`Guild`
        Guild that this role is from.
    raw: dict
        Raw role data.

    Attributes
    ----------
    _raw: dict
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
    permissions: ``discord.Permissions``
        Role permissions.
    perms: ``discord.Permissions``
        Same as :meth:`Role.permissions`
    managed: bool
        If this role is managed by a bot application, should be ``False``.
    mentionable: bool
        If this role can be mentioned by another users.
    """

    __slots__ = ('_data', 'id', 'guild', 'name', 'color', 'hoist', 'position',
        'position', 'permissions', 'managed', 'mentionable')

    def __init__(self, server, guild, raw):
        super().__init__(server)
        self._raw = raw
        self.id = int(raw['role_id'])
        self._update(guild, raw)

    def _update(self, guild, raw):
        rg = raw.get
        self.name = raw.get('name') or '@everyone'
        self.guild = guild
        self.is_default = self.guild.id == self.id

        # specific role data
        self.color = rg('color', 0)
        self.hoist = rg('hoisted', False)
        self.position = rg('position', 0)

        self.permissions = Permissions(rg('permissions', 0))
        self.perms = self.permissions

        self.managed = rg('managed', False)
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
            'permissions': self.permissions.value,
            'managed': self.managed,
            'mentionable': self.mentionable,
        }

