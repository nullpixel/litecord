import requests
import random
import pprint

API_BASE = 'http://0.0.0.0:8000/api'

token = 'MTQ5MjYwMDQ2MzM3.XtULkT4wpElDKqZOFDhLUj0Djdw'

def main():
    bot_payload = {
        'name': f'Awesome Bot {random.randint(0, 100)}',
        'description': 'good bot',
    }
    headers = {'Authorization': f'Bot {token}'}
    r = requests.post(f'{API_BASE}/oauth2/applications', headers=headers, json=bot_payload)
    print(r)
    d = r.json()
    pprint.pprint(d)

    print('bot data')
    r = requests.get(f'{API_BASE}/oauth2/applications/{d["id"]}', headers=headers)
    print(r)
    d = r.json()
    pprint.pprint(d)

if __name__ == '__main__':
    main()
