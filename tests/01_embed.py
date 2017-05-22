#!/usr/bin/python3
import requests
import json

EMBED_URL = "http://0.0.0.0:8000/embed"

r = requests.get(EMBED_URL, data=json.dumps({
    'url': 'https://xkcd.com/666'
}))

print(r)
print(r.text)
