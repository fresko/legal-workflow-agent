import os
import json  # Importar el módulo json
import time
import tempfile
from hashlib import blake2b
from tempfile import NamedTemporaryFile
from dotenv import load_dotenv
import requests
import streamlit as st
from flatten_json import flatten 
from streamlit_pdf_viewer import pdf_viewer
import google.generativeai as genai
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import pandas as pd
import datetime


# Manejo de Sessiones
if 'doc_id' not in st.session_state:
    st.session_state['doc_id'] = None

if 'hash' not in st.session_state:
    st.session_state['hash'] = None

if 'git_rev' not in st.session_state:
    st.session_state['git_rev'] = "unknown"
    if os.path.exists("revision.txt"):
        with open("revision.txt", 'r') as fr:
            from_file = fr.read()
            st.session_state['git_rev'] = from_file if len(from_file) > 0 else "unknown"

if 'uploaded' not in st.session_state:
    st.session_state['uploaded'] = False

if 'binary' not in st.session_state:
    st.session_state['binary'] = None

if 'annotations' not in st.session_state:
    st.session_state['annotations'] = []

if 'pages' not in st.session_state:
    st.session_state['pages'] = None

if 'page_selection' not in st.session_state:
    st.session_state['page_selection'] = []

# Nuevas variables de sesión para la configuración de la API
if 'api_key' not in st.session_state:
    st.session_state['api_key'] = ""

if 'selected_model' not in st.session_state:
    st.session_state['selected_model'] = "gemini-1.5-flash-002"

# Inicializa variables de estado para control de flujo
if 'fase_proceso' not in st.session_state:
    st.session_state['fase_proceso'] = 'inicial'  # Posibles valores: inicial, interpretado, agendado
    
if 'datos_interpretacion' not in st.session_state:
    st.session_state['datos_interpretacion'] = None

# Configuración de la página de Streamlit
st.set_page_config(
    page_title="AGente AI - Documentos/Facturas",
    page_icon="🤖",
    initial_sidebar_state="expanded",  # Cambiar a 'collapsed' para permitir ocultar la barra lateral   
    menu_items={
        'Get Help': 'https://www.digitalmagia.com',
        'Report a bug': "https://www.digitalmagia.com",
        'About': "Forma para completar ,corregir y aprobar los datos antes de enviarlo a plataforma de alojamiento."
    }
)

# Crear Tablas 
tab1, tab2 = st.tabs(["📄 PDF", "🤖 Agent AI"])
# Crear dos columnas
col1, col2, col3 = st.columns(3)

# Ejemplo de estructura para annotations
annotations = [
    {
        "page": 1,
        "type": "title",
        "content": "Análisis de Datos con Python",
        "coordinates": [100, 200, 300, 400]
    },
    {
        "page": 1,
        "type": "author",
        "content": "Juan Pérez",
        "coordinates": [100, 450, 300, 500]
    },
    {
        "page": 2,
        "type": "section",
        "content": "Introducción",
        "coordinates": [100, 100, 300, 150]
    }
]

# Ejemplo de estructura para pages
pages = [
    {
        "page_number": 1,
        "text": "Análisis de Datos con Python\nJuan Pérez\n...",
        "dimensions": [595, 842]
    },
    {
        "page_number": 2,
        "text": "Introducción\nEn este documento, exploraremos...",
        "dimensions": [595, 842]
    }
]

# Función para manejar la carga de un nuevo archivo
def new_file():
    st.session_state['doc_id'] = None
    st.session_state['uploaded'] = True
    st.session_state['annotations'] = []
    st.session_state['binary'] = None

