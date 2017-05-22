#!/usr/bin/python3
import requests
import json

TOKEN = 'litecord_RLoWjnc45pDX2shufGjijfyPbh2kV0sYGz2EwARhIAs='
TOKEN_2 = 'litecord_Pmo48qD-Ctk9myVpyI5m399wkXNOxAsvgiUBf7H3Rp8kfXJJw77GFgn8OY38pUmqj_nKEy6R9g6nCACg4ipJkg=='
ADMIN_ENDPOINT = "http://0.0.0.0:8000/api/count"

r = requests.get(ADMIN_ENDPOINT, headers={
    'Authorization': f'Bot {TOKEN}'
})

print(r)
print(r.text)
