import requests

API_BASE = 'http://0.0.0.0:8000/api'

token = 'MTQ5MjYwMDQ2MzM3.tcLbMZuswIKanjv1FB0Om1yq2rA'

def main():
    bot_payload = {
        'name': 'Awesome Bot',
        'description': 'good bot',
    }
    r = requests.post(f'{API_BASE}/auth/bot/add', headers={'Authorization': f'Bot {token}'}, json=bot_payload)
    print(r)
    print(r.json())

if __name__ == '__main__':
    main()
