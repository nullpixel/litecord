import logging
from .objects import Guild, Message
from .snowflake import get_snowflake

log = logging.getLogger(__name__)

class GuildManager:
    """Manage guild, channel and message data.

    Attributes:
        server: A `LitecordServer` instance
        guild_db: A direct reference to the server's guild database
        message_db: a direct reference to the server's message database
        guilds: A dictionary, list of all available guilds
        channels: Dictionary, list of all available channels
    """
    def __init__(self, server):
        self.server = server
        self.guild_db = server.db['guilds']
        self.message_db = server.db['messages']

        self.guilds = {}
        self.channels = {}
        self.messages = {}

    def get_guild(self, guild_id):
        """Get a `Guild` object by its ID."""
        guild_id = int(guild_id)
        return self.guilds.get(guild_id)

    def get_channel(self, channel_id):
        """Get a `Channel` object by its ID."""
        channel_id = int(channel_id)
        return self.channels.get(channel_id)

    def get_message(self, message_id):
        """Get a `Message` object by its ID."""
        message_id = int(message_id)
        return self.messages.get(message_id)

    def get_guilds(self, user_id):
        """Get a list of all `Guild`s a user is on."""
        user_id = int(user_id)
        return [self.guilds[guild_id] for guild_id in self.guilds \
            if user_id in self.guilds[guild_id].member_ids]

    def all_guilds(self):
        """Yield all available guilds."""
        for guild_id in self.guilds:
            yield self.guilds[guild_id]

    def all_messages(self, limit=500):
        """Yield `limit` messages, with the 1st being the most recent one."""
        sorted_ids = sorted(self.messages.keys(), reverse=True)[:limit]

        for message_id in sorted_ids:
            message = self.messages[message_id]
            yield message

    async def new_message(self, channel, author, raw):
        """Create a new message and put it in the database.

        Dispatches MESSAGE_CREATE events to respective clients.
        Returns a `Message` object.
        """

        message_id = get_snowflake()
        message = Message(self.server, channel, raw)

        self.messages[message_id] = message

        # TODO: store messages
        for member in channel.guild.online_members:
            conn = member.connection
            await conn.dispatch('MESSAGE_CREATE', message.as_json)

        return message

    def init(self):
        for guild_id in self.guild_db:
            guild_data = self.guild_db[guild_id]

            guild = Guild(self.server, guild_data)
            self.guilds[guild.id] = guild

            for channel in guild.all_channels():
                self.channels[channel.id] = channel

        # load messages from database
        for message_id in self.message_db:
            message_data = self.message_db[message_id]
            message_data['id'] = message_id
            channel = self.get_channel(message_data['channel_id'])

            message = Message(self.server, channel, message_data)
            self.messages[message.id] = message

        return True