# Función para cargar el archivo JSON
def load_json(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def text_to_json(text_data):
    try:
        json_data = json.loads(text_data)
        return json_data
    except json.JSONDecodeError as e:
        st.error(f"Error al convertir texto a JSON: {str(e)}")
        return None

# Función para aplanar y limpiar datos JSON
def flatten_json_data(json_data):
    flat_json = flatten(json_data)
    cleaned_data = {}
    for key, value in flat_json.items():
        if isinstance(value, (list, dict)):
            value = str(value)
        clean_key = key.replace('_', ' ').title()
        cleaned_data[clean_key] = value
    return cleaned_data

def create_dynamic_form(json_data, tab):
    tab.title("Formulario Dinámico")
    form_approve = tab.form(key='dynamic_form')
    form_data = {}
    for key, value in json_data.items():
        if isinstance(value, bool):
            form_data[key] = form_approve.checkbox(key, value=value)
        elif isinstance(value, (int, float)):
            form_data[key] = form_approve.number_input(key, value=value)
        else:
            form_data[key] = form_approve.text_input(key, value=str(value))
    submit_button = form_approve.form_submit_button(label='Enviar')
    if submit_button:
        tab.success("Formulario enviado exitosamente!")

def tabular_validation_form(json_data, tab):
    """Formulario de validación usando tablas editables para personas y campos simples para fechas"""
    
    tab.subheader("📋 Validación de Datos en Formato Tabular")
    
    # Convocantes como dataframe
    tab.subheader("Convocantes")
    convocantes = json_data.get("convocantes", [])
    if not convocantes:
        convocantes = [{"rol": "", "nombre": "", "email": "", "telefono": ""}]
    
    # Convertir a dataframe
    df_convocantes = pd.DataFrame(convocantes)
    edited_df_convocantes = tab.data_editor(df_convocantes, 
                                          num_rows="dynamic", 
                                          use_container_width=True,
                                          height=200,
                                          width=900,
                                          column_config={
                                              "rol": st.column_config.TextColumn("Rol", width="medium"),
                                              "nombre": st.column_config.TextColumn("Nombre", width="medium"),
                                              "email": st.column_config.TextColumn("Email", width="medium"),
                                              "telefono": st.column_config.TextColumn("Teléfono", width="medium")
                                          })
    
    # Convocados como dataframe
    tab.subheader("Convocados")
    convocados = json_data.get("convocados", [])
    if not convocados:
        convocados = [{"rol": "", "nombre": "", "mail": "", "telefono": ""}]
    
    # Convertir a dataframe
    df_convocados = pd.DataFrame(convocados)
    edited_df_convocados = tab.data_editor(df_convocados, 
                                         num_rows="dynamic", 
                                         use_container_width=True,
                                         height=200,
                                         width=900,
                                         column_config={
                                             "rol": st.column_config.TextColumn("Rol", width="medium"),
                                             "nombre": st.column_config.TextColumn("Nombre", width="medium"),
                                             "mail": st.column_config.TextColumn("Email", width="medium"),
                                             "telefono": st.column_config.TextColumn("Teléfono", width="medium")
                                         })
    
    # Fecha y hora
    col1, col2 = tab.columns(2)
    with col1:
        fecha_str = json_data.get("fecha_conciliacion", "")
        try:
            fecha_def = datetime.datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else datetime.date.today()
        except ValueError:
            fecha_def = datetime.date.today()
        fecha = st.date_input("Fecha de conciliación", value=fecha_def)
    
    with col2:
        hora_str = json_data.get("hora_conciliacion", "")
        try:
            hora_def = datetime.datetime.strptime(hora_str, "%H:%M").time() if hora_str else datetime.datetime.now().time()
        except ValueError:
            hora_def = datetime.datetime.now().time()
        hora = st.time_input("Hora de conciliación", value=hora_def)
    
    # Jornada AM/PM
    jornada = json_data.get("jornada AM/PM", "")
    jornada_options = ["AM", "PM"]
    selected_jornada = tab.selectbox(
        "Jornada",
        options=jornada_options,
        index=jornada_options.index(jornada) if jornada in jornada_options else 0
    )
    
    # Extraer correos de los convocados
    convocados_emails = [convocado.get("mail", "") for convocado in edited_df_convocados.to_dict(orient='records') if "mail" in convocado]
    
    # Convertir dataframes a listas de diccionarios
    convocantes_dict = edited_df_convocantes.to_dict(orient='records')
    convocados_dict = edited_df_convocados.to_dict(orient='records')
    
    # Construir datos para enviar
    data_to_send = {
        "convocantes": convocantes_dict,
        "convocados": convocados_dict,
        "fecha_conciliacion": fecha.strftime("%Y-%m-%d"),
        "hora_conciliacion": hora.strftime("%H:%M"),
        "jornada AM/PM": selected_jornada,
        "correos_convocados": convocados_emails  # Agregar lista de correos de convocados
    }
    
    return data_to_send

def upload_to_gemini(path, mime_type=None):
    file = genai.upload_file(path, mime_type=mime_type)
    print(f"Uploaded file '{file.display_name}' as: {file.uri}")
    return file

def wait_for_files_active(files):
    print("Waiting for file processing...")
    for name in (file.name for file in files):
        file = genai.get_file(name)
        while file.state.name == "PROCESSING":
            print(".", end="", flush=True)
            time.sleep(10)
            file = genai.get_file(name)
        if file.state.name != "ACTIVE":
            raise Exception(f"File {file.name} failed to process")
    print("...all files ready")
    print()

def crete_prompt(file_content, selected_llm, prompt=None, system_instructions=None):
    """
    Crea una interacción con el modelo de IA usando un archivo PDF y devuelve la respuesta.
    
    Args:
        file_content (str): Ruta al archivo PDF
        selected_llm (str): Nombre del modelo LLM a utilizar
        prompt (str, opcional): Instrucción específica para el modelo
        system_instructions (str, opcional): Instrucciones del sistema para guiar al modelo
        
    Returns:
        Respuesta del modelo generativo
    """
    # Prompt por defecto si no se proporciona uno
    if prompt is None:
        prompt = "identifica los datos de convocantes, convocados, fecha de audicencia, jornada am o pm del archivo adjunto"
    
    schema = {
    "type": "object",
    "properties": {
        "convocantes": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
            "rol": {
                "type": "string"
            },
            "nombre": {
                "type": "string"
            },
            "email": {
                "type": "string"
            },
            "telefono": {
                "type": "string"
            }
            },
            "required": [
            "email",
            "nombre"
            ]
        }
        },
        "convocados": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
            "rol": {
                "type": "string"
            },
            "nombre": {
                "type": "string"
            },
            "mail": {
                "type": "string"
            },
            "telefono": {
                "type": "string"
            }
            },
            "required": [
            "mail",
            "nombre"
            ]
        }
        },
       "fecha_conciliacion": {
        "type": "string"
     },
     "hora_conciliacion": {
        "type": "string"
     },
     "fecha_conciliacion": {
        "type": "string"
     },
     "jornada AM/PM": {
        "type": "string"
     }
    },  
    "required": [
        "convocantes",
        "convocados"
    ]
    }
    
    generation_config = {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
        "response_mime_type": "application/json",
        "response_schema": schema,
    }
    
    model = genai.GenerativeModel(
        model_name=selected_llm,       
        generation_config=generation_config,
    )
    
    files = genai.upload_file(file_content, mime_type="application/pdf")
    print(f"Uploaded file '{files.display_name}' as: {files.uri}")
    
    # Crear la historia del chat
    history = []
    
    # Añadir instrucciones del sistema si se proporcionan
    if system_instructions:
        history.append({
            "role": "system",
            "parts": [system_instructions]
        })
    
    # Añadir mensaje del usuario con archivo y prompt
    history.append({
        "role": "user",
        "parts": [
            files,
            prompt,
        ],
    })
    
    # Iniciar la sesión de chat
    chat_session = model.start_chat(history=history)
    
    # Enviar mensaje para obtener respuesta
    response = chat_session.send_message("Analiza el documento según las instrucciones proporcionadas")
    
    return response

