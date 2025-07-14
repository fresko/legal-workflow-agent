import streamlit as st
import boto3
from datetime import datetime
import time
import os
import uuid
import random

# Configuración de página
st.set_page_config(
    page_title="Carga de Documentos - CNCVIRTUAL5@",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="collapsed"
)



# Estilos CSS personalizados
st.markdown("""
<style>
    /* Contenedor principal */
    .upload-container {
        max-width: 700px;
        margin: 0 auto;
        padding: 2rem 1rem;
        transition: all 0.3s ease;
    }
    
    /* Títulos y descripción */
    h1 {
        text-align: center;
        font-size: 2.2rem;
        margin-bottom: 0.5rem;
        color: #2e2e2e;
    }
    
    .description {
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
        font-size: 1.1rem;
    }
    
    /* Estilizar zona de arrastre */
    [data-testid="stFileUploader"] {
        width: 100%;
    }
    
    [data-testid="stFileUploader"] > label {
        display: none;
    }
    
    [data-testid="stFileUploader"] > section {
        border: 2px dashed #39FF14 !important;
        border-radius: 10px !important;
        padding: 2rem !important;
        background-color: rgba(57, 255, 20, 0.05) !important;
        transition: all 0.3s ease;
    }
    
    [data-testid="stFileUploader"] > section:hover {
        transform: scale(1.02);
        border-color: #39FF14 !important;
        background-color: rgba(57, 255, 20, 0.1) !important;
    }
    
    /* Estilo para botones */
    div.stButton > button {
        width: 100%;
        background-color: #6e6e6e;
        color: white;
        border: none;
        padding: 0.75rem;
        font-size: 1.1rem;
        transition: all 0.3s ease;
    }
    
    div.stButton > button:hover,
    div.stButton > button:active {
        background-color: #39FF14;
        color: #333;
    }
    
    /* Animación de deslizamiento */
    @keyframes slideUp {
        from { transform: translateY(0); opacity: 1; }
        to { transform: translateY(-30px); opacity: 0.9; }
    }
    
    .slide-up {
        animation: slideUp 0.5s forwards;
    }
    
    /* Animación de aparición */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .fade-in {
        animation: fadeIn 0.5s forwards;
    }
    
    /* Estilos para mensajes de resultado */
    .success-message {
        background-color: rgba(57, 255, 20, 0.2);
        border: 1px solid #39FF14;
        border-radius: 8px;
        padding: 1.5rem;
        margin-top: 2rem;
        margin-bottom: 1rem;  /* Added margin at bottom */
        text-align: center;
        width: 100%;  /* Ensure it takes full width of container */
        box-sizing: border-box;  /* Include padding in width calculation */
    }
    
    .error-message {
        background-color: rgba(255, 87, 87, 0.2);
        border: 1px solid #ff5757;
        border-radius: 8px;
        padding: 1.5rem;
        margin-top: 2rem;
        text-align: center;
    }
    
    /* Ocultar elementos de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Ocultar botón de deploy */
    .stDeployButton {display: none !important;}
    [data-testid="stToolbar"] {display: none !important;}
    
    /* Estilos para el chat en la barra lateral */
    [data-testid="stChatMessageContent"] {
        background-color: rgba(57, 255, 20, 0.05);
        border: 1px solid rgba(57, 255, 20, 0.3);
        border-radius: 10px;
        padding: 0.75rem !important;
    }
    
    /* Estilo para mensajes del asistente */
    [data-testid="stChatMessageContent"][data-testid*="assistant"] {
        background-color: rgba(57, 255, 20, 0.1);
        border-color: rgba(57, 255, 20, 0.4);
    }
    
    /* Estilo para mensajes del usuario */
    [data-testid="stChatMessageContent"][data-testid*="user"] {
        background-color: rgba(110, 110, 110, 0.1);
        border-color: rgba(110, 110, 110, 0.3);
    }
    
    /* Estilo para el avatar del usuario */
    [data-testid="stChatMessageAvatar"][data-testid*="user"] div {
        background-color: #6e6e6e !important;
    }
    
    /* Estilo para el avatar del asistente */
    [data-testid="stChatMessageAvatar"][data-testid*="assistant"] div {
        background-color: #39FF14 !important;
        color: #333333 !important;
    }
    
    /* Estilo para el input del chat */
    .stChatInputContainer textarea {
        border-radius: 10px !important;
        border: 1px solid rgba(57, 255, 20, 0.3) !important;
        padding: 10px !important;
    }
    
    .stChatInputContainer textarea:focus {
        border-color: #39FF14 !important;
        box-shadow: 0 0 0 1px rgba(57, 255, 20, 0.2) !important;
    }
    
    /* Estilo para el botón de enviar */
    .stChatInputContainer button {
        border-radius: 50% !important;
        background-color: #6e6e6e !important;
        transition: all 0.3s ease !important;
    }
    
    .stChatInputContainer button:hover {
        background-color: #39FF14 !important;
        color: #333333 !important;
    }
    
    /* Ajustar el contenedor del chat */
    [data-testid="stChatMessageContainer"] {
        padding: 0.5rem !important;
    }
    
    /* Eliminar el borde del contenedor del chat */
    [data-testid="stChatContainer"] {
        border: none !important;
    }
    
    /* Ajustar tamaño de texto en los mensajes */
    [data-testid="stChatMessageContent"] p {
        font-size: 0.9rem !important;
        margin: 0 !important;
    }
    
    /* Estilo para el placeholder del input */
    .stChatInputContainer textarea::placeholder {
        color: #666 !important;
        font-style: italic !important;
    }
    
    /* Estilo para el historial de chat */
    [data-testid="stChatMessageContainer"] > div {
        margin-bottom: 0.75rem !important;
    }
    
    /* Diseño responsive para el chat */
    @media (max-width: 768px) {
        [data-testid="stChatMessageContent"] {
            padding: 0.5rem !important;
        }
        
        [data-testid="stChatMessageContent"] p {
            font-size: 0.8rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# Inicializar variables de estado
if 'upload_complete' not in st.session_state:
    st.session_state['upload_complete'] = False
    
if 'upload_status' not in st.session_state:
    st.session_state['upload_status'] = None
    
if 'uploaded_files' not in st.session_state:
    st.session_state['uploaded_files'] = []
    
if 'auto_reset' not in st.session_state:
    st.session_state['auto_reset'] = False
    
if 'reset_time' not in st.session_state:
    st.session_state['reset_time'] = None
    
# Añadir un key único para el uploader que cambia en cada reseteo
if 'uploader_key' not in st.session_state:
    st.session_state['uploader_key'] = str(uuid.uuid4())

# Función para subir archivos a S3
def upload_to_s3(file, bucket_name):
    try:
        # Configurar cliente AWS S3 (asumiendo credenciales configuradas)
        s3_client = boto3.client('s3')
        
        # Generar ruta en S3
        current_date = datetime.now().strftime("%Y-%m-%d")
        s3_path = f"cncvirtual5/{current_date}/{file.name}"
        print(f"Subiendo archivo a S3: {s3_path}")
        # Subir archivo
        s3_client.upload_fileobj(file, bucket_name, s3_path)
        
        # Generar URL
        url = f"https://{bucket_name}.s3.amazonaws.com/{s3_path}"
        
        return {
            "success": True,
            "name": file.name,
            "url": url,
            "path": s3_path
        }
    except Exception as e:
        return {
            "success": False,
            "name": file.name,
            "error": str(e)
        }

# Función para resetear completamente el estado
def reset_state():
    st.session_state['upload_complete'] = False
    st.session_state['upload_status'] = None
    st.session_state['uploaded_files'] = []
    st.session_state['auto_reset'] = False
    st.session_state['reset_time'] = None
    # Cambiar la clave del uploader para forzar su recreación
    st.session_state['uploader_key'] = str(uuid.uuid4())
    st.rerun()

# Interfaz de usuario
def main():
    # Auto-reset después de mostrar mensaje (2.5 segundos)
    if st.session_state['auto_reset'] and st.session_state['reset_time'] is not None:
        if datetime.now().timestamp() - st.session_state['reset_time'] > 2.5:
            reset_state()
    
    # Contenedor principal
    container_class = "upload-container" if not st.session_state['upload_complete'] else "upload-container slide-up"
    st.markdown(f'<div class="{container_class}">', unsafe_allow_html=True)
    st.markdown("<h1>Cargar Documentos</h1>", unsafe_allow_html=True)
    st.markdown("<p class='description'>Arrastra tus archivos a la zona indicada para subirlos a la nube</p>", unsafe_allow_html=True)
    
    # Área de carga de archivos con key dinámica para forzar su recreación
    uploaded_files = st.file_uploader(
        "Arrastra tus documentos aquí",
        accept_multiple_files=True,
        type=["pdf", "doc", "docx", "jpg", "jpeg", "png"],
        label_visibility="collapsed",
        key=st.session_state['uploader_key']  # Usar key dinámica
    )
    
    # Botón para iniciar la carga
    if uploaded_files:
        button_text = f"Cargar {len(uploaded_files)} documento{'s' if len(uploaded_files) > 1 else ''}"
        
        if st.button(button_text, icon=":material/send:", use_container_width=True):
            process_uploaded_files(uploaded_files)
    else:
        st.button("Seleccionar documentos", use_container_width=True, disabled=True)
    
    # Cerramos el contenedor principal
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Contenedor para mensajes (más pequeño que antes)
    if st.session_state['upload_complete']:
        if st.session_state['upload_status'] == 'success':
            files_str = ", ".join([f_info['name'] for f_info in st.session_state['uploaded_files'] if f_info['success']])
            success_html = f"""
            <div style="background-color: rgba(57, 255, 20, 0.2); border: 1px solid #39FF14; border-radius: 8px; padding: 0.75rem; margin-top: 1.5rem; text-align: center; max-width: 500px; margin-left: auto; margin-right: auto;">
                <h4 style="margin-top: 0; margin-bottom: 0.5rem;">Carga Exitosa</h4>
                <p style="margin: 0.25rem 0; font-size: 0.85rem;">Los archivos se han subido correctamente al servidor.</p>
                <p style="margin: 0.25rem 0; font-size: 0.85rem;"><strong>Archivos:</strong> {files_str}</p>
            </div>
            """
            st.markdown(success_html, unsafe_allow_html=True)
        else:
            error_details = ""
            for file_info in st.session_state['uploaded_files']:
                if not file_info['success']:
                    error_details += f"<p style='margin: 0.2rem 0; font-size: 0.8rem;'><strong>{file_info['name']}:</strong> {file_info['error']}</p>"
            
            error_html = f"""
            <div style="background-color: rgba(255, 87, 87, 0.2); border: 1px solid #ff5757; border-radius: 8px; padding: 0.75rem; margin-top: 1.5rem; text-align: center; max-width: 500px; margin-left: auto; margin-right: auto;">
                <h4 style="margin-top: 0; margin-bottom: 0.5rem;">Error en la Carga</h4>
                <p style="margin: 0.25rem 0; font-size: 0.85rem;">Se produjo un error al subir algunos archivos.</p>
                {error_details}
            </div>
            """
            st.markdown(error_html, unsafe_allow_html=True)
        
        # Establecer tiempo para autoreset si no está configurado
        if not st.session_state['auto_reset']:
            st.session_state['auto_reset'] = True
            st.session_state['reset_time'] = datetime.now().timestamp()
    
# Función para procesar archivos subidos
def process_uploaded_files(uploaded_files):
    # Nombre del bucket S3
    bucket_name = "citas-conciliacion-pruebas" 
    
    # Procesar cada archivo
    progress = st.progress(0)
    results = []
    
    for i, file in enumerate(uploaded_files):
        # Actualizar progreso
        progress_value = (i + 1) / len(uploaded_files)
        progress.progress(progress_value)
        
        # Subir a S3
        result = upload_to_s3(file, bucket_name)
        results.append(result)
        
        # Pausa breve para mostrar el progreso
        time.sleep(0.10)
    
    # Guardar resultados y cambiar estado
    st.session_state['uploaded_files'] = results
    st.session_state['upload_complete'] = True
    
    # Determinar estado general
    has_error = any(not r['success'] for r in results)
    st.session_state['upload_status'] = 'error' if has_error else 'success'
    
    # Efecto de animación y recarga
    time.sleep(0.5)  # Brief pause for visual effect
    st.rerun()

def chat_legal():
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = [{
            "role": "assistant", 
            "content": "👋 Hola, soy tu Asistente Legal. Puedo ayudarte con:\n\n• Audiencias de conciliación\n• Trámites legales\n• Consultas jurídicas\n\n¿En qué puedo asistirte hoy?"
        }]

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    if prompt := st.chat_input("¿Cómo puedo ayudarte hoy?"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)

        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            # Lista de respuestas más relacionadas con temas legales
            assistant_responses = [
                "Comprendo tu consulta. Para asesorarte mejor, necesitaría algunos detalles adicionales sobre tu caso específico.",
                "Esta es una situación común en procesos de conciliación. Te recomendaría considerar los siguientes aspectos legales...",
                "Desde el punto de vista jurídico, existen varias alternativas que podrías explorar en este caso.",
                "Para audiencias de tránsito como la que mencionas, la normativa establece ciertos procedimientos específicos que debemos seguir.",
                "En el ámbito legal, este tipo de situaciones están reguladas por el artículo correspondiente que establece los lineamientos a seguir."
            ]
            
            assistant_response = random.choice(assistant_responses)
            
            # Simular respuesta progresiva
            for chunk in assistant_response.split():
                full_response += chunk + " "
                time.sleep(0.04)  # Reducido el tiempo para mejor experiencia
                message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
        
        # Añadir respuesta al historial
        st.session_state.messages.append({"role": "assistant", "content": full_response})

# Configuración de la barra lateral
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; margin-bottom: 1rem;">
        <div style="background-color: #333333; width: 80px; height: 80px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto; border: 2px solid #39FF14;">
            <svg xmlns="http://www.w3.org/2000/svg" height="50" viewBox="0 -960 960 960" width="50" fill="#39FF14">
                <path d="M320-120v-80h80v-80H160v-280q0-83 50-147.5T340-792v-48h40v48q54 14 97 55t43 97h-40q0-58-41-99t-99-41q-58 0-99 41t-41 99v240h400v80H480v80h80v80H320Zm360-520q-17 0-28.5-11.5T640-680q0-17 11.5-28.5T680-720q17 0 28.5 11.5T720-680q0 17-11.5 28.5T680-640Zm80-80q-17 0-28.5-11.5T720-760q0-17 11.5-28.5T760-800q17 0 28.5 11.5T800-760q0 17-11.5 28.5T760-720Z"/>
            </svg>
        </div>
        <h1 style="margin-top: 1rem;">Asistente Legal</h1>
    </div>
    """, unsafe_allow_html=True)    
    st.markdown("""
    <div style="margin-top: 1rem;">
        <p class='description' style='text-align: center;'>Tu apoyo inteligente en audiencias   
            Audiencias de Conciliación, 
            Audiencias de Tránsito,   
            Audiencias Legales.</p>                                
        <center><h3 style="border-bottom: 1px solid rgba(57, 255, 20, 0.3); padding-bottom: 5px;">.</h3></center>
       
    </div>
    """, unsafe_allow_html=True)
    chat_legal()

   

# Ejecutar la aplicación
if __name__ == "__main__":
    main()