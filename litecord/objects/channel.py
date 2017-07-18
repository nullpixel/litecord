import logging

from .base import LitecordObject
from ..basics import CHANNEL_TO_INTEGER
from ..snowflake import _snowflake

log = logging.getLogger(__name__)

class BaseChannel(LitecordObject):
    """A general base channel object.

    Parameters
    ----------
    server: :class:`LitecordServer`
        Server instance.
    _channel: dict
        Raw channel data.
    guild: :class:`Guild`, optional
        Guild that this channel refers to.

    Attributes
    ----------
    _data: dict
        Raw channel data.
    id: int
        The channel's snowflake ID.
    guild_id: int
        The guild's ID this channel is in.
    guild: :class:`Guild`
        The guild that this channel refers to, can be :py:const:`None`.
    name: str
        Channel's name.
    type: int
        Channel's type.
    str_type: str
        Channel's type as a string. Usually it is ``"text"``.
    position: int
        Channel's position on the guild, channel position starts from 0.
    is_private: bool
        Should be False.
    is_default: bool
        If this channel is the default for the guild.
    """

    __slots__ = ('_raw', 'id', 'guild_id', 'guild', 'name', 'type', 'str_type',
        'position', 'is_private', 'is_default')

    def __init__(self, server, _channel, guild=None):
        super().__init__(server)
        self._raw = _channel

        self.id = int(_channel['channel_id'])
        self.guild_id = int(_channel['guild_id'])

        self.guild = guild
        if guild is None:
            self.guild = self.guild_man.get_guild(self.guild_id)

        if self.guild is None:
            log.warning('Creating an orphaned channel(no guild found)')

        self.str_type = _channel['type']
        self.type = CHANNEL_TO_INTEGER[_channel['type']]
        self._update(self.guild, _channel)

    def _update(self, guild, raw):
        self.guild = guild
        self.name = raw['name']
        self.position = raw['position']
        self.is_private = False
        self.is_default = self.id == self.guild_id

    @property
    def __eq__(self, other):
        return isinstance(other, BaseChannel) and other.id == self.id

    @property
    def watchers(self):
        """Yields all :class:`Member` who are online and can watch the channel."""
        for member in self.guild.online_members:
            #if member.channel_perms[self.id].READ_MESSAGES: yield member
            yield member

    async def dispatch(self, evt_name, evt_data):
        """Dispatch an event to all channel watchers."""
        dispatched = 0
        for member in self.guild.viewers:
            if (await member.dispatch(evt_name, evt_data)):
                dispatched += 1

        log.debug(f'Dispatched {evt_name} to {dispatched} channel watchers')

        return dispatched

    async def delete(self):
        """Delete a channel"""
        return await self.guild_man.delete_channel(self)

    @property
    def as_invite(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'type': self.type,
        }


class TextChannel(BaseChannel):
    """Represents a text channel.

    Attributes
    ----------
    topic: str
        Channel topic/description.
    last_message_id: int
        The last message created in the channel,
        it is only updated when you get the channel
        through :meth:`GuildManager.get_channel`.

    """

    __slots__ = ('topic', 'last_message_id')

    def __init__(self, server, raw_channel, guild=None):
        super().__init__(server, raw_channel, guild)
        self.last_message_id = 0
        self._update(raw_channel)

    def _update(self, raw):
        BaseChannel._update(self, raw)
        self.topic = raw['topic']

    def get_message(self, message_id):
        """Get a single message from a channel."""
        try:
            m = self.server.guild_man.get_message(message_id)
            if m.channel.id == self.id:
                return m
        except AttributeError:
            pass
        return None

    async def last_messages(self, limit=50):
        """Get the last messages from a text channel.

        Returns
        -------
        list: list of :class:`Message`
            Ordered(by time) list of message objects.
        """
        res = []
        cursor = self.server.message_coll.find({'channel_id': self.id}).sort('message_id')

        for raw_message in reversed(await cursor.to_list(length=limit)):
            if len(res) > limit: break
            m_id = raw_message['message_id']
            raw_message['id'] = m_id

            if m_id in self.guild_man.messages:
                res.append(self.guild_man.messages[m_id])
            else:
                m = Message(self.server, self, raw_message)
                self.guild_man.messages[m_id] = m

                res.append(m)

        return res

    async def from_timestamp(self, timestamp):
        """Get all messages from the timestamp to latest"""
        # TODO: THIS IS INNEFICIENT. WE NEED TO YIELD IDFK HOW
        # BECAUSE THIS IS ASYNCIO AAAA
        as_snowflake = _snowflake(timestamp)
        mc = self.server.message_coll
        cur = mc.find({'channel_id': self.id, 'message_id': {'$gt': as_snowflake}}).sort('message_id')
        return (await cur.to_list(length=None))

    async def delete_many(self, message_ids, bulk=False):
        """Delete many messages from a channel.
        
        Fires `MESSAGE_DELETE` for each deleted message.

        Parameters
        ----------
        message_ids: List[int]
            Message IDs to be deleted from the channel
        build: bool, optional
            If thie is going to fire a `MESSAGE_DELETE_BULK` instead of `MESSAGE_DELETE`.
            Defaults to :py:meth:`False`.

        Returns
        -------
        None
        """
        message_ids = sorted(message_ids, reverse=True)
        in_bulk = []

        for message_id in message_ids:
            r = await self.server.message_coll.delete_many({'channel_id': self.id, 'message_id': message_id})
            if r.deleted_count < 1:
                continue

            if not bulk:
                await self.dispatch('MESSAGE_DELETE', {
                    'channel_id': self.id,
                    'message_id': message_id,
                })
            else:
                in_bulk.append(message_id)

        if bulk:
            await self.dispatch('MESSAGE_DELETE_BULK', {
                'channel_id': self.id,
                'ids': in_bulk,
            })

    async def edit(self, payload: dict):
        """Edit a text channel with a text channel edit payload.
        
        Parameters
        ----------
        payload: dict
            Text channel edit payload.

        Returns
        -------
        A new :class:`TextChannel` object with the edited data
        """
        return await self.guild_man.edit_channel(payload)

    @property
    def as_json(self):
        return {
            'id': str(self.id),
            'guild_id': str(self.guild_id),
            'name': self.name,
            'type': self.type,
            'position': self.position,
            'is_private': self.is_private,
            'permission_overwrites': [],
            'topic': self.topic,
            'last_message_id': str(self.last_message_id),
        }


