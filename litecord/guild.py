import logging
import asyncio
import datetime

from .objects import Guild, Message, Invite
from .snowflake import get_snowflake, get_invite_code

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

        self.invi_janitor_task = self.server.loop.create_task(self.invite_janitor)

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
        await channel.dispatch('MESSAGE_CREATE', message.as_json)

        return message

    async def delete_message(self, message):
        """Delete a message.

        Dispatches MESSAGE_DELETE events to respective clients.
        Returns `True` on success, `False` on failure.
        """

        result = await self.message_db.delete_one({'message_id': message.id})
        log.info(f"Deleted {result.deleted_count} messages")

        await message.channel.dispatch('MESSAGE_DELETE', {
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

        await message.channel.dispatch('MESSAGE_UPDATE', message.as_json)
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

        await guild.dispatch('GUILD_MEMBER_ADD', payload)

        return new_member

    async def remove_member(self, guild, user):
        """Remove a user from a guild.

        Dispatches GUILD_MEMBER_REMOVE to relevant clients.
        Dispatches GUILD_DELETE to the user being removed from the guild.
        """

        user_id = str(user.id)

        raw_guild = guild._data
        raw_guild['members'].remove(user_id)

        result = await self.guild_db.replace_one({'id': str(guild.id)}, raw_guild)
        log.info(f"Updated {result.modified_count} guilds")

        await self.reload_guild(guild.id)
        await guild.dispatch('GUILD_MEMBER_REMOVE', {
            'guild_id': str(guild.id),
            'user': user.as_json,
        })

        await user.dispatch("GUILD_DELETE", {
            'id': str(guild.id),
            'unavailable': False,
        })

    async def ban_member(self, member):
        pass

    async def unban_member(self, user):
        pass

    async def kick_member(self, member):
        guild = member.guild
        try:
            await self.remove_member(guild, member.user)
            return True
        except:
            log.error("Error kicking member.", exc_info=True)
            return False

    async def create_channel(self, guild, channel_payload):
        pass

    async def edit_channel(self, guild, new_payload):
        pass

    async def delete_channel(self, channel):
        pass

    async def invite_janitor(self):
        """Janitor task for invites.

        This checks every 30 minutes for invalid invites and removes them from
        the database.
        """

        try:
            while True:
                cursor = self.invite_db.find()
                now = datetime.datetime.now()

                deleted, total = 0, 0

                for raw_invite in (await cursor.to_list(length=None)):
                    timestamp = raw_invite.get('timestamp', None)

                    if timestamp is not None:
                        invite_timestamp = datetime.datetime.strptime(self.iso_timestamp, \
                            "%Y-%m-%dT%H:%M:%S")

                        if now > invite_timestamp:
                            await self.invite.db.delete_one({'code': raw_invite['code']})
                            try:
                                self.invites.pop({'code': raw_invite['code']})
                            except:
                                pass

                            deleted += 1
                    total += 1

                log.info("Deleted {deleted}/{total} invites")

                # 30 minutes until next cycle
                await asyncio.sleep(1800)
        except asyncio.CancelledError:
            pass

    async def make_invite_code(self):
        """Generate an unique invite code.

        This uses `snowflake.get_invite_code` and checks if the code already exists
        in the database.
        """

        invi_code = get_invite_code()
        raw_invite = await self.invite_db.find_one({'code': invi_code})

        while raw_invite is not None:
            invi_code = get_invite_code()
            raw_invite = await self.invite_db.find_one({'code': invi_code})

        return invi_code

    async def create_invite(self, channel, inviter, invite_payload):
        # TODO: something something permissions
        #if not channel.guild.permissions(user, MAKE_INVITE):
        # return None

        age = invite_payload['max_age']
        iso_timestamp = None
        if age > 0:
            now = datetime.datetime.now().timestamp
            expiry_timestamp = datetime.datetime.fromtimestamp(now + age)
            iso_timestamp = expiry_timestamp.isoformat()

        uses = invite_payload.get('max_uses', -1)
        if uses == 0:
            uses = -1

        invite_code = await self.make_invite_code()
        raw_invite = {
            'code': invite_code,
            'channel_id': str(channel.id),
            'inviter_id': str(inviter.id),
            'timestamp': iso_timestamp,
            'uses': uses,
            'temporary': False,
            'unique': True,
        }

        self.invite_db.insert_one(raw_invite)

        invite = Invite(self.server, raw_invite)
        if invite.valid:
            self.invites[invite.code] = invite

        return invite

    async def use_invite(self, user, invite):
        """Uses an invite.

        Adds a user to a guild, returns `False` on failure, `Member` on success.
        """

        if not invite.sane:
            log.warning(f"Insane invite {invite.code} to {invite.channel.guild.name}")
            return False

        success = invite.use()
        if not success:
            return False

        await invite.update()

        guild = invite.channel.guild
        member = await self.add_member(guild, user)

        if member is None:
            return False

        return member

    async def delete_invite(self, invite):
        """Deletes an invite.

        Removes it from database and cache.
        """

        res = await self.invite_db.delete_one({'code': invite.code})
        log.info(f"Removed {res.deleted_count} invites")

        try:
            self.invites.pop(invite.code)
        except:
            pass

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
                self.invites[invite.code] = invite
                valid_invites += 1
            else:
                await self.delete_invite(invite)

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
