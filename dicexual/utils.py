
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