def send_webhook(webhook_url, json_data):
    """
    Envía datos JSON a un webhook especificado.
    
    Args:
        webhook_url (str): La URL del webhook al que enviar los datos
        json_data (dict): Los datos en formato diccionario para enviar como JSON
        
    Returns:
        requests.Response: El objeto de respuesta de la petición HTTP
    """
    # Configura los headers para especificar que estamos enviando JSON
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Legal-Workflow-Agent/1.0'
    }
    print(f"posting to {webhook_url}")
    try:
        # Realiza la petición POST con los datos JSON
        response = requests.post(
            webhook_url, 
            data=json.dumps(json_data),
            headers=headers
        )
        
        # Verifica si la petición fue exitosa
        response.raise_for_status()
        
        # Imprime información sobre la respuesta
        print(f"Webhook enviado con éxito. Código de estado: {response.status_code}")
        print(f"Respuesta: {response.text}")
        
        return response
        
    except requests.exceptions.RequestException as e:
        print(f"Error al enviar el webhook: {e}")
        return None


# Configuración de la barra lateral
with st.sidebar:
    st.title("Agendamiento de Audiencia")
    st.subheader("Cargue de Documentos con Agentes AI .")
    uploaded_file = st.file_uploader("Upload an article",
                                     type=("pdf"),
                                     on_change=new_file,
                                     help="The full-text is extracted using Gen AI Gemini,GPT4. ")
    
    # Configuración de API - MOVIDO AL SIDEBAR
    st.header("Configuración de IA")
    # Configurar API Key
    api_key = st.text_input('GOOGLE_API_KEY', type='password', value=st.session_state['api_key'])
    st.session_state['api_key'] = api_key

    if api_key:
        os.environ["GOOGLE_API_KEY"] = api_key
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    
    # Selección de modelo
    options = ["gemini-1.5-flash-002", "gemini-1.0-pro", "gemini-1.5-pro", "gemini-2.0-flash-exp", "gemini-2.0-pro-exp","gemini-2.5-pro-preview-03-25", "gemini-2.5-flash-preview-04-17"]
    selected_llm = st.selectbox("Selecciona el modelo LLM:", options, index=options.index(st.session_state['selected_model']))
    st.session_state['selected_model'] = selected_llm
    
    # Resto de la configuración del sidebar
    st.header("Contenido del PDF")
    enable_text = st.toggle('Render text in PDF', value=False, disabled=not st.session_state['uploaded'],
                            help="Enable the selection and copy-paste on the PDF")
    st.header("Documento - Secciones")
    highlight_title = st.toggle('Hotel', value=True, disabled=not st.session_state['uploaded'])
    highlight_person_names = st.toggle('General', value=True, disabled=not st.session_state['uploaded'])
    highlight_affiliations = st.toggle('Habitaciones', value=True, disabled=not st.session_state['uploaded'])
    highlight_head = st.toggle('Acomodaciones', value=True, disabled=not st.session_state['uploaded'])
    highlight_sentences = st.toggle('Compra', value=False, disabled=not st.session_state['uploaded'])
    highlight_paragraphs = st.toggle('Venta', value=True, disabled=not st.session_state['uploaded'])
    highlight_notes = st.toggle('Notes', value=True, disabled=not st.session_state['uploaded'])
    highlight_formulas = st.toggle('Politicas', value=True, disabled=not st.session_state['uploaded'])
    highlight_figures = st.toggle('Figutas - Tablas', value=True, disabled=not st.session_state['uploaded'])
    highlight_callout = st.toggle('Refe', value=True, disabled=not st.session_state['uploaded'])
    highlight_citations = st.toggle('Citas', value=True, disabled=not st.session_state['uploaded'])
    st.header("Anotaciones")
    annotation_thickness = st.slider(label="Annotation boxes border thickness", min_value=1, max_value=6, value=1)
    pages_vertical_spacing = st.slider(label="Pages vertical spacing", min_value=0, max_value=10, value=2)
    st.header("Altura y Ancho")
    resolution_boost = st.slider(label="Resolution boost", min_value=1, max_value=10, value=1)
    width = st.slider(label="PDF width", min_value=100, max_value=1000, value=700)
    height = st.slider(label="PDF height", min_value=-1, max_value=10000, value=-1)
    st.header("Selección de Pagina")
    placeholder = st.empty()
    if not st.session_state['pages']:
        st.session_state['page_selection'] = placeholder.multiselect(
            "Select pages to display",
            options=[],
            default=[],
            help="The page number considered is the PDF number and not the document page number.",
            disabled=not st.session_state['pages'],
            key=1
        )
    st.header("Soporte y Ayuda")
    st.markdown("""Cargue de Alojammiento con Agentes AI - Gemini Google""")
    if st.session_state['git_rev'] != "unknown":
        st.markdown("**Revision number**: [" + st.session_state[
            'git_rev'] + "](http://digitalmagia.com" + st.session_state['git_rev'] + ")")

