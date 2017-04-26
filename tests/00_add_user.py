#!/usr/bin/python3
import requests
import json

API_BASE = "http://0.0.0.0:8000/api"
def route(route):
    return f'{API_BASE}/{route}'

r = requests.post(route('users/add'), data=json.dumps({
    'email': 'lol',
    'username': 'lal',
    'password': 'lul',
}))
print(r)
print(r.text)
