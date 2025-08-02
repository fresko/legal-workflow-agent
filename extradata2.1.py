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
SCHEMA = os.environ.get('SCHEMA')
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

def process_pdf_with_gemini(file_path, model_name, prompt, system_instruction):
    """
    Procesa un archivo PDF con el modelo Gemini y extrae información estructurada.
    
    Args:
        file_path: Ruta al archivo PDF temporal
        model_name: Nombre del modelo de Gemini a utilizar
        prompt: Prompt personalizado para la extracción
        system_instruction: Instrucciones del sistema para el modelo
        
    Returns:
        dict: Datos extraídos en formato JSON según el SCHEMA definido
    """
    try:
        # Convertir SCHEMA de string a dict si es necesario
        SCHEMA_dict = SCHEMA
        if isinstance(SCHEMA, str):
            try:
                SCHEMA_dict = json.loads(SCHEMA)
            except json.JSONDecodeError:
                print("⚠️ SCHEMA inválido, usando SCHEMA por defecto")
                SCHEMA_dict = None
        
        # Configurar parámetros de generación optimizados
        generation_config = {
            "temperature": 0.1,
            "top_p": 0.8,
            "top_k": 20,
            "max_output_tokens": 8192,
            "response_mime_type": "application/json",
        }
        
        # Solo agregar SCHEMA si es válido
        if SCHEMA_dict:
            generation_config["response_SCHEMA"] = SCHEMA_dict
        
        # Inicializar el modelo con instrucciones del sistema
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_instruction,
            generation_config=generation_config,
        )
        
        # Subir el archivo a Gemini
        files = genai.upload_file(file_path, mime_type="application/pdf")
        print(f"Uploaded file '{files.display_name}' as: {files.uri}")
        
        # Usar el prompt proporcionado o uno por defecto
        final_prompt = prompt if prompt and prompt.strip() else "Extrae toda la información relevante del documento en formato JSON"
        
        # Generar contenido con Gemini
        print("Generando contenido con Gemini...")
        response = model.generate_content([files, final_prompt])
        
        if not response.text:
            raise Exception("Respuesta vacía de Gemini")
        
        # Parsear la respuesta JSON
        result_json = json.loads(response.text)
        print("Datos extraídos exitosamente")
        print(f"JSON extraído: {json.dumps(result_json, indent=2)}")
        
        # Validación básica de la estructura
        if isinstance(result_json, dict):
            print("✅ Estructura JSON válida")
            
            # Validaciones opcionales
            if 'convocantes' in result_json:
                print(f"✅ Convocantes encontrados: {len(result_json.get('convocantes', []))}")
            
            if 'convocados' in result_json:
                print(f"✅ Convocados encontrados: {len(result_json.get('convocados', []))}")
                
        else:
            print("⚠️ La respuesta no es un objeto JSON válido")
        
        return result_json
        
    except json.JSONDecodeError as e:
        print(f"❌ Error al procesar la respuesta JSON: {e}")
        print(f"Respuesta recibida: {response.text if 'response' in locals() else 'No response'}")
        raise Exception(f"La respuesta no es un JSON válido: {str(e)}")
        
    except Exception as e:
        print(f"❌ Error en procesamiento con Gemini: {e}")
        raise Exception(f"Error al procesar PDF con Gemini: {str(e)}")
    
    finally:
        # Limpiar el archivo subido de Gemini si es posible
        try:
            if 'files' in locals():
                genai.delete_file(files.name)
                print(f"🗑️ Archivo eliminado de Gemini: {files.name}")
        except Exception as cleanup_error:
            print(f"⚠️ No se pudo limpiar archivo de Gemini: {cleanup_error}")

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



