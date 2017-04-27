from random import randint

def strip_user_data(user):
    return {
        'id': user['id'],
        'username': user['username'],
        'discriminator': user['discriminator'],
        'avatar': user['avatar'],
        'bot': user['bot'],
        #'mfa_enabled': user['mfa_enabled'],
        'verified': user['verified'],
        'email': user['email'],
    }

def random_digits(n):
    range_start = 10**(n-1)
    range_end = (10**n)-1
    return randint(range_start, range_end)
