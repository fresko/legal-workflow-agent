import json
import os
import boto3
import tempfile
import requests
import google.generativeai as genai
import urllib.parse
import PyPDF2
import io
import re
from urllib.parse import unquote_plus
from datetime import datetime, timedelta

print('Loading functionn 2')

# Configurar API key de Google Gemini desde variable de entorno
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
MODEL_NAME = os.environ.get('MODEL_NAME')
PROMPT_EXTRADATA = os.environ.get('PROMPT')
SYS_INSTRUCTION = os.environ.get('SYS_INSTRUCTION')
# Inicializar el cliente de S3
s3_client = boto3.client('s3')

# Configurar Gemini API
genai.configure(api_key=GOOGLE_API_KEY)
##
def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))

    # Get the object from the event and show its content type
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    webhook_url = event.get('webhook_url', WEBHOOK_URL)
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)     
        print("CONTENT TYPE: " + response['ContentType'])
        print(f"1.Procesando archivo: s3://{bucket}/{key}")
         # Extraer parámetros del evento
        #bucket = event.get('bucket')
        #key = event.get('key')
        #webhook_url = event.get('webhook_url', WEBHOOK_URL)
        
        # Validar que se recibieron los parámetros necesarios
        #if not bucket or not key:
        #    return {
        #        'statusCode': 400,
        #        'body': json.dumps({
        #            'error': 'Se requieren los parámetros "bucket" y "key"'
        #        })
        #    }
         # Validar que se recibieron los parámetros necesarios
        
        
        # Si la clave viene codificada en URL, decodificarla
        #key = unquote_plus(key)          
        # Descargar el archivo de S3 a un archivo temporal
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            try:
                s3_client.download_file(bucket, key, tmp_file.name)
            except s3_client.exceptions.NoSuchKey:
                raise Exception(f"El archivo '{key}' no existe en el bucket '{bucket}'")
            except s3_client.exceptions.ClientError as e:
                raise Exception(f"Error al descargar el archivo de S3: {e}")
            file_path = tmp_file.name
            # Verificar si es un PDF y recortarlo
            if key.lower().endswith('.pdf'):
                print(f"2.Recortando PDF a las primeras 2 páginas:'{file_path}' // {key}")
                trimmed_file_path = trim_pdf(file_path, max_pages=2)   
                print(f"3.Ruta Tmp Recortado:'{trimmed_file_path}'")         
                # Si el recorte fue exitoso, eliminar el archivo original
                if trimmed_file_path != file_path:
                    #os.unlink(file_path)
                    file_path = trimmed_file_path   
            # Validar que el archivo es un PDF
            #if not file_path.endswith('pdf'):
            #    raise Exception(f"El archivo '{key}' no es un archivo PDF válido")            
                    print(f"4.Gemini con Archivo Recortado:'{file_path}'")
                    # Procesar el PDF con Gemini
                    response_data = process_pdf_with_gemini(file_path, MODEL_NAME,PROMPT_EXTRADATA,SYS_INSTRUCTION)            
                    # Enviar los resultados al webhook
                    webhook_response = send_to_webhook(webhook_url, response_data)
                     # Eliminar el archivo temporal
                    if webhook_response:
                       os.unlink(file_path) 
                       print(f"5.Archivo Temporal Eliminado:'{file_path}'")        
             # Devolver respuesta
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Procesamiento completado exitosamente',
                    'pdf_data': response_data,
                    'webhook_response': webhook_response
                })
            }
        #return response['ContentType']
    except Exception as e:
        print(e)
        print('Error getting object {} from bucket {}. Make sure they exist and your bucket is in the same region as this function.'.format(key, bucket))
        raise e

def trim_pdf(file_path, max_pages=2):

    """Recorta un PDF a un número máximo de páginas"""
    try:
        # Abrir el PDF descargado de S3
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            pdf_writer = PyPDF2.PdfWriter()
            
            # Determinar cuántas páginas procesar
            pages_to_process = min(len(pdf_reader.pages), max_pages)
            print(f"Procesando {pages_to_process} páginas de un total de {len(pdf_reader.pages)}")
            
            # Agregar solo las primeras páginas
            for page_num in range(pages_to_process):
                pdf_writer.add_page(pdf_reader.pages[page_num])
                
            # Crear un nuevo archivo temporal en una ruta diferente
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_trimmed:
                trimmed_file_path = tmp_trimmed.name
            
            # Guardar el PDF recortado en un archivo temporal nuevo
            #trimmed_file_path = f"{file_path}_trimmed.pdf"
            with open(trimmed_file_path, 'wb') as output_file:
                pdf_writer.write(output_file)
            
            return trimmed_file_path
    except Exception as e:
        print(f"Error al recortar el PDF: {e}")
        # En caso de error, devolvemos el archivo original
        return file_path