# Función para obtener el hash de un archivo
def get_file_hash(fname):
    hash_md5 = blake2b()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

if uploaded_file:
    if not st.session_state['binary']:
        with col1:
            st.spinner('Reading file, calling ...')
            binary = uploaded_file.getvalue()
            tmp_file = NamedTemporaryFile()
            tmp_file.write(bytearray(binary))
            st.session_state['binary'] = binary
            st.session_state['annotations'] = annotations if not st.session_state['annotations'] else st.session_state['annotations']
            st.session_state['pages'] = pages if not st.session_state['pages'] else st.session_state['pages']

    if st.session_state['pages']:
        st.session_state['page_selection'] = placeholder.multiselect(
            "Select pages to display",
            options=list(range(1, 1)),
            default=[],
            help="The page number considered is the PDF number and not the document page number.",
            disabled=not 1,
            key=2
        )

    # Renderizado del documento PDF
    with tab1:
        with st.spinner("Rendering PDF document"):
            annotations = st.session_state['annotations']
            if not highlight_sentences:
                annotations = list(filter(lambda a: a['type'] != 's', annotations))
            if not highlight_paragraphs:
                annotations = list(filter(lambda a: a['type'] != 'p', annotations))
            if not highlight_title:
                annotations = list(filter(lambda a: a['type'] != 'title', annotations))
            if not highlight_head:
                annotations = list(filter(lambda a: a['type'] != 'head', annotations))
            if not highlight_citations:
                annotations = list(filter(lambda a: a['type'] != 'biblStruct', annotations))
            if not highlight_notes:
                annotations = list(filter(lambda a: a['type'] != 'note', annotations))
            if not highlight_callout:
                annotations = list(filter(lambda a: a['type'] != 'ref', annotations))
            if not highlight_formulas:
                annotations = list(filter(lambda a: a['type'] != 'formula', annotations))
            if not highlight_person_names:
                annotations = list(filter(lambda a: a['type'] != 'persName', annotations))
            if not highlight_figures:
                annotations = list(filter(lambda a: a['type'] != 'figure', annotations))
            if not highlight_affiliations:
                annotations = list(filter(lambda a: a['type'] != 'affiliation', annotations))
            if height > -1:
                pdf_viewer(
                    input=st.session_state['binary'],
                    width=width,
                    height=height,
                    annotations=annotations,
                    pages_vertical_spacing=pages_vertical_spacing,
                    annotation_outline_size=annotation_thickness,
                    pages_to_render=st.session_state['page_selection'],
                    render_text=enable_text,
                    resolution_boost=resolution_boost
                )
            else:
                pdf_viewer(
                    input=st.session_state['binary'],
                    width=width,
                    annotations=annotations,
                    pages_vertical_spacing=pages_vertical_spacing,
                    annotation_outline_size=annotation_thickness,
                    pages_to_render=st.session_state['page_selection'],
                    render_text=enable_text,
                    resolution_boost=resolution_boost
                )

    # Render siempre los botones, pero habilita/deshabilita según estado
    with tab2:
        tab2.subheader("AGENT IA - Utiliza el agente para Interpretar tu PDF")
        tab2.write("Este agente utiliza inteligencia artificial para interpretar y analizar el contenido de tu PDF.")
        tab2.image("img/doc_extradata.png", caption="IA en acción", output_format="auto")
        
        # Dividir en columnas para mostrar el estado actual
        col_estado, col_fase = tab2.columns([3, 1])
        with col_fase:
            if st.session_state['fase_proceso'] != 'inicial':
                tab2.success(f"Fase: {st.session_state['fase_proceso'].title()}")
        
        # Primer botón - Siempre visible
        btn_agente = tab2.button("Iniciar Interpretación", 
                                 disabled=not st.session_state['api_key'] or not uploaded_file)
        
        if btn_agente:
            if not st.session_state['api_key']:
                tab2.error("Por favor, configure la API key en la barra lateral antes de continuar.")
            else:
                tab2.write("Interpretación iniciada...")
                # Código de procesamiento...
                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    file_path = tmp_file.name
                response_llm = crete_prompt(file_path, st.session_state['selected_model'])
                json_data = text_to_json(response_llm.text)
                
                # Guardar datos en el state para uso posterior
                st.session_state['datos_interpretacion'] = json_data
                st.session_state['fase_proceso'] = 'interpretado'
                # Force rerun para actualizar la interfaz
                st.rerun()
        
        # Mostrar formulario si ya se interpretó
        if st.session_state['fase_proceso'] == 'interpretado' or st.session_state['fase_proceso'] == 'agendado':
            # Mostrar el formulario de validación
            data_to_send = tabular_validation_form(st.session_state['datos_interpretacion'], tab2)
            st.session_state['data_to_send'] = data_to_send
        
        # Segundo botón - Visible solo después de interpretación
        btn_agenda = tab2.button("Agendar Conciliación 📧", 
                                 disabled=st.session_state['fase_proceso'] == 'inicial')

        if btn_agenda and st.session_state['fase_proceso'] == 'interpretado':
            print("Enviando datos al webhook...")
            response = send_webhook("https://magia.app.n8n.cloud/webhook-test/a4a9b9f0-5ed7-4c80-bebe-09a9d955ae2f", 
                                    st.session_state['data_to_send'])
            if response and response.status_code == 200:
                tab2.success("✅ Cita de conciliación agendada correctamente.")
                st.session_state['fase_proceso'] = 'agendado'
            else:
                tab2.error("❌ Error al agendar la cita de conciliación.")
        
        # Botón para reiniciar el proceso si ya se agendó
        if st.session_state['fase_proceso'] == 'agendado':
            if tab2.button("Iniciar nuevo agendamiento"):
                st.session_state['fase_proceso'] = 'inicial'
                st.session_state['datos_interpretacion'] = None
                st.session_state['data_to_send'] = None
                st.rerun()




