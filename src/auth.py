
import jwt

from jwt import PyJWKClient, PyJWKClientError

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer

from src.keycloak_config import (
    JWKS_URL,
    ISSUER,
    KEYCLOAK_CLIENT_ID
)


# ==========================================
# CONFIGURACIÓN OAUTH2 CON KEYCLOAK
# ==========================================

security = OAuth2AuthorizationCodeBearer(
    authorizationUrl=(
        "http://localhost:8080/realms/mortalidad/"
        "protocol/openid-connect/auth"
    ),
    tokenUrl=(
        "http://localhost:8080/realms/mortalidad/"
        "protocol/openid-connect/token"
    ),
    scopes={}
)


# ==========================================
# OBTENER CLAVES PÚBLICAS DE KEYCLOAK
# ==========================================

jwks_client = PyJWKClient(JWKS_URL)


# ==========================================
# VALIDAR TOKEN JWT
# ==========================================

def verificar_token(
    token: str = Depends(security)
):
    try:
        # Obtener clave pública correspondiente al token
        signing_key = jwks_client.get_signing_key_from_jwt(
            token
        )

        # Verificar firma, expiración, emisor y audiencia
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=KEYCLOAK_CLIENT_ID,
            issuer=ISSUER,
            options={
                "require": [
                    "exp",
                    "iat",
                    "iss",
                    "aud"
                ]
            }
        )

        return payload

    except (jwt.PyJWTError, PyJWKClientError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )


# ==========================================
# VERIFICAR ROL ADMINISTRADOR
# ==========================================

def requiere_admin(
    usuario: dict = Depends(verificar_token)
):
    roles = usuario.get(
        "realm_access", {}
    ).get("roles", [])

    if "admin" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos de administrador"
        )

    return usuario
