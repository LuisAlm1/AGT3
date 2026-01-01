"""
Servicio de integración con OpenAI Responses API
Utiliza el endpoint de Responses con Conversations para mantener contexto
"""
import os
import json
import httpx
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4.1')
OPENAI_BASE_URL = 'https://api.openai.com/v1'


# Definición de funciones para recopilar datos del negocio
ASSISTANT_FUNCTIONS = [
    {
        "type": "function",
        "function": {
            "name": "save_business_profile",
            "description": "Guarda el perfil completo del negocio del usuario incluyendo resumen, estilo de posts y recurrencia",
            "parameters": {
                "type": "object",
                "properties": {
                    "business_summary": {
                        "type": "string",
                        "description": "Resumen detallado de lo que hace el negocio del usuario. Debe incluir: tipo de negocio, productos/servicios principales, público objetivo, valores o diferenciadores"
                    },
                    "post_style": {
                        "type": "string",
                        "description": "Estilo y forma deseada para los posts. Debe incluir: tono (profesional, casual, divertido, inspiracional), colores preferidos, tipo de contenido (educativo, promocional, entretenimiento), referencias visuales"
                    },
                    "recurrence": {
                        "type": "string",
                        "enum": ["daily", "weekly", "biweekly", "monthly"],
                        "description": "Frecuencia con la que el usuario quiere publicar posts"
                    },
                    "preferred_time": {
                        "type": "string",
                        "description": "Hora preferida para publicar en formato HH:MM (24 horas)"
                    }
                },
                "required": ["business_summary", "post_style", "recurrence"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_business_summary",
            "description": "Actualiza únicamente el resumen del negocio",
            "parameters": {
                "type": "object",
                "properties": {
                    "business_summary": {
                        "type": "string",
                        "description": "Nuevo resumen del negocio"
                    }
                },
                "required": ["business_summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_post_style",
            "description": "Actualiza únicamente el estilo de los posts",
            "parameters": {
                "type": "object",
                "properties": {
                    "post_style": {
                        "type": "string",
                        "description": "Nuevo estilo para los posts"
                    }
                },
                "required": ["post_style"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_recurrence",
            "description": "Actualiza únicamente la frecuencia de publicación",
            "parameters": {
                "type": "object",
                "properties": {
                    "recurrence": {
                        "type": "string",
                        "enum": ["daily", "weekly", "biweekly", "monthly"],
                        "description": "Nueva frecuencia de publicación"
                    },
                    "preferred_time": {
                        "type": "string",
                        "description": "Nueva hora preferida en formato HH:MM"
                    }
                },
                "required": ["recurrence"]
            }
        }
    }
]


SYSTEM_PROMPT = """Eres un asistente de marketing experto que ayuda a configurar la estrategia de publicación automática en redes sociales.

Tu objetivo es recopilar la siguiente información del usuario de manera conversacional y amigable:

1. **Resumen del negocio**: Qué hace su negocio, productos/servicios, público objetivo, valores
2. **Estilo de posts**: Tono, colores, tipo de contenido, referencias visuales
3. **Frecuencia de publicación**: Diaria, semanal, quincenal o mensual, y hora preferida

INSTRUCCIONES:
- Sé amigable y profesional
- Haz preguntas claras y específicas
- Cuando tengas suficiente información sobre los 3 puntos, usa la función save_business_profile para guardar todo
- Si el usuario quiere modificar algo específico después, usa las funciones de actualización correspondientes
- Confirma siempre cuando hayas guardado la información
- Si el usuario pregunta sobre precios o créditos, explica que cada post cuesta 1 crédito y que tienen 1 crédito gratis para probar

Comienza presentándote y preguntando sobre su negocio."""


class OpenAIService:
    """Servicio para interactuar con OpenAI Responses API"""

    def __init__(self):
        self.api_key = OPENAI_API_KEY
        self.model = OPENAI_MODEL
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    async def create_conversation(self) -> str:
        """
        Crea una nueva conversación en OpenAI

        Returns:
            ID de la conversación
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f'{OPENAI_BASE_URL}/conversations',
                headers=self.headers,
                json={
                    "metadata": {
                        "purpose": "marketing_assistant"
                    }
                }
            )
            response.raise_for_status()
            data = response.json()
            return data['id']

    async def send_message(
        self,
        user_message: str,
        conversation_id: Optional[str] = None,
        previous_response_id: Optional[str] = None,
        include_functions: bool = True
    ) -> Dict[str, Any]:
        """
        Envía un mensaje usando la Responses API

        Args:
            user_message: Mensaje del usuario
            conversation_id: ID de conversación existente (opcional)
            previous_response_id: ID de respuesta anterior para contexto (opcional)
            include_functions: Si incluir las funciones del asistente

        Returns:
            Dict con la respuesta del asistente y metadata
        """
        # Construir el input
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]

        payload = {
            "model": self.model,
            "input": messages,
        }

        # Agregar contexto de conversación
        if conversation_id:
            payload["conversation"] = conversation_id
        elif previous_response_id:
            payload["previous_response_id"] = previous_response_id

        # Agregar funciones si es necesario
        if include_functions:
            payload["tools"] = ASSISTANT_FUNCTIONS

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f'{OPENAI_BASE_URL}/responses',
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            return self._parse_response(data)

    async def continue_conversation(
        self,
        user_message: str,
        conversation_id: str,
        include_functions: bool = True
    ) -> Dict[str, Any]:
        """
        Continúa una conversación existente

        Args:
            user_message: Mensaje del usuario
            conversation_id: ID de la conversación
            include_functions: Si incluir las funciones

        Returns:
            Respuesta parseada
        """
        payload = {
            "model": self.model,
            "input": [{"role": "user", "content": user_message}],
            "conversation": conversation_id,
        }

        if include_functions:
            payload["tools"] = ASSISTANT_FUNCTIONS

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f'{OPENAI_BASE_URL}/responses',
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            return self._parse_response(data)

    def _parse_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parsea la respuesta de OpenAI

        Args:
            data: Respuesta raw de la API

        Returns:
            Dict estructurado con la respuesta
        """
        result = {
            "response_id": data.get("id"),
            "conversation_id": data.get("conversation"),
            "text": "",
            "function_calls": [],
            "raw": data
        }

        # Extraer el contenido de la respuesta
        output = data.get("output", [])
        for item in output:
            if item.get("type") == "message":
                content = item.get("content", [])
                for c in content:
                    if c.get("type") == "text":
                        result["text"] += c.get("text", "")
            elif item.get("type") == "function_call":
                result["function_calls"].append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "arguments": json.loads(item.get("arguments", "{}"))
                })

        return result

    async def generate_post_content(
        self,
        business_summary: str,
        post_style: str,
        post_number: int = 1
    ) -> Dict[str, Any]:
        """
        Genera el contenido de un post (prompt de imagen y caption)

        Args:
            business_summary: Resumen del negocio
            post_style: Estilo deseado
            post_number: Número del post (para variedad)

        Returns:
            Dict con image_prompt y caption
        """
        generation_prompt = f"""Genera contenido para un post de Facebook para el siguiente negocio:

RESUMEN DEL NEGOCIO:
{business_summary}

ESTILO DESEADO:
{post_style}

INSTRUCCIONES:
1. Genera un PROMPT DE IMAGEN ultra detallado para generar una imagen profesional. El prompt debe incluir:
   - Descripción del sujeto/escena principal
   - Estilo fotográfico (lifestyle, producto, conceptual, etc.)
   - Iluminación específica (golden hour, studio lighting, natural diffused, etc.)
   - Lente de cámara (35mm wide, 85mm portrait, macro, etc.)
   - Profundidad de campo (shallow DoF f/1.8, deep focus f/11, etc.)
   - Paleta de colores
   - Mood y atmósfera
   - Composición (rule of thirds, centered, leading lines, etc.)
   - Detalles de textura y materiales
   - Formato 1:1 para Instagram/Facebook

2. Genera un CAPTION atractivo para Facebook que:
   - Enganche al lector desde el inicio
   - Cuente una mini-historia o transmita un mensaje
   - Incluya un call-to-action sutil
   - Use emojis de forma estratégica (2-4 máximo)
   - Tenga 2-3 hashtags relevantes al final
   - Sea entre 50-150 palabras

Este es el post número {post_number}, así que sé creativo y varía el contenido.

Responde EXACTAMENTE en este formato JSON:
{{
    "image_prompt": "prompt detallado aquí",
    "caption": "caption aquí"
}}"""

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f'{OPENAI_BASE_URL}/responses',
                headers=self.headers,
                json={
                    "model": self.model,
                    "input": [{"role": "user", "content": generation_prompt}],
                }
            )
            response.raise_for_status()
            data = response.json()

            # Extraer el texto de la respuesta
            text = ""
            output = data.get("output", [])
            for item in output:
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "text":
                            text += c.get("text", "")

            # Parsear el JSON de la respuesta
            try:
                # Buscar el JSON en la respuesta
                import re
                json_match = re.search(r'\{[\s\S]*\}', text)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    raise ValueError("No se encontró JSON en la respuesta")
            except json.JSONDecodeError as e:
                logger.error(f"Error parseando respuesta: {text}")
                raise ValueError(f"Error parseando respuesta de OpenAI: {e}")


# Instancia global
openai_service = OpenAIService()
