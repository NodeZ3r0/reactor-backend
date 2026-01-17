import jwt
import requests
import os
import sys
from typing import Optional, Dict
from dotenv import load_dotenv

load_dotenv()

KEYCLOAK_URL = os.getenv('KEYCLOAK_URL', 'https://wopr.systems/auth')
KEYCLOAK_REALM = os.getenv('KEYCLOAK_REALM', 'master')

print(f"[AUTH] Loaded config: URL={KEYCLOAK_URL}, REALM={KEYCLOAK_REALM}", file=sys.stderr)

class User:
    def __init__(self, user_id: str, username: str, email: str, is_admin: bool = False):
        self.id = user_id
        self.username = username
        self.email = email
        self.is_admin = is_admin

def get_keycloak_public_key():
    url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
    print(f"[AUTH] Fetching JWKS from: {url}", file=sys.stderr)
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        jwks = response.json()
        print(f"[AUTH] Successfully fetched {len(jwks.get('keys', []))} keys", file=sys.stderr)
        return jwks
    except Exception as e:
        print(f"[AUTH] ERROR fetching Keycloak public key: {e}", file=sys.stderr)
        return None

def verify_token(token: str) -> Optional[Dict]:
    print(f"[AUTH] Verifying token (length: {len(token)})", file=sys.stderr)
    try:
        jwks = get_keycloak_public_key()
        if not jwks:
            print(f"[AUTH] ERROR: No JWKS available", file=sys.stderr)
            return None
        
        unverified_header = jwt.get_unverified_header(token)
        print(f"[AUTH] Token kid: {unverified_header.get('kid')}", file=sys.stderr)
        
        rsa_key = {}
        for key in jwks['keys']:
            if key['kid'] == unverified_header['kid']:
                rsa_key = {'kty': key['kty'], 'kid': key['kid'], 'use': key['use'], 'n': key['n'], 'e': key['e']}
                print(f"[AUTH] Found matching key", file=sys.stderr)
                break
        
        if not rsa_key:
            print(f"[AUTH] ERROR: No matching key found for kid={unverified_header.get('kid')}", file=sys.stderr)
            return None
        
        from jwt.algorithms import RSAAlgorithm
        public_key = RSAAlgorithm.from_jwk(rsa_key)
        
        payload = jwt.decode(token, key=public_key, algorithms=['RS256'], options={'verify_aud': False})
        print(f"[AUTH] Token verified successfully for user: {payload.get('preferred_username')}", file=sys.stderr)
        return payload
    except Exception as e:
        print(f"[AUTH] ERROR: Token verification failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return None

def extract_user_from_token(token: str) -> Optional[User]:
    print(f"[AUTH] Extracting user from token", file=sys.stderr)
    payload = verify_token(token)
    if not payload:
        print(f"[AUTH] ERROR: No payload from verify_token", file=sys.stderr)
        return None
    
    user_id = payload.get('sub')
    username = payload.get('preferred_username', 'unknown')
    email = payload.get('email', '')
    roles = payload.get('realm_access', {}).get('roles', [])
    is_admin = 'admin' in roles
    
    print(f"[AUTH] Created user: {username} (admin={is_admin})", file=sys.stderr)
    return User(user_id, username, email, is_admin)


from fastapi import Header, HTTPException

REACTOR_API_KEY = os.getenv("REACTOR_API_KEY")

def verify_api_key(x_api_key: str = Header(None)):
    if not REACTOR_API_KEY:
        raise HTTPException(status_code=500, detail="REACTOR_API_KEY not configured on server")
    if not x_api_key or x_api_key != REACTOR_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True
