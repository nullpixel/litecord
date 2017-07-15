import logging
import datetime

from ..snowflake import snowflake_time

class LitecordObject:
    """A general Litecord object.

    Attributes
    ----------
    server: :class:`LitecordServer`
        Server instance
    """
    def __init__(self, server):
        self.server = server

    def __eq__(self, other):
        if not (getattr(other, 'id', False) and getattr(self, 'id', False)):
            raise TypeError("Can't compare things without id attribute")

        return other.id == self.id

    @property
    def guild_man(self):
        """The server's :class:`GuildManager`."""
        # This property is needed for things to work
        # since guild_man is None when initializing databases
        return self.server.guild_man

    @property
    def as_db(self):
        """Get a version of the object to be inserted into the database."""
        raise NotImplementedError('This instance didn\'t implement as_db')

    @property
    def as_json(self):
        """Return a JSON serializable object representing itself.

        NOTE: it is recommended to not give sensitive information through `as_json`
            as it is usually used to send the object to a client.
        """
        raise NotImplementedError('This instance didn\'t implement as_json')

    def to_timestamp(self, snowflake):
        ts = snowflake_time(snowflake)
        return datetime.datetime.fromtimestamp(ts)

    def iter_json(self, indexable):
        """Get all objects from an indexable, in JSON serializable form"""
        return [indexable[index].as_json for index in indexable]

