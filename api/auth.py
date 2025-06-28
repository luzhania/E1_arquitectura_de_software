from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from jose import jwt
import requests
import os
from dotenv import load_dotenv

load_dotenv()

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
API_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
ALGORITHMS = ["RS256"]
URL_FRONTEND = os.getenv("URL_FRONTEND", "https://www.arquitecturadesoftware.me")

# Detect if running in CI environment
IS_CI = os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("CI") == "true"

bearer_scheme = HTTPBearer()

def get_jwk():
    """Get JWKS from Auth0 - skip in CI environment"""
    if IS_CI:
        print("[AUTH] Running in CI environment, skipping Auth0 JWKS fetch")
        return {"keys": []}
    
    if not AUTH0_DOMAIN:
        print("[AUTH] No Auth0 domain configured, running in mock mode")
        return {"keys": []}
        
    try:
        jsonurl = requests.get(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json")
        return jsonurl.json()
    except Exception as e:
        print(f"[AUTH] Failed to fetch JWKS: {e}")
        return {"keys": []}

# Only fetch JWKS if not in CI
if IS_CI:
    jwks = {"keys": []}
    print("[AUTH] Running in CI environment, skipping Auth0 initialization")
else:
    jwks = get_jwk()

def verify_token(token: str = Depends(bearer_scheme)):
    """Verify JWT token - skip validation in CI environment"""
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Skip auth validation in CI environment
    if IS_CI:
        print("[AUTH] Running in CI environment, returning mock user")
        return {"sub": "test-user", "email": "test@example.com"}
    
    # Skip auth validation if no Auth0 domain configured
    if not AUTH0_DOMAIN:
        print("[AUTH] No Auth0 domain configured, returning mock user")
        return {"sub": "test-user", "email": "test@example.com"}
    
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
            print("[DEBUG] Token payload:", payload)
            return payload
    except Exception as e:
        print(f"[AUTH] Token validation failed: {e}")
        raise credentials_exception
        
    raise credentials_exception

# def admin_required(user: dict = Depends(verify_token)):
#     # roles = user.get(f"{URL_FRONTEND}/roles", [])##Modificar en deploy
#     roles = user.get("https://www.arquitecturadesoftware.me/roles", [])
#     if "admin" not in roles:
#         print("[AUTH] User is not an admin, access denied")
#         raise HTTPException(status_code=403, detail="Not authorized to access this resource.")
#     return user

ROLE_CLAIM = "https://www.arquitecturadesoftware.me/roles"  # ✅ Usa el claim exacto del token

def admin_required(user: dict = Depends(verify_token)):
    roles = user.get(ROLE_CLAIM, [])
    print(f"[AUTH] User roles: {roles}")
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="Not authorized to access this resource.")
    print("[AUTH] Admin access granted")
    return user

def is_admin(user: dict = Depends(verify_token)):
    roles = user.get(ROLE_CLAIM, [])
    return "admin" in roles