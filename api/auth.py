from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer
from jose import jwt
import requests
import os
from dotenv import load_dotenv
load_dotenv()


AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
API_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
ALGORITHMS = ["RS256"]

bearer_scheme = HTTPBearer()

def get_jwk():
    jsonurl = requests.get(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json")
    return jsonurl.json()

jwks = get_jwk()

def verify_token(token: str = Depends(bearer_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        unverified_header = jwt.get_unverified_header(token.credentials)
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
        if rsa_key:
            payload = jwt.decode(
                token.credentials,
                rsa_key,
                algorithms=ALGORITHMS,
                audience=API_AUDIENCE,
                issuer=f"https://{AUTH0_DOMAIN}/"
            )
            return payload
    except Exception:
        raise credentials_exception
    raise credentials_exception
