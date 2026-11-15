
# Configuración de Keycloak

KEYCLOAK_URL = "http://localhost:8080"

KEYCLOAK_REALM = "mortalidad"

KEYCLOAK_CLIENT_ID = "mortalidad-api"

# URL para obtener las claves públicas de Keycloak
JWKS_URL = (
    f"{KEYCLOAK_URL}/realms/"
    f"{KEYCLOAK_REALM}/protocol/openid-connect/certs"
)

# Emisor esperado de los tokens
ISSUER = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"
