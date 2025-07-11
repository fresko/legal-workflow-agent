# -*- coding: utf-8 -*-
"""
Extractor de datos de documentos legales con Gemini AI
Versión mejorada con soporte para fine-tuning y mejor detección de campos verticales
"""

import json
import os
import tempfile
import requests
import google.generativeai as genai
import PyPDF2
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime
import re

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LegalDocumentExtractor:
    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa el extractor de documentos legales
        
        Args:
            api_key: API key de Google Gemini. Si no se proporciona, se busca en variables de entorno
        """
        self.config = self._load_config()
        self.api_key = api_key or self._get_api_key()
        self._configure_gemini()
        self.schema = self._get_response_schema()
        self.model_name = self.config.get('model_settings', {}).get('model_name', 'gemini-2.0-flash-001')
        
    def _load_config(self) -> Dict[str, Any]:
        """Carga la configuración desde config.json"""
        config_path = Path(__file__).parent / 'config.json'
        
        default_config = {
            "model_settings": {
                "model_name": "gemini-2.0-flash-001",
                "temperature": 0.1,
                "max_output_tokens": 8192,
                "top_p": 0.8,
                "top_k": 20
            },
            "processing_settings": {
                "max_pages": 2,
                "output_format": "json"
            }
        }
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # Merge with defaults
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                    elif isinstance(value, dict):
                        for subkey, subvalue in value.items():
                            if subkey not in config[key]:
                                config[key][subkey] = subvalue
                return config
            except Exception as e:
                logger.warning(f"Error cargando config.json: {e}, usando configuración por defecto")
                return default_config
        else:
            logger.info("config.json no encontrado, usando configuración por defecto")
            return default_config
        
    def _get_api_key(self) -> str:
        """Obtiene la API key desde variables de entorno o archivo config"""
        # Intentar desde variable de entorno
        api_key = os.getenv('GOOGLE_API_KEY')
        
        if not api_key:
            # Intentar desde archivo config.json
            api_key = self.config.get('GOOGLE_API_KEY')
        
        if not api_key or api_key == 'TU_API_KEY_AQUI':
            raise ValueError(
                "API key no encontrada o no configurada. "
                "Configúrala en la variable de entorno GOOGLE_API_KEY "
                "o en el archivo config.json. "
                "Obtén tu API key en: https://makersuite.google.com/app/apikey"
            )
        
        return api_key
    
    def _configure_gemini(self):
        """Configura el cliente de Gemini"""
        genai.configure(api_key=self.api_key)
        logger.info("Cliente Gemini configurado correctamente")
    
    def _get_response_schema(self) -> Dict[str, Any]:
        """Define el schema mejorado para la respuesta JSON"""
        return {
            "type": "object",
            "properties": {
                "expediente": {
                    "type": "string",
                    "description": "Número de expediente del documento"
                },
                "ciudad": {
                    "type": "string",
                    "description": "Ciudad donde se presenta la solicitud (Bogotá, Cali, Medellín, Barranquilla)"
                },
                "hechos": {
                    "type": "string",
                    "description": "Descripción detallada de los hechos"
                },
                "peticiones": {
                    "type": "string",
                    "description": "Peticiones realizadas en la solicitud"
                },
                "cuantia": {
                    "type": "string",
                    "description": "Valor económico de la cuantía"
                },
                "convocantes": {
                    "type": "array",
                    "description": "Lista de personas que convocan",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rol": {
                                "type": "string",
                                "description": "Rol de la persona (CONDUCTOR, PROPIETARIO, OTROS)"
                            },
                            "nombre": {
                                "type": "string",
                                "description": "Nombre completo de la persona"
                            },
                            "email": {
                                "type": "string",
                                "description": "Dirección(es) de correo electrónico separadas por comas"
                            },
                            "telefono": {
                                "type": "string",
                                "description": "Número(s) de teléfono"
                            }
                        },
                        "required": ["nombre", "email"]
                    }
                },
                "convocados": {
                    "type": "array",
                    "description": "Lista de personas convocadas",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rol": {
                                "type": "string",
                                "description": "Rol de la persona (CONDUCTOR, PROPIETARIO, OTROS)"
                            },
                            "nombre": {
                                "type": "string",
                                "description": "Nombre completo de la persona"
                            },
                            "mail": {
                                "type": "string",
                                "description": "Dirección(es) de correo electrónico separadas por comas"
                            },
                            "telefono": {
                                "type": "string",
                                "description": "Número(s) de teléfono"
                            }
                        },
                        "required": ["nombre", "mail"]
                    }
                },
                "fecha_conciliacion": {
                    "type": "string",
                    "description": "Fecha de la audiencia en formato YYYY-MM-DD"
                },
                "hora_conciliacion": {
                    "type": "string",
                    "description": "Hora de la audiencia"
                },
                "jornada": {
                    "type": "string",
                    "description": "Jornada de la audiencia (AM/PM)"
                },
                "fecha_inicio": {
                    "type": "string",
                    "description": "Fecha y hora de inicio de la audiencia en formato ISO 8601 (YYYY-MM-DDTHH:mm:ss)"
                },
                "fecha_fin": {
                    "type": "string",
                    "description": "Fecha y hora de fin de la audiencia (una hora después del inicio) en formato ISO 8601 (YYYY-MM-DDTHH:mm:ss)"
                }
            },
            "required": ["convocantes", "convocados"]
        }
    
    def trim_pdf(self, file_path: str, max_pages: int = 2) -> str:
        """
        Recorta un PDF a un número máximo de páginas
        
        Args:
            file_path: Ruta al archivo PDF
            max_pages: Número máximo de páginas a procesar
            
        Returns:
            Ruta del archivo PDF recortado
        """
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                pdf_writer = PyPDF2.PdfWriter()
                
                pages_to_process = min(len(pdf_reader.pages), max_pages)
                logger.info(f"Procesando {pages_to_process} páginas de un total de {len(pdf_reader.pages)}")
                
                for page_num in range(pages_to_process):
                    pdf_writer.add_page(pdf_reader.pages[page_num])
                
                trimmed_file_path = f"{file_path}_trimmed.pdf"
                with open(trimmed_file_path, 'wb') as output_file:
                    pdf_writer.write(output_file)
                
                return trimmed_file_path
                
        except Exception as e:
            logger.error(f"Error al recortar el PDF: {e}")
            return file_path
    
    def _get_enhanced_prompt(self) -> str:
        """Genera un prompt mejorado para mejor detección de campos verticales"""
        return """
        Analiza CUIDADOSAMENTE el documento adjunto (solo las páginas del formulario, no los anexos), que es una solicitud de audiencia de conciliación. 

        INSTRUCCIONES ESPECÍFICAS PARA CAMPOS VERTICALES:
        
        🔍 CONVOCANTE vs CONVOCADO - DIFERENCIACIÓN CRÍTICA:
        - Busca las etiquetas "CONVOCANTE" y "CONVOCADO" o "CONVOCANDO" que aparecen de forma VERTICAL (rotadas 90°) en el lado izquierdo del documento
        - Estas etiquetas delimitan secciones claramente diferenciadas
        - Todo lo que está bajo la etiqueta vertical "CONVOCANTE" pertenece a convocantes
        - Todo lo que está bajo la etiqueta vertical "CONVOCADO"/"CONVOCANDO" pertenece a convocados
        
        📋 ESTRUCTURA DE CAMPOS POR SECCIÓN:
        Cada sección (CONVOCANTE/CONVOCADO) contiene:
        - CONDUCTOR: nombre, email, teléfono
        - PROPIETARIO: nombre, email, teléfono  
        - OTROS: nombre, email, teléfono (si aplica)
        
        📧 MANEJO DE EMAILS:
        - Si encuentras múltiples direcciones de correo en un campo, concaténalas separadas por comas
        - Busca patrones como: email1@domain.com, email2@domain.com
        
        🏙️ CIUDAD - IDENTIFICACIÓN POR CHECKBOX:
        - Busca casillas marcadas junto a: Bogotá[ ], Cali[✓], Medellín[ ], Barranquilla[ ]
        - La ciudad marcada es la seleccionada
        
        📅 FECHAS Y HORARIOS - DETECCIÓN ESPECÍFICA DE CASILLAS AM/PM:
        
        🕐 JORNADA (AM/PM) - ANÁLISIS DE CASILLAS CHECK:
        - Busca ESPECÍFICAMENTE las casillas de check para AM y PM en la sección de fecha/hora
        - Pueden aparecer como:
          * AM [✓] PM [ ]  (AM marcado)
          * AM [ ] PM [✓]  (PM marcado)
          * AM [x] PM [ ]  (AM marcado con x)
          * AM [ ] PM [x]  (PM marcado con x)
        - También pueden aparecer como checkboxes marcados visualmente: ☑, ✓, X, o casillas rellenas
        - La casilla MARCADA indica la jornada seleccionada
        - Si no encuentras casillas marcadas claramente, busca el contexto de la hora para determinar AM/PM
        
        🕒 PROCESAMIENTO DE HORA Y JORNADA:
        - Extrae la HORA exacta del documento (ej: 10:00, 2:30, 14:00)
        - Identifica la JORNADA basándose en las casillas marcadas (AM o PM)
        - Si la hora ya está en formato 24h (ej: 14:00), determina automáticamente si es AM o PM
        
        📅 FORMATO DE FECHAS:
        - Convierte fechas a formato YYYY-MM-DD
        - Para fecha_inicio: Combina fecha, hora y jornada en formato ISO 8601 (YYYY-MM-DDTHH:mm:ss)
        - Para fecha_fin: Agrega exactamente 1 hora a la fecha_inicio
        
        🔍 EJEMPLOS ESPECÍFICOS DE DETECCIÓN:
        
        CASO 1 - Casillas claras:
        "Hora: 10:00  AM [✓] PM [ ]" 
        → hora_conciliacion: "10:00", jornada: "AM"
        → fecha_inicio: "2024-03-15T10:00:00", fecha_fin: "2024-03-15T11:00:00"
        
        CASO 2 - PM marcado:
        "Hora: 2:30   AM [ ] PM [✓]"
        → hora_conciliacion: "2:30", jornada: "PM" 
        → fecha_inicio: "2024-03-15T14:30:00", fecha_fin: "2024-03-15T15:30:00"
        
        CASO 3 - Formato 24 horas:
        "Hora: 14:30"
        → hora_conciliacion: "14:30", jornada: "PM" (automático)
        → fecha_inicio: "2024-03-15T14:30:00", fecha_fin: "2024-03-15T15:30:00"
        
        ⚠️ INSTRUCCIONES CRÍTICAS:
        1. SIEMPRE busca primero las casillas de check AM/PM marcadas
        2. Si no encuentras casillas, usa el contexto de la hora para determinar AM/PM
        3. Asegúrate de que fecha_inicio y fecha_fin sean consistentes con la jornada detectada
        4. Valida que los horarios tengan sentido (ej: no 25:00 horas)
        
        Extrae la información y estructúrala según el schema JSON proporcionado. 
        Analiza ÚNICAMENTE este documento sin considerar información previa.
        """
    
    def _get_system_instruction(self) -> str:
        """Instrucciones del sistema optimizadas"""
        return """
        Eres un experto en análisis de documentos legales colombianos. 
        Tu tarea es extraer información de formularios de solicitud de audiencia de conciliación.
        
        REGLAS IMPORTANTES:
        1. Diferencia claramente entre CONVOCANTE y CONVOCADO usando las etiquetas verticales
        2. Mantén formato de fecha YYYY-MM-DD
        3. Concatena múltiples emails con comas
        4. Identifica roles específicos: CONDUCTOR, PROPIETARIO, OTROS
        5. Responde SIEMPRE en formato JSON válido
        """
    
    def process_pdf_with_gemini(self, file_path: str) -> Dict[str, Any]:
        """
        Procesa un archivo PDF con Gemini y extrae información estructurada
        
        Args:
            file_path: Ruta al archivo PDF
            
        Returns:
            Diccionario con los datos extraídos
        """
        model_settings = self.config.get('model_settings', {})
        
        generation_config = {
            "temperature": model_settings.get('temperature', 0.1),
            "top_p": model_settings.get('top_p', 0.8),
            "top_k": model_settings.get('top_k', 20),
            "max_output_tokens": model_settings.get('max_output_tokens', 8192),
            "response_mime_type": "application/json",
            "response_schema": self.schema,
        }
        
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self._get_system_instruction(),
            generation_config=generation_config,
        )
        
        # Verificar que el archivo existe y es accesible
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")
        
        # Subir archivo a Gemini
        logger.info(f"Subiendo archivo: {file_path}")
        files = genai.upload_file(file_path, mime_type="application/pdf")
        logger.info(f"Archivo subido: '{files.display_name}' - {files.uri}")
        
        try:
            logger.info("Generando contenido con Gemini...")
            response = model.generate_content([files, self._get_enhanced_prompt()])
            
            if not response.text:
                raise Exception("Respuesta vacía de Gemini")
            
            result_json = json.loads(response.text)
            logger.info("Datos extraídos exitosamente")
            
            # Validar estructura básica
            self._validate_response(result_json)
            
            # Procesar y validar fechas
            result_json = self._process_datetime_fields(result_json)
            
            return result_json
            
        except json.JSONDecodeError as e:
            logger.error(f"Error al procesar JSON: {e}")
            logger.error(f"Respuesta recibida: {response.text}")
            raise Exception("La respuesta no es un JSON válido")
        except Exception as e:
            logger.error(f"Error en procesamiento: {e}")
            raise
    
    def _validate_response(self, data: Dict[str, Any]) -> None:
        """Valida la estructura de la respuesta"""
        validation_settings = self.config.get('validation_settings', {})
        
        if validation_settings.get('require_convocantes', True):
            if 'convocantes' not in data or not data['convocantes']:
                logger.warning("No se encontraron convocantes en la respuesta")
        
        if validation_settings.get('require_convocados', True):
            if 'convocados' not in data or not data['convocados']:
                logger.warning("No se encontraron convocados en la respuesta")
        
        # Validar emails si está habilitado
        if validation_settings.get('validate_email_format', True):
            self._validate_emails(data)
    
    def _validate_emails(self, data: Dict[str, Any]) -> None:
        """Valida formato de emails en la respuesta"""
        import re
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        
        # Validar emails en convocantes
        for convocante in data.get('convocantes', []):
            email = convocante.get('email', '')
            if email and not re.search(email_pattern, email):
                logger.warning(f"Email posiblemente inválido en convocante: {email}")
        
        # Validar emails en convocados
        for convocado in data.get('convocados', []):
            email = convocado.get('mail', '')
            if email and not re.search(email_pattern, email):
                logger.warning(f"Email posiblemente inválido en convocado: {email}")
    
    def _process_datetime_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Procesa y valida los campos de fecha y hora, creando fecha_inicio y fecha_fin"""
        from datetime import datetime, timedelta
        
        try:
            fecha_conciliacion = data.get('fecha_conciliacion')
            hora_conciliacion = data.get('hora_conciliacion')
            jornada = data.get('jornada', '').upper()
            
            # Log de datos recibidos
            logger.info(f"Procesando fecha/hora: fecha={fecha_conciliacion}, hora={hora_conciliacion}, jornada={jornada}")
            
            # Si no tenemos los datos básicos, intentar extraer de otros campos
            if not fecha_conciliacion or not hora_conciliacion:
                logger.warning("Faltan datos de fecha/hora, no se pueden generar fecha_inicio y fecha_fin")
                return data
            
            # Validar que la jornada esté presente y sea válida
            if not jornada or jornada not in ['AM', 'PM']:
                logger.warning(f"Jornada inválida o faltante: '{jornada}'. Intentando inferir de la hora...")
                
                # Intentar inferir la jornada de la hora si está en formato 24h
                try:
                    hora_num = int(hora_conciliacion.split(':')[0])
                    if hora_num >= 12:
                        jornada = 'PM'
                        logger.info(f"Jornada inferida como PM basándose en hora {hora_num}")
                    else:
                        jornada = 'AM'
                        logger.info(f"Jornada inferida como AM basándose en hora {hora_num}")
                except:
                    logger.warning("No se pudo inferir la jornada, usando valor original")
            
            # Parsear la hora y convertir a formato 24 horas
            hora_24 = self._convert_to_24_hour_format(hora_conciliacion, jornada)
            
            if hora_24:
                # Crear fecha_inicio en formato ISO 8601
                fecha_inicio_str = f"{fecha_conciliacion}T{hora_24}:00"
                
                # Validar que la fecha sea válida
                try:
                    fecha_inicio_dt = datetime.fromisoformat(fecha_inicio_str)
                except ValueError as e:
                    logger.error(f"Fecha inválida: {fecha_inicio_str}, error: {e}")
                    return data
                
                # Crear fecha_fin (una hora después)
                fecha_fin_dt = fecha_inicio_dt + timedelta(hours=1)
                fecha_fin_str = fecha_fin_dt.strftime("%Y-%m-%dT%H:%M:%S")
                
                # Agregar los nuevos campos
                data['fecha_inicio'] = fecha_inicio_str
                data['fecha_fin'] = fecha_fin_str
                
                # Actualizar la jornada en caso de que haya sido inferida
                data['jornada'] = jornada
                
                logger.info(f"✅ Fechas procesadas exitosamente:")
                logger.info(f"   🕐 Inicio: {fecha_inicio_str}")
                logger.info(f"   🕑 Fin: {fecha_fin_str}")
                logger.info(f"   🌅 Jornada: {jornada}")
            else:
                logger.warning("No se pudo procesar la hora, formato no reconocido")
                logger.warning(f"Datos recibidos: hora='{hora_conciliacion}', jornada='{jornada}'")
                
        except Exception as e:
            logger.error(f"Error procesando fechas: {e}")
            
        return data
    
    def _convert_to_24_hour_format(self, hora_str: str, jornada: str) -> Optional[str]:
        """Convierte hora en formato 12h a 24h con validaciones mejoradas"""
        
        try:
            # Limpiar la string de hora
            hora_clean = hora_str.strip().replace('.', ':')
            
            # Buscar patrones de hora (HH:MM o H:MM)
            hora_match = re.search(r'(\d{1,2}):(\d{2})', hora_clean)
            if not hora_match:
                # Intentar solo horas (ej: "10", "2")
                hora_match = re.search(r'(\d{1,2})', hora_clean)
                if hora_match:
                    horas = int(hora_match.group(1))
                    minutos = 0
                else:
                    logger.warning(f"No se pudo extraer hora de: '{hora_str}'")
                    return None
            else:
                horas = int(hora_match.group(1))
                minutos = int(hora_match.group(2))
            
            # Detectar si ya está en formato 24 horas
            if horas > 12:
                logger.info(f"Hora ya en formato 24h: {horas}:{minutos:02d}")
                return f"{horas:02d}:{minutos:02d}"
            
            # Validar rangos para formato 12h
            if horas < 1 or horas > 12 or minutos < 0 or minutos > 59:
                logger.warning(f"Hora fuera de rango válido: {horas}:{minutos}")
                # Intentar corrección automática si es formato 24h mal detectado
                if horas >= 0 and horas <= 23 and minutos >= 0 and minutos <= 59:
                    logger.info(f"Corrigiendo a formato 24h: {horas}:{minutos}")
                    return f"{horas:02d}:{minutos:02d}"
                return None
            
            # Normalizar jornada
            jornada_clean = jornada.strip().upper()
            
            # Convertir a formato 24 horas basándose en la jornada
            if jornada_clean == 'PM':
                if horas != 12:  # 1 PM = 13:00, 2 PM = 14:00, etc.
                    horas += 12
                # 12 PM = 12:00 (mediodía, no se cambia)
            elif jornada_clean == 'AM':
                if horas == 12:  # 12 AM = 00:00 (medianoche)
                    horas = 0
                # 1 AM = 01:00, 2 AM = 02:00, etc. (no se cambia)
            else:
                logger.warning(f"Jornada no reconocida: '{jornada}', asumiendo formato tal como está")
                # Si no hay jornada clara, mantener la hora como está
                if horas <= 12:
                    logger.info(f"Sin jornada clara, manteniendo hora: {horas}:{minutos:02d}")
                
            # Validación final
            if horas < 0 or horas > 23:
                logger.error(f"Hora final fuera de rango: {horas}:{minutos}")
                return None
                
            resultado = f"{horas:02d}:{minutos:02d}"
            logger.info(f"Conversión exitosa: '{hora_str}' {jornada} → {resultado}")
            return resultado
            
        except (ValueError, AttributeError) as e:
            logger.warning(f"Error convirtiendo hora '{hora_str}' con jornada '{jornada}': {e}")
            return None
    
    def process_document(self, file_path: str, output_path: Optional[str] = None, 
                        max_pages: int = 2, send_to_webhook: bool = None) -> Dict[str, Any]:
        """
        Procesa un documento completo desde PDF hasta JSON
        
        Args:
            file_path: Ruta al archivo PDF
            output_path: Ruta para guardar el JSON (opcional)
            max_pages: Máximo de páginas a procesar
            send_to_webhook: Si enviar al webhook (None = usar configuración)
            
        Returns:
            Diccionario con los datos extraídos
        """
        logger.info(f"Iniciando procesamiento de: {file_path}")
        
        # Recortar PDF si es necesario
        trimmed_path = self.trim_pdf(file_path, max_pages)
        
        try:
            # Extraer datos
            result = self.process_pdf_with_gemini(trimmed_path)
            
            # Guardar resultado si se especifica ruta
            if output_path:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=4, ensure_ascii=False)
                logger.info(f"Resultado guardado en: {output_path}")
            
            # Enviar al webhook si está configurado
            webhook_settings = self.config.get('webhook_settings', {})
            should_send = send_to_webhook if send_to_webhook is not None else webhook_settings.get('enabled', False)
            
            if should_send and webhook_settings.get('default_url'):
                try:
                    webhook_response = self._send_to_configured_webhook(result)
                    logger.info("✅ Datos enviados al webhook exitosamente!")
                    result['webhook_response'] = webhook_response
                except Exception as e:
                    logger.warning(f"⚠️ Error enviando al webhook: {e}")
                    result['webhook_error'] = str(e)
            
            return result
            
        finally:
            # Limpiar archivo temporal si se creó
            if trimmed_path != file_path and os.path.exists(trimmed_path):
                os.unlink(trimmed_path)
    
    def _diagnose_webhook_error(self, response, webhook_url: str) -> str:
        """
        Diagnostica errores específicos de webhook y proporciona soluciones
        
        Args:
            response: Respuesta HTTP del webhook
            webhook_url: URL del webhook
            
        Returns:
            Mensaje de diagnóstico específico
        """
        status_code = response.status_code
        response_text = response.text
        
        # Diagnóstico específico para n8n webhooks
        if "n8n.cloud" in webhook_url:
            if status_code == 404:
                if "not registered" in response_text:
                    return """
🔧 PROBLEMA DETECTADO: Webhook de n8n no está activo

📋 INSTRUCCIONES PARA SOLUCIONARLO:
1. Ve a tu workspace de n8n en https://magia.app.n8n.cloud
2. Abre el workflow que contiene este webhook
3. Haz clic en el botón "Execute Workflow" (▶️) en el canvas
4. El webhook se activará y estará listo para recibir datos
5. Vuelve a ejecutar el extractor

⚠️  NOTA: Los webhooks de n8n en modo test se desactivan después de cada uso.
Para uso continuo, configura el workflow en modo "Always On" o "Production".

🔗 Webhook URL: {webhook_url}
""".format(webhook_url=webhook_url)
                    
            elif status_code == 429:
                return """
⚠️  PROBLEMA: Límite de rate limit alcanzado en n8n
🔧 SOLUCIÓN: Espera unos minutos antes de volver a intentar
"""
        
        # Diagnóstico general para otros webhooks
        if status_code == 401:
            return "🔐 Error de autenticación: Verifica las credenciales del webhook"
        elif status_code == 403:
            return "🚫 Acceso prohibido: El webhook rechazó la conexión"
        elif status_code == 500:
            return "⚙️  Error del servidor: Problema en el endpoint del webhook"
        else:
            return f"❌ Error HTTP {status_code}: {response_text}"

    def _send_to_configured_webhook(self, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envía los datos al webhook configurado en config.json
        
        Args:
            json_data: Datos a enviar
            
        Returns:
            Información sobre la respuesta del webhook
        """
        webhook_settings = self.config.get('webhook_settings', {})
        
        if not webhook_settings.get('enabled', False):
            raise Exception("Webhook no está habilitado en la configuración")
        
        webhook_url = webhook_settings.get('default_url')
        if not webhook_url:
            raise Exception("URL del webhook no configurada")
        
        # Configurar headers desde config
        headers = webhook_settings.get('headers', {})
        if not headers.get('Content-Type'):
            headers['Content-Type'] = 'application/json'
        if not headers.get('User-Agent'):
            headers['User-Agent'] = 'Legal-Document-Extractor/2.0'
        
        # Configurar timeout
        timeout = webhook_settings.get('timeout', 60)
        method = webhook_settings.get('method', 'POST').upper()
        
        try:
            logger.info(f"Enviando datos al webhook configurado: {webhook_url}")
            logger.info(f"Método: {method}, Timeout: {timeout}s")
            
            if method == 'POST':
                response = requests.post(
                    webhook_url,
                    data=json.dumps(json_data, ensure_ascii=False),
                    headers=headers,
                    timeout=timeout
                )
            else:
                raise Exception(f"Método HTTP no soportado: {method}")
            
            # Verificar el status code manualmente para manejar errores específicos
            if response.status_code >= 400:
                diagnosis = self._diagnose_webhook_error(response, webhook_url)
                logger.error(f"📋 Diagnóstico del webhook:\n{diagnosis}")
                raise Exception(f"Error HTTP {response.status_code}: {response.text}\n\nDiagnóstico:\n{diagnosis}")
            
            logger.info(f"✅ Webhook enviado exitosamente. Código: {response.status_code}")
            return {
                'statusCode': response.status_code,
                'response': response.text,
                'url': webhook_url,
                'timestamp': datetime.now().isoformat()
            }
            
        except requests.exceptions.Timeout:
            logger.error(f"❌ Timeout enviando al webhook después de {timeout}s")
            raise Exception(f"Timeout del webhook después de {timeout} segundos")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error al enviar webhook: {e}")
            
            # Si tenemos una respuesta HTTP, diagnosticar el error específico
            if hasattr(e, 'response') and e.response is not None:
                diagnosis = self._diagnose_webhook_error(e.response, webhook_url)
                logger.error(f"📋 Diagnóstico:\n{diagnosis}")
                raise Exception(f"Error en webhook: {str(e)}\n\nDiagnóstico:\n{diagnosis}")
            else:
                raise Exception(f"Error en webhook: {str(e)}")
        except Exception as e:
            # Manejar otros errores HTTP que no sean requests.exceptions
            if hasattr(e, 'response') and e.response is not None:
                diagnosis = self._diagnose_webhook_error(e.response, webhook_url)
                logger.error(f"📋 Diagnóstico:\n{diagnosis}")
                raise Exception(f"Error en webhook: {str(e)}\n\nDiagnóstico:\n{diagnosis}")
            else:
                raise Exception(f"Error en webhook: {str(e)}")

    def send_to_webhook(self, webhook_url: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envía los datos extraídos a un webhook
        
        Args:
            webhook_url: URL del webhook
            json_data: Datos a enviar
            
        Returns:
            Información sobre la respuesta del webhook
        """
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Legal-Document-Extractor/2.0'
        }
        
        try:
            logger.info(f"Enviando datos al webhook: {webhook_url}")
            response = requests.post(
                webhook_url,
                data=json.dumps(json_data, ensure_ascii=False),
                headers=headers
            )
            response.raise_for_status()
            
            logger.info(f"Webhook enviado exitosamente. Código: {response.status_code}")
            return {
                'statusCode': response.status_code,
                'response': response.text
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error al enviar webhook: {e}")
            raise Exception(f"Error en webhook: {str(e)}")


def main():
    """Función principal para ejecución desde línea de comandos"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Extractor de documentos legales')
    parser.add_argument('--pdf', required=True, help='Ruta al archivo PDF')
    parser.add_argument('--output', help='Ruta para guardar el JSON')
    parser.add_argument('--webhook', help='URL del webhook (opcional, sobrescribe configuración)')
    parser.add_argument('--no-webhook', action='store_true', help='Deshabilitar envío automático al webhook')
    parser.add_argument('--pages', type=int, default=2, help='Máximo de páginas a procesar')
    
    args = parser.parse_args()
    
    try:
        extractor = LegalDocumentExtractor()
        
        # Determinar si enviar al webhook
        send_webhook = not args.no_webhook
        
        result = extractor.process_document(
            file_path=args.pdf,
            output_path=args.output,
            max_pages=args.pages,
            send_to_webhook=send_webhook
        )
        
        print("✅ Procesamiento completado!")
        
        # Mostrar resultado sin el webhook_response si existe
        result_display = {k: v for k, v in result.items() if k not in ['webhook_response', 'webhook_error']}
        print(json.dumps(result_display, indent=2, ensure_ascii=False))
        
        # Si se especifica webhook personalizado (sobrescribe configuración)
        if args.webhook and send_webhook:
            try:
                webhook_response = extractor.send_to_webhook(args.webhook, result_display)
                print(f"✅ Datos enviados al webhook personalizado: {args.webhook}")
            except Exception as e:
                print(f"❌ Error enviando al webhook personalizado: {e}")
        
        # Mostrar información del webhook automático si se usó
        if 'webhook_response' in result:
            print(f"✅ Datos enviados automáticamente al webhook configurado")
        elif 'webhook_error' in result:
            print(f"⚠️ Error en webhook automático: {result['webhook_error']}")
            
    except Exception as e:
        logger.error(f"Error en procesamiento: {e}")
        exit(1)


if __name__ == "__main__":
    main()