def process_pdf_with_gemini(file_path, model_name, prompt,system_instruction):
    """
    Procesa un archivo PDF con el modelo Gemini y extrae información estructurada.
    
    Args:
        file_path: Ruta al archivo PDF temporal
        model_name: Nombre del modelo de Gemini a utilizar
        prompt: Prompt personalizado para la extracción
        
    Returns:
        dict: Datos extraídos en formato JSON según el schema definido
    """
    # Definir el schema mejorado para la respuesta
    schema = {
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
    
    # Configurar parámetros de generación optimizados
    generation_config = {
        "temperature": 0.1,
        "top_p": 0.8,
        "top_k": 20,
        "max_output_tokens": 8192,
        "response_mime_type": "application/json",
        "response_schema": schema,
    }
    
    # Prompt mejorado para mejor detección
    enhanced_prompt = PROMPT_EXTRADATA
    
    # Inicializar el modelo con instrucciones del sistema
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_instruction,
        generation_config=generation_config,
    )
    
    # Subir el archivo a Gemini
    files = genai.upload_file(file_path, mime_type="application/pdf")
    print(f"Uploaded file '{files.display_name}' as: {files.uri}")
    
    # Usar el prompt mejorado si no se proporciona uno personalizado
    final_prompt = prompt if prompt and prompt.strip() else enhanced_prompt
    
    try:
        # Generar contenido con Gemini
        print("Generando contenido con Gemini...")
        response = model.generate_content([files, final_prompt])
        
        if not response.text:
            raise Exception("Respuesta vacía de Gemini")
        
        result_json = json.loads(response.text)
        print("Datos extraídos exitosamente")
        
        # Validar estructura básica
        _validate_response(result_json)
        
        # Procesar y validar fechas
        result_json = _process_datetime_fields(result_json)
        
        return result_json
        
    except json.JSONDecodeError as e:
        print(f"Error al procesar la respuesta JSON: {e}")
        print(f"Respuesta recibida: {response.text}")
        raise Exception("La respuesta no es un JSON válido")
    except Exception as e:
        print(f"Error en procesamiento: {e}")
        raise

def _convert_to_24_hour_format(hora_str, jornada):
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
                print(f"No se pudo extraer hora de: '{hora_str}'")
                return None
        else:
            horas = int(hora_match.group(1))
            minutos = int(hora_match.group(2))
        
        # Detectar si ya está en formato 24 horas
        if horas > 12:
            print(f"Hora ya en formato 24h: {horas}:{minutos:02d}")
            return f"{horas:02d}:{minutos:02d}"
        
        # Validar rangos para formato 12h
        if horas < 1 or horas > 12 or minutos < 0 or minutos > 59:
            print(f"Hora fuera de rango válido: {horas}:{minutos}")
            # Intentar corrección automática si es formato 24h mal detectado
            if horas >= 0 and horas <= 23 and minutos >= 0 and minutos <= 59:
                print(f"Corrigiendo a formato 24h: {horas}:{minutos}")
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
            print(f"Jornada no reconocida: '{jornada}', asumiendo formato tal como está")
            # Si no hay jornada clara, mantener la hora como está
            if horas <= 12:
                print(f"Sin jornada clara, manteniendo hora: {horas}:{minutos:02d}")
            
        # Validación final
        if horas < 0 or horas > 23:
            print(f"Hora final fuera de rango: {horas}:{minutos}")
            return None
            
        resultado = f"{horas:02d}:{minutos:02d}"
        print(f"Conversión exitosa: '{hora_str}' {jornada} → {resultado}")
        return resultado
        
    except (ValueError, AttributeError) as e:
        print(f"Error convirtiendo hora '{hora_str}' con jornada '{jornada}': {e}")
        return None

