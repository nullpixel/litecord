import logging

from voluptuous import Schema, REMOVE_EXTRA

from ..utils import _err, _json, pwd_hash
from ..snowflake import get_raw_token
from ..decorators import auth_route

log = logging.getLogger(__name__)

class AuthEndpoints:
    """Handle authentication endpoints."""
    def __init__(self, server, app):
        self.server = server
        self.register(app)

        self.login_schema = Schema({
            'email': str,
            'password': str,
        }, extra=REMOVE_EXTRA)

    def register(self, app):
        self.server.add_post('auth/login', self.login)

    async def login(self, request):
        """Login a user through the `POST /auth/login` endpoint.

        With the provided token you can connect to the
        gateway and send an IDENTIFY payload.

        Parameters
        ----------
        request: dict
            Two keys, `email` and `password`, password is in plaintext.

        Returns
        -------
        dict:
            With a `token` field.
        """
        try:
            payload = await request.json()
        except Exception as err:
            return _err("error parsing")

        payload = self.login_schema(payload)

        email = payload['email']
        password = payload['password']

        raw_user = await self.server.get_raw_user_email(email)
        if raw_user is None:
            return _err("fail on login [email]")

        pwd = raw_user['password']
        if pwd_hash(password, pwd['salt']) != pwd['hash']:
            return _err("fail on login [password]")

        user_id = raw_user['id']
        old_token = await self.server.token_userid(user_id)

        new_token = await get_raw_token()
        while (await self.server.token_used(new_token)):
            new_token = await get_raw_token()

        await self.server.token_unregister(old_token)

        log.info(f"[login] Generated new token for {user_id}")
        await self.server.token_register(new_token, user_id)

        return _json({"token": new_token})
