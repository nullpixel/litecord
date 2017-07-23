from .base import LitecordObject

class Webhook(LitecordObject):
    """A webhook object
    
    Attributes
    ----------
    _raw: dict
        Raw webhook data.
    id: int
        ID of the webhook.
    channel_id: int
        ID of the channel the webhook refers to.
    creator_id: int
        ID of the user who created the webhook.
    channel: :class:`Channel`
        Channel the webhook refers to.
    creator_id: :class:`User`
        User who created the webhook.
    name: str
        Name of the webhook.
    avatar: str
        Avatar of the webhook.
    token: str
        Token of the webhook.
    """

    def __init__(self, user, channel, raw):
        self.id = int(raw['webhook_id'])
        self._update(user, channel, raw)

    def _update(self, user, channel, raw):
        self._raw = raw
        self.channel = channel
        self.guild = channel.guild
        self.creator = user

        self.channel_id = int(raw['channel_id'])
        self.creator_id = int(raw['creator_id'])
        
        self.name = raw['name']
        self.avatar = raw['avatar']
        self.token = raw['token']

    async def execute(self):
        return