def _process_datetime_fields(data):
    """Procesa y valida los campos de fecha y hora, creando fecha_inicio y fecha_fin"""
    try:
        fecha_conciliacion = data.get('fecha_conciliacion')
        hora_conciliacion = data.get('hora_conciliacion')
        jornada = data.get('jornada', '').upper()
        
        # Log de datos recibidos
        print(f"Procesando fecha/hora: fecha={fecha_conciliacion}, hora={hora_conciliacion}, jornada={jornada}")
        
        # Si no tenemos los datos básicos, intentar extraer de otros campos
        if not fecha_conciliacion or not hora_conciliacion:
            print("Faltan datos de fecha/hora, no se pueden generar fecha_inicio y fecha_fin")
            return data
        
        # Validar que la jornada esté presente y sea válida
        if not jornada or jornada not in ['AM', 'PM']:
            print(f"Jornada inválida o faltante: '{jornada}'. Intentando inferir de la hora...")
            
            # Intentar inferir la jornada de la hora si está en formato 24h
            try:
                hora_num = int(hora_conciliacion.split(':')[0])
                if hora_num >= 12:
                    jornada = 'PM'
                    print(f"Jornada inferida como PM basándose en hora {hora_num}")
                else:
                    jornada = 'AM'
                    print(f"Jornada inferida como AM basándose en hora {hora_num}")
            except:
                print("No se pudo inferir la jornada, usando valor original")
        
        # Parsear la hora y convertir a formato 24 horas
        hora_24 = _convert_to_24_hour_format(hora_conciliacion, jornada)
        
        if hora_24:
            # Crear fecha_inicio en formato ISO 8601
            fecha_inicio_str = f"{fecha_conciliacion}T{hora_24}:00"
            
            # Validar que la fecha sea válida
            try:
                fecha_inicio_dt = datetime.fromisoformat(fecha_inicio_str)
            except ValueError as e:
                print(f"Fecha inválida: {fecha_inicio_str}, error: {e}")
                return data
            
            # Crear fecha_fin (una hora después)
            fecha_fin_dt = fecha_inicio_dt + timedelta(hours=1)
            fecha_fin_str = fecha_fin_dt.strftime("%Y-%m-%dT%H:%M:%S")
            
            # Agregar los nuevos campos
            data['fecha_inicio'] = fecha_inicio_str
            data['fecha_fin'] = fecha_fin_str
            
            # Actualizar la jornada en caso de que haya sido inferida
            data['jornada'] = jornada
            
            print(f"✅ Fechas procesadas exitosamente:")
            print(f"   🕐 Inicio: {fecha_inicio_str}")
            print(f"   🕑 Fin: {fecha_fin_str}")
            print(f"   🌅 Jornada: {jornada}")
        else:
            print("No se pudo procesar la hora, formato no reconocido")
            print(f"Datos recibidos: hora='{hora_conciliacion}', jornada='{jornada}'")
            
    except Exception as e:
        print(f"Error procesando fechas: {e}")
        
    return data

def _validate_emails(data):
    """Valida formato de emails en la respuesta"""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    
    # Validar emails en convocantes
    for convocante in data.get('convocantes', []):
        email = convocante.get('email', '')
        if email and not re.search(email_pattern, email):
            print(f"Email posiblemente inválido en convocante: {email}")
    
    # Validar emails en convocados
    for convocado in data.get('convocados', []):
        email = convocado.get('mail', '')
        if email and not re.search(email_pattern, email):
            print(f"Email posiblemente inválido en convocado: {email}")

def _validate_response(data):
    """Valida la estructura de la respuesta"""
    if 'convocantes' not in data or not data['convocantes']:
        print("⚠️ No se encontraron convocantes en la respuesta")
    
    if 'convocados' not in data or not data['convocados']:
        print("⚠️ No se encontraron convocados en la respuesta")
    
    # Validar emails
    _validate_emails(data)

def send_to_webhook(webhook_url, json_data):
    """
    Envía los datos extraídos a un webhook.
    
    Args:
        webhook_url: URL del webhook
        json_data: Datos en formato diccionario para enviar como JSON
        
    Returns:
        dict: Información sobre la respuesta del webhook
    """
    try:
        # Configurar headers para la solicitud
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Lambda-Legal-Workflow-Agent/1.0'
        }
        
        print(f"Enviando datos al webhook: {webhook_url}")
        
        # Realizar la petición POST
        response = requests.post(
            webhook_url,
            data=json.dumps(json_data),
            headers=headers
        )
        
        # Verificar si la petición fue exitosa
        response.raise_for_status()
        
        print(f"Webhook enviado con éxito. Código de estado: {response.status_code}")
        
        return {
            'statusCode': response.status_code,
            'response': response.text
        }
        
    except requests.exceptions.RequestException as e:
        print(f"Error al enviar el webhook: {e}")
        raise Exception(f"Error en la solicitud al webhook: {str(e)}")



