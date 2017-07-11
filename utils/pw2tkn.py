#!/usr/bin/env python3

"""
pw2tkn.py - get your Litecord token using email/password authentication.

Usage:
    python pw2tkn.py your_user your_password
"""

import requests
import sys
import json

API_URL = 'https://litecord.memework.org/api'
#API_URL = 'http://0.0.0.0:8000/api'
API_URL = 'http://163.172.191.166:8000/api'

def main(args):
    email = args[1]
    password = args[2]

    payload = {
        "email": email,
        "password": password
    }
    _payload = json.dumps(payload)
    _resp = requests.post(f'{API_URL}/auth/login', data=_payload)
    print(_resp)
    resp = _resp.json()

    print(f"Your token is {resp.get('token')}")

if __name__ == '__main__':
    main(sys.argv)
