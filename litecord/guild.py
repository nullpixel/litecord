import logging
import asyncio
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
        self.guild_db = server.guild_db
        self.message_db = server.message_db
        self.invite_db = server.invite_db

        self.guilds = {}
        self.channels = {}
        self.messages = {}
        self.invites = {}

    def get_guild(self, guild_id):
        """Get a `Guild` object by its ID."""
        guild_id = int(guild_id)
        return self.guilds.get(guild_id)

    def get_channel(self, channel_id):
        """Get a `Channel` object by its ID."""
        channel_id = int(channel_id)
        channel = self.channels.get(channel_id)
        if channel is None:
            return None

        async def _updater():
            # Update a channel's last_message_id property
            mlist = await channel.last_messages(1)
            try:
                m_id = mlist[0].id
            except:
                m_id = None
            channel.last_message_id = m_id

        asyncio.async(_updater())
        return channel

    def get_message(self, message_id):
        """Get a `Message` object by its ID."""
        message_id = int(message_id)
        return self.messages.get(message_id)

    def get_guilds(self, user_id):
        """Get a list of all `Guild`s a user is on."""
        user_id = int(user_id)
        return [self.guilds[guild_id] for guild_id in self.guilds \
            if user_id in self.guilds[guild_id].member_ids]

    def get_invite(self, invite_code):
        return self.invites.get(invite_code)

    def all_guilds(self):
        """Yield all available guilds."""
        for guild_id in self.guilds:
            yield self.guilds[guild_id]

    async def all_messages(self, limit=500):
        """Yield `limit` messages, with the 1st being the most recent one."""
        cursor = self.message_db.find().sort('message_id')

        for raw_message in reversed(await cursor.to_list(length=limit)):
            message = self.messages[raw_message['message_id']]
            yield message

    async def new_message(self, channel, author, raw):
        """Create a new message and put it in the database.

        Dispatches MESSAGE_CREATE events to respective clients.
        Returns a `Message` object.
        """

        message_id = get_snowflake()
        message = Message(self.server, channel, raw)

        result = await self.message_db.insert_one(message.as_db)
        log.info(f"Adding message with id {result.inserted_id!r}")

        self.messages[message.id] = message

        for member in channel.guild.online_members:
            conn = member.connection
            await conn.dispatch('MESSAGE_CREATE', message.as_json)

        return message

    async def delete_message(self, message):
        """Delete a message.

        Dispatches MESSAGE_DELETE events to respective clients.
        Returns `True` on success, `False` on failure.
        """

        result = await self.message_db.delete_one({'message_id': message.id})
        log.info(f"Deleted {result.deleted_count} messages")

        for member in message.channel.guild.online_members:
            conn = member.connection
            await conn.dispatch('MESSAGE_DELETE', {
                'id': str(message.id),
                'channel_id': str(message.channel.id),
            })

        return True

    async def reload_guild(self, guild_id):
        """Reload one guild.

        Used normally after a database update.
        This updates cache objects.
        """

        raw_guild = await self.guild_db.find_one({'id': str(guild_id)})

        guild = Guild(self.server, raw_guild)
        self.guilds[guild.id] = guild

        for channel in guild.all_channels():
            self.channels[channel.id] = channel

    async def new_guild(self, owner, payload):
        """Create a Guild.

        Dispatches GUILD_CREATE event to the owner of the new guild.
        Returns a `Guild` object.

        Arguments:
            owner: A `User` object representing the guild's owner.
            payload: A guild payload:
            {
                "name": "Name of the guild",
                "region": "guild voice region, ignored",
                "verification_level": TODO,
                "default_message_notifications": TODO,
                "roles": [List of role payloads],
                "channels": [List of channel payloads],
                "icon": "base64 128x128 jpeg image for the guild icon",
            }
        """

        conn = owner.connection
        if not conn:
            log.warning("User not connected through WS to do this action.")
            return None

        payload['owner_id'] = str(owner.id)
        payload['id'] = str(get_snowflake())
        payload['features'] = []
        payload['channels'].append({
            'id': str(payload['id']),
            'guild_id': str(payload['id']),
            'name': 'general',
            'type': 'text',
            'position': 0,
            'topic': '',
        })

        for raw_channel in payload['channels']:
            raw_channel['guild_id'] = payload['id']

        guild = Guild(self.server, payload)
        await self.guild_db.insert_one(payload)
        self.guilds[guild.id] = guild

        for channel in guild.all_channels():
            self.channels[channel.id] = channel

        await self.server.presence.status_update(guild, owner)
        await conn.dispatch('GUILD_CREATE', guild.as_json)

        return guild

    async def edit_message(self, message, payload):
        """Edit a message.

        Dispatches MESSAGE_UPDATE events to respective clients.
        Returns `True` on success, `False` on failure.
        """

        new_content = payload['content']
        message.edit(new_content)

        result = await self.message_db.replace_one({'message_id': message.id}, message.as_db)
        log.info(f"Updated {result.modified_count} messages")

        for member in message.channel.guild.online_members:
            conn = member.connection
            await conn.dispatch('MESSAGE_UPDATE', message.as_json)

        return True

    async def add_member(self, guild, user):
        """Adds a user to a guild.

        Dispatches GUILD_MEMBER_ADD to relevant clients.
        Returns `Member` on success, `None` on failure.
        """

        raw_guild = guild._data
        raw_guild['members'].append(str(user.id))

        result = await self.guild_db.replace_one({'id': str(guild.id)}, raw_guild)
        log.info(f"Updated {result.modified_count} guilds")

        await self.reload_guild(guild.id)
        guild = self.server.get_guild(guild.id)

        new_member = guild.members.get(user.id)
        if new_member is None:
            return None

        to_add = {'guild_id': str(guild.id)}
        payload = {**new_member.as_json, **add}

        await guild.dispatch_to_members('GUILD_MEMBER_ADD', payload)

        return new_member

    async def remove_member(self, guild, user):
        """Remove a user from a guild.

        Dispatches GUILD_MEMBER_REMOVE to relevant clients.
        """

        user_id = str(user.id)

        raw_guild = guild._data
        raw_guild['members'].remove(user_id)

        result = await self.guild_db.replace_one({'id': str(guild.id)}, raw_guild)
        log.info(f"Updated {result.modified_count} guilds")

        await self.reload_guild(guild.id)
        await guild.dispatch_to_members('GUILD_MEMBER_REMOVE', {
            'guild_id': str(guild.id),
            'user': user.as_json,
        })

    async def create_invite(self, user, channel):
        # TODO: something something permissions
        #if not channel.guild.permissions(user, MAKE_INVITE):
        # return None
        return None

    async def init(self):
        cursor = self.guild_db.find()
        guild_count = 0

        for raw_guild in reversed(await cursor.to_list(length=None)):
            guild = Guild(self.server, raw_guild)
            self.guilds[guild.id] = guild

            for channel in guild.all_channels():
                self.channels[channel.id] = channel
            guild_count += 1

        log.info(f'[guild] Loaded {guild_count} guilds')

        cursor = self.invite_db.find()
        invite_count = 0
        valid_invites = 0

        for raw_invite in (await cursor.to_list(length=None)):
            invite = Invite(self.server, raw_invite)

            if invite.valid:
                self.invites[invite.id] = invite
                valid_invites += 1

            invite_count += 1

        log.info(f'[guild] Loaded {valid_invites} valid out of {invite_count} invites')

        # load messages from database

        cursor = self.message_db.find().sort('message_id')
        message_count = 0

        for raw_message in reversed(await cursor.to_list(length=200)):
            raw_message['id'] = raw_message['message_id']
            channel = self.get_channel(raw_message['channel_id'])

            m = Message(self.server, channel, raw_message)
            self.messages[m.id] = m
            message_count += 1

        log.info(f'[guild] Loaded {message_count} messages')
