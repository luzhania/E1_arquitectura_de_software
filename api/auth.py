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

# # Update your verify_token function to correctly extract the email from Auth0 tokens

# from fastapi import Depends, HTTPException, status
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# from jose import jwt
# from jwt.exceptions import InvalidTokenError
# import os

# security = HTTPBearer()

# # Update these with your Auth0 values
# AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "your-auth0-domain")
# AUTH0_API_AUDIENCE = os.getenv("AUTH0_API_AUDIENCE", "your-audience")
# AUTH0_ALGORITHMS = ["RS256"]

# async def get_jwks():
#     import httpx
#     url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
#     async with httpx.AsyncClient() as client:
#         resp = await client.get(url)
#         return resp.json()

# async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
#     token = credentials.credentials
#     try:
#         # Get the key set from Auth0
#         jwks = await get_jwks()
        
#         # First decode without verification to get the kid (key id)
#         unverified_header = jwt.get_unverified_header(token)
        
#         # Find the correct key
#         rsa_key = {}
#         for key in jwks["keys"]:
#             if key["kid"] == unverified_header["kid"]:
#                 rsa_key = {
#                     "kty": key["kty"],
#                     "kid": key["kid"],
#                     "use": key["use"],
#                     "n": key["n"],
#                     "e": key["e"]
#                 }
        
#         if rsa_key:
#             payload = jwt.decode(
#                 token,
#                 rsa_key,
#                 algorithms=AUTH0_ALGORITHMS,
#                 audience=AUTH0_API_AUDIENCE,
#                 issuer=f"https://{AUTH0_DOMAIN}/"
#             )
            
#             # Extract email from Auth0 token - check for both standard fields
#             # Auth0 typically uses "email" or "sub" field for user identity
#             user_email = payload.get("email") or payload.get("sub").split("|")[1]
            
#             return {
#                 "email": user_email,
#                 "sub": payload.get("sub")
#             }
        
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Invalid authentication credentials"
#         )
#     except InvalidTokenError as e:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail=f"Invalid token: {str(e)}"
#         )