
import jwt

from jwt import PyJWKClient, PyJWKClientError

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer

from src.keycloak_config import (
    AUTH_ENABLED,
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
# USUARIO DE PRUEBA (sin autenticación)
# ==========================================
# Se usa solo cuando AUTH_ENABLED=false.
# No altera la lógica de producción.

_USUARIO_PRUEBA = {
    "sub": "test-user",
    "preferred_username": "test-user",
    "realm_access": {
        "roles": ["admin"]
    }
}


# ==========================================
# VALIDAR TOKEN JWT (con soporte AUTH_ENABLED)
# ==========================================

def _verificar_token_keycloak(
    token: str = Depends(security)
):
    """Valida el token JWT contra Keycloak."""
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


def verificar_token():
    """
    Dependencia FastAPI que valida el token si AUTH_ENABLED=true.
    Si AUTH_ENABLED=false, devuelve un contexto de prueba sin
    requerir token.
    """
    if not AUTH_ENABLED:
        return _USUARIO_PRUEBA
    return _verificar_token_keycloak()


# ==========================================
# VERIFICAR ROL ADMINISTRADOR (con soporte AUTH_ENABLED)
# ==========================================

def _requiere_admin_keycloak(
    usuario: dict = Depends(_verificar_token_keycloak)
):
    """Verifica rol admin con Keycloak activo."""
    roles = usuario.get(
        "realm_access", {}
    ).get("roles", [])

    if "admin" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos de administrador"
        )

    return usuario


def requiere_admin():
    """
    Dependencia FastAPI que verifica rol admin si AUTH_ENABLED=true.
    Si AUTH_ENABLED=false, devuelve el usuario de prueba con rol admin.
    """
    if not AUTH_ENABLED:
        return _USUARIO_PRUEBA
    return _requiere_admin_keycloak()
