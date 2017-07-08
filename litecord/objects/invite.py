from .base import LitecordObject


class Invite(LitecordObject):
    """An invite object.

    Parameters
    ----------
    server: :class:`LitecordServer`
        Server instance.
    _data: dict
        Raw invite data.

    Attributes
    ----------
    _data: dict
        Raw invite object.
    code: str
        Invite code.
    channel_id: int
        Channel's ID being reffered in this invite.
    channel: :class:`Channel`
        Channel being reffered in ``channel_id``. Can be :py:const:`None`.
    inviter_id: int
        User's ID who made the invite.
    inviter: :class:`User`
        User who made the invite. Can be :py:const:`None`.
    temporary: bool
        Flag if this invite is temprary or not.
    uses: int
        Uses this invite has. If the invite is infinite, this becomes ``-1``.
    iso_timestamp: str
        A ISO 8601 formatted string.
    infinite: bool
        Flag if this invite is infinite or not.
    expiry_timestamp: `datetime.datetime`
        If the invite is not infinite, this is the date when the invite will
        expire and be invalid.
        If not, this becomes :py:const:`None`.
    """

    __slots__ = ('_data', 'code', 'channel_id', 'channel', 'inviter_id', 'inviter'
        'temporary', 'uses', 'iso_timestamp', 'infinite', 'expiry_timestamp')

    def __init__(self, server, _data):
        super().__init__(server)
        self.server = server
        self._data = _data

        self.code = _data['code']
        self.channel_id = int(_data['channel_id'])

        self.channel = server.guild_man.get_channel(self.channel_id)
        if self.channel is None:
            log.warning("Orphan invite (channel)")

        guild = self.channel.guild

        self.inviter_id = int(_data['inviter_id'])
        self.inviter = guild.members.get(self.inviter_id)
        if self.inviter is None:
            log.warning("Orphan invite (inviter)")

        self.temporary = _data.get('temporary', False)

        self.uses = _data.get('uses', -1)

        self.iso_timestamp = _data.get('timestamp', None)
        self.infinite = True
        self.expiry_timestamp = None

        if self.iso_timestamp is not None:
            self.infinite = False
            self.expiry_timestamp = datetime.datetime.strptime(self.iso_timestamp, \
                "%Y-%m-%dT%H:%M:%S.%f")

    @property
    def valid(self):
        """Returns a boolean representing the validity of the invite"""
        if self.channel is None:
            return False

        if not self.infinite:
            now = datetime.datetime.now()

            if now.timestamp() > self.expiry_timestamp.timestamp():
                return False

        # check uses
        if self.uses == -1:
            return True

        if self.uses < 1:
            return False

        return True

    def use(self):
        """Returns a boolean on success/failure of using an invite"""
        if self.channel is None:
            return False

        if not self.infinite:
            now = datetime.datetime.now()

            if now.timestamp() > self.expiry_timestamp.timestamp():
                return False

        # check uses
        if self.uses == -1:
            return True

        if self.uses < 1:
            return False

        self.uses -= 1
        return True

    async def update(self):
        """Update an invite in the database."""
        res = await self.server.invite_db.replace_one({'code': self.code}, self.as_db)
        log.info(f"Updated {res.modified_count} invites")

    @property
    def sane(self):
        """Checks if an invite is sane."""
        return self.channel is not None

    @property
    def as_db(self):
        return {
            'code': self.code,
            'channel_id': str(self.channel_id),
            'timestamp': self.iso_timestamp,
            'uses': self.uses,
            'temporary': self.temporary,
            'unique': True,
        }

    @property
    def as_json(self):
        return {
            'code': self.code,
            'guild': self.channel.guild.as_invite,
            'channel': self.channel.as_invite,
            'inviter': self.inviter.as_invite,
        }


