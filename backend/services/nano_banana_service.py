"""
Servicio de integración con Nano Banana Pro (Gemini 3 Pro Image)
Para generación de imágenes de alta calidad
"""
import os
import httpx
import base64
import uuid
from typing import Optional, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
NANO_BANANA_MODEL = 'gemini-3-pro-image-preview'
NANO_BANANA_ENDPOINT = f'https://generativelanguage.googleapis.com/v1beta/models/{NANO_BANANA_MODEL}:generateContent'

# Directorio para guardar imágenes
IMAGES_DIR = Path('/var/www/agathoscreative/images/posts')


class NanoBananaService:
    """Servicio para generar imágenes con Nano Banana Pro"""

    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.images_dir = IMAGES_DIR
        # Crear directorio si no existe
        self.images_dir.mkdir(parents=True, exist_ok=True)

    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        image_size: str = "1K",
        save_locally: bool = True
    ) -> Dict[str, Any]:
        """
        Genera una imagen usando Nano Banana Pro

        Args:
            prompt: Prompt detallado para la imagen
            aspect_ratio: Relación de aspecto (1:1, 16:9, 9:16, etc.)
            image_size: Tamaño de imagen (1K, 2K, 4K)
            save_locally: Si guardar la imagen localmente

        Returns:
            Dict con image_data, image_path, image_url
        """
        headers = {
            'Content-Type': 'application/json',
            'x-goog-api-key': self.api_key
        }

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": {
                    "aspectRatio": aspect_ratio,
                    "imageSize": image_size
                }
            },
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                NANO_BANANA_ENDPOINT,
                headers=headers,
                json=payload
            )

            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Error de Nano Banana Pro: {response.status_code} - {error_text}")
                raise Exception(f"Error generando imagen: {response.status_code}")

            data = response.json()

            # Extraer la imagen de la respuesta
            result = self._parse_response(data)

            if save_locally and result.get('image_data'):
                # Guardar imagen localmente
                image_path = self._save_image(result['image_data'])
                result['image_path'] = str(image_path)
                result['image_url'] = f"/images/posts/{image_path.name}"

            return result

    def _parse_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parsea la respuesta de Nano Banana Pro

        Args:
            data: Respuesta raw de la API

        Returns:
            Dict con image_data (base64), text, etc.
        """
        result = {
            "image_data": None,
            "text": "",
            "mime_type": "image/png"
        }

        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("No se generó ninguna imagen")

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])

        for part in parts:
            if "text" in part:
                result["text"] += part["text"]
            elif "inlineData" in part:
                inline_data = part["inlineData"]
                result["image_data"] = inline_data.get("data")
                result["mime_type"] = inline_data.get("mimeType", "image/png")

        if not result["image_data"]:
            raise ValueError("La respuesta no contiene datos de imagen")

        return result

    def _save_image(self, image_data: str, filename: Optional[str] = None) -> Path:
        """
        Guarda la imagen localmente

        Args:
            image_data: Datos de imagen en base64
            filename: Nombre de archivo opcional

        Returns:
            Path del archivo guardado
        """
        if not filename:
            filename = f"post_{uuid.uuid4().hex[:12]}.png"

        image_path = self.images_dir / filename

        # Decodificar y guardar
        image_bytes = base64.b64decode(image_data)
        image_path.write_bytes(image_bytes)

        logger.info(f"Imagen guardada: {image_path}")
        return image_path

    async def generate_post_image(
        self,
        image_prompt: str,
        post_id: str
    ) -> Dict[str, Any]:
        """
        Genera una imagen para un post específico

        Args:
            image_prompt: Prompt detallado de la imagen
            post_id: ID del post para nombrar el archivo

        Returns:
            Dict con paths y URLs de la imagen
        """
        # Agregar instrucciones adicionales al prompt
        enhanced_prompt = f"""Create a stunning, professional social media image.

{image_prompt}

IMPORTANT REQUIREMENTS:
- High quality, sharp details
- Professional lighting
- Vibrant but natural colors
- Suitable for Facebook/Instagram
- No text overlays (the caption will be separate)
- Clean composition with visual impact
"""

        result = await self.generate_image(
            prompt=enhanced_prompt,
            aspect_ratio="1:1",  # Cuadrado para redes sociales
            image_size="2K",  # Alta calidad
            save_locally=True
        )

        # Renombrar con el ID del post si se guardó
        if result.get('image_path'):
            old_path = Path(result['image_path'])
            new_filename = f"post_{post_id}.png"
            new_path = old_path.parent / new_filename

            if old_path.exists():
                old_path.rename(new_path)
                result['image_path'] = str(new_path)
                result['image_url'] = f"/images/posts/{new_filename}"

        return result


# Instancia global
nano_banana_service = NanoBananaService()
