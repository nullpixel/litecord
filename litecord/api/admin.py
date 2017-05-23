import logging

import traceback
import textwrap
import contextlib
import io

from aiohttp import web

from ..utils import _err, _json
from ..ratelimits import admin_endpoint

log = logging.getLogger(__name__)

class AdminEndpoints:
    def __init__(self, server):
        self.server = server
        self.guild_man = server.guild_man
        self._last_result = None

    def register(self, app):
        self.server.add_get('count', self.h_get_counts)
        self.server.add_post('admin_eval', self.h_eval)

    @admin_endpoint
    async def h_get_counts(self, request, user):
        """`GET /counts`.

        Return some statistics.
        """
        return _json(await self.server.make_counts())

    def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    def get_syntax_error(self, e):
        if e.text is None:
            return '```py\n{0.__class__.__name__}: {0}\n```'.format(e)
        return '```py\n{0.text}{1:>{0.offset}}\n{2}: {0}```'.format(e, '^', type(e).__name__)

    @admin_endpoint
    async def h_eval(self, request, user):
        """`POST:/admin_eval`

        Evaluate code.
        Most part of this code is modified from https://github.com/Rapptz/RoboDanny/blob/master/cogs/repl.py
        Thanks Danny.
        """
        try:
            payload = await request.json()
        except:
            return _err('error parsing data')

        body = payload.get('to_eval')
        if body is None:
            return _err('give something plox')

        log.info(f"{user!r} is evaluating {body!r}")

        env = {
            '_': self._last_result,
            'self': self,
            'server': self.server,
            'guild_man': self.guild_man,
            'user': user,
            'request': request,
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = 'async def func():\n%s' % textwrap.indent(body, '  ')

        out = {
            'error': False,
            'stdout': '',
        }

        try:
            exec(to_compile, env)
        except SyntaxError as e:
            out['error'] = True
            out['stdout'] = self.get_syntax_error(e)

            return _json(out)

        func = env['func']
        try:
            with contextlib.redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            res = f'{value}{traceback.format_exc()}'
            out['stdout'] = res
            return _json(out)
        else:
            value = stdout.getvalue()

            if ret is None:
                if value:
                    res = f'{value}'
                    out['stdout'] = res
                    return _json(out)
            else:
                self._last_result = ret
                res = f'{value}{ret}'
                out['stdout'] = res
                return _json(out)

        return _json(out)
