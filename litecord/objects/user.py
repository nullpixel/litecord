import logging

from .base import LitecordObject
from ..utils import dt_to_json

log = logging.getLogger(__name__)

class User(LitecordObject):
    """A general user object.

    Parameters
    ----------
    server: :class:`LitecordServer`
        Server instance
    raw: dict
        Raw user data.

    Attributes
    ----------
    _raw: dict
        Raw user data.
    id: int
        Snowflake ID of this user.
    username: str
        User's username.
    discriminator: str
        User's discriminator.
    avatar_hash: str
        User's avatar hash, used to retrieve the user's avatar data.
    email: str
        User's email, can be :py:const:`None`
    admin: bool
        Flag that shows if the user is an admin user.
    bot: bool
        If this is a bot user.
    """

    __slots__ = ('_raw', 'id', 'username', 'discriminator', 'avatar_hash',
        'email', 'admin')

    def __init__(self, server, raw):
        super().__init__(server)
        self._raw = raw
        self.id = int(raw['user_id'])

        self.username = raw['username']
        self.discriminator = raw['discriminator']
        self.avatar_hash = raw['avatar']

        self.email = raw.get('email')
        self.admin = raw.get('admin', False)
        self.bot = raw.get('bot', False)

    def __str__(self):
        return f'{self.username}#{self.discriminator}'

    def __repr__(self):
        return f'<User id={self.id} name={self.username} discriminator={self.discriminator} ' \
               f'bot={self.bot} admin={self.admin}>'

    def __eq__(self, other):
        return isinstance(other, User) and other.id == self.id

    @property
    def guilds(self):
        """Yield all guilds a user is in."""
        for guild in self.guild_man.all_guilds():
            if self.id in guild.member_ids:
                yield guild

    @property
    def members(self):
        """Yield all members a user has attached."""
        for guild in self.guilds:
            yield guild.members[self.id]

    @property
    def as_json_private(self):
        """JSON version of the user object but with private info."""
        return {**self.as_json, **{
            'password': self._raw['password'],
            'verified': self._raw['verified'],
            'email': self._raw['email'],
        }}

    @property
    def as_json(self):
        """Remove sensitive data from `User._raw` and make it JSON serializable"""
        return {
            'id': str(self.id),
            'username': self.username,
            'discriminator': self.discriminator,
            'avatar': self.avatar_hash,
            'bot': self.bot,
            'mfa_enabled': False,
        }

    @property
    def connections(self):
        """Yield all connections that are related to this user."""
        for conn in self.server.get_connections(self.id):
            yield conn

    @property
    def online(self):
        """Returns boolean if the user has at least 1 connection attached to it"""
        return len(list(self.server.get_connections(self.id))) > 0

    async def dispatch(self, evt_name, evt_data):
        """Dispatch an event to all connections a user has.

        Parameters
        ----------
        evt_name: str
            Event name.
        evt_data: any
            Event data.

        Returns
        -------
        bool

        """
        log.debug(f"Dispatching {evt_name} to {self.id}")
        _conns = list(self.connections)
        if len(_conns) < 1:
            return False

        for conn in _conns:
            try:
                await conn.dispatch(evt_name, evt_data)
                log.debug(f"Dispatched to {conn.session_id!r}")
            except:
                log.debug(f"Failed to dispatch event to {conn.session_id!r}")

        return True


def default_game():
    return {
        'status': 'online',
        'type': 0,
        'name': None,
        'url': None,
    }


class Presence:
    """A presence object.

    Presence objects are used to signal clients that someone is playing a game,
    or that someone went Online, Idle/AFK or DnD(Do not Disturb).

    Parameters
    ----------
    guild: :class:`Guild`
        Guild that this presence object relates to.
    user: :class:`User`
        User that this presence object relates to.
    status: dict, optional
        Status data to load into the presence object.

    Attributes
    ----------
    game: dict
        The currently playing game/status.
    user: :class:`User`
        The user that this presence object is linked to.
    guild: :class:`Guild`
        Guild that this presence object relates to.
    """

    __slots__ = ('game', 'user', 'guild')

    def __init__(self, guild, user, status):
        self.game = None
        self._update(guild, user, status)

    def _update(self, guild, user, status):
        _base = self.game
        if self.game is None:
            _base = default_game()
        
        if status is None:
            status = {}

        self.game = {**_base, **status}

        self.user = user
        self.guild = guild

        if self.game['status'] not in ('online', 'offline', 'idle', 'dnd'):
            log.warning(f'Presence for {self.user!r} with unknown status')

    def __repr__(self):
        return f'<Presence user={self.user!s} status={self.game["status"]!r} game.name={self.game["name"]}>'

    @property
    def as_json(self):
        return {
            # Discord sends an incomplete user object with all optional fields(excluding id)
            # we are lazy, so we send the same user object you'd receive in other normal events :^)
            'user': self.user.as_json,
            'guild_id': str(self.guild.id),
            'roles': [],
            'game': {
                'type': self.game.get('type'),
                'name': self.game.get('name'),
                'url': self.game.get('url'),
            },
            'status': self.game.get('status'),
        }
