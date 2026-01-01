"""
Servicio de integración con Facebook Graph API
"""
import os
import httpx
from urllib.parse import urlencode
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

FACEBOOK_APP_ID = os.environ.get('FACEBOOK_APP_ID')
FACEBOOK_APP_SECRET = os.environ.get('FACEBOOK_APP_SECRET')
FACEBOOK_REDIRECT_URI = os.environ.get('FACEBOOK_REDIRECT_URI', 'https://agathoscreative.com/auth/facebook/callback')
GRAPH_API_VERSION = 'v21.0'
GRAPH_API_BASE = f'https://graph.facebook.com/{GRAPH_API_VERSION}'

# Permisos requeridos
FACEBOOK_PERMISSIONS = [
    'pages_manage_posts',
    'pages_read_engagement',
    'pages_show_list',
    'public_profile',
    'email'
]


class FacebookService:
    """Servicio para interactuar con Facebook Graph API"""

    def __init__(self):
        self.app_id = FACEBOOK_APP_ID
        self.app_secret = FACEBOOK_APP_SECRET
        self.redirect_uri = FACEBOOK_REDIRECT_URI

    def get_login_url(self, state: str = None) -> str:
        """
        Genera la URL de login de Facebook OAuth

        Args:
            state: Token CSRF para seguridad

        Returns:
            URL de autorización de Facebook
        """
        params = {
            'client_id': self.app_id,
            'redirect_uri': self.redirect_uri,
            'scope': ','.join(FACEBOOK_PERMISSIONS),
            'response_type': 'code',
        }
        if state:
            params['state'] = state

        return f'https://www.facebook.com/{GRAPH_API_VERSION}/dialog/oauth?{urlencode(params)}'

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Intercambia el código de autorización por un access token

        Args:
            code: Código de autorización de Facebook

        Returns:
            Dict con access_token, token_type, expires_in
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f'{GRAPH_API_BASE}/oauth/access_token',
                params={
                    'client_id': self.app_id,
                    'client_secret': self.app_secret,
                    'redirect_uri': self.redirect_uri,
                    'code': code
                }
            )
            response.raise_for_status()
            return response.json()

    async def get_long_lived_token(self, short_lived_token: str) -> Dict[str, Any]:
        """
        Convierte un token de corta duración en uno de larga duración (60 días)

        Args:
            short_lived_token: Token de usuario de corta duración

        Returns:
            Dict con access_token y expires_in
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f'{GRAPH_API_BASE}/oauth/access_token',
                params={
                    'grant_type': 'fb_exchange_token',
                    'client_id': self.app_id,
                    'client_secret': self.app_secret,
                    'fb_exchange_token': short_lived_token
                }
            )
            response.raise_for_status()
            return response.json()

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Obtiene información del usuario

        Args:
            access_token: Token de acceso del usuario

        Returns:
            Dict con id, name, email
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f'{GRAPH_API_BASE}/me',
                params={
                    'fields': 'id,name,email',
                    'access_token': access_token
                }
            )
            response.raise_for_status()
            return response.json()

    async def get_user_pages(self, access_token: str) -> List[Dict[str, Any]]:
        """
        Obtiene las páginas que administra el usuario

        Args:
            access_token: Token de acceso del usuario

        Returns:
            Lista de páginas con id, name, access_token
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f'{GRAPH_API_BASE}/me/accounts',
                params={
                    'fields': 'id,name,access_token,category,picture',
                    'access_token': access_token
                }
            )
            response.raise_for_status()
            data = response.json()
            return data.get('data', [])

    async def post_to_page(
        self,
        page_id: str,
        page_access_token: str,
        message: str,
        image_url: Optional[str] = None,
        image_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Publica un post en una página de Facebook

        Args:
            page_id: ID de la página
            page_access_token: Token de acceso de la página
            message: Texto del post
            image_url: URL de la imagen (opcional)
            image_path: Path local de la imagen (opcional)

        Returns:
            Dict con id del post
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Si hay imagen, usar el endpoint de fotos
            if image_url or image_path:
                endpoint = f'{GRAPH_API_BASE}/{page_id}/photos'

                if image_path:
                    # Subir imagen desde archivo local
                    with open(image_path, 'rb') as image_file:
                        files = {'source': image_file}
                        data = {
                            'message': message,
                            'access_token': page_access_token
                        }
                        response = await client.post(endpoint, data=data, files=files)
                else:
                    # Usar URL de imagen
                    response = await client.post(
                        endpoint,
                        data={
                            'url': image_url,
                            'message': message,
                            'access_token': page_access_token
                        }
                    )
            else:
                # Post solo de texto
                endpoint = f'{GRAPH_API_BASE}/{page_id}/feed'
                response = await client.post(
                    endpoint,
                    data={
                        'message': message,
                        'access_token': page_access_token
                    }
                )

            response.raise_for_status()
            result = response.json()

            # Construir URL del post
            post_id = result.get('id', result.get('post_id', ''))
            if '_' in post_id:
                # El ID viene como page_id_post_id
                post_url = f"https://www.facebook.com/{post_id.replace('_', '/posts/')}"
            else:
                post_url = f"https://www.facebook.com/{page_id}/posts/{post_id}"

            return {
                'post_id': post_id,
                'post_url': post_url
            }

    async def verify_page_permissions(self, page_id: str, page_access_token: str) -> bool:
        """
        Verifica que tengamos permisos para publicar en la página

        Args:
            page_id: ID de la página
            page_access_token: Token de acceso de la página

        Returns:
            True si tenemos permisos
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f'{GRAPH_API_BASE}/{page_id}',
                    params={
                        'fields': 'id,name,tasks',
                        'access_token': page_access_token
                    }
                )
                response.raise_for_status()
                data = response.json()
                tasks = data.get('tasks', [])
                # Verificar que tenga permiso de CREATE_CONTENT
                return 'CREATE_CONTENT' in tasks or 'MANAGE' in tasks
        except Exception as e:
            logger.error(f"Error verificando permisos: {e}")
            return False

    def calculate_token_expiry(self, expires_in: int) -> datetime:
        """
        Calcula la fecha de expiración del token

        Args:
            expires_in: Segundos hasta expiración

        Returns:
            Datetime de expiración
        """
        return datetime.now(timezone.utc) + timedelta(seconds=expires_in)


# Instancia global
facebook_service = FacebookService()
