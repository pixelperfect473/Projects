import time
import requests
import credentials
import tokens
# GET TOKENS AND STORES IT IN TOKEN.PY
#token expires every 2 hours
AUTH_URL = 'https://authentication.carfax.ca/oauth/token'

AUTH_HEADERS = {
    'Content-Type': 'application/x-www-form-urlencoded'
}

def get_auth():
    # only retrieve if last token expired or i never retrieved it
    if not tokens.TOKEN or time.time() >= tokens.TOKEN_EXPIRY:
        response = requests.post(AUTH_URL,headers=AUTH_HEADERS,data={    
            'audience': credentials.audience,
            'grant_type':credentials.grant_type,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret
        })
        data = response.json()
        token = data["access_token"]
        expiry = time.time() + data.get("expires_in",2*59*60) #log expiry or hardcode 
        with open('tokens.py','w') as f:
            f.write(f'TOKEN ="{token}"\n')
            f.write(f'TOKEN_EXPIRY = {expiry}\n')
        tokens.TOKEN, tokens.TOKEN_EXPIRY = token, expiry
        return tokens.TOKEN
