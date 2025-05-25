import streamlit as st
import boto3
from datetime import datetime
import time
import os

# Configuración de página
st.set_page_config(
    page_title="Carga de Documentos",
    page_icon="📄",
    layout="centered"
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
        to { transform: translateY(-30px); opacity: 0.7; }
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
        text-align: center;
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
</style>
""", unsafe_allow_html=True)

# Inicializar variables de estado
if 'upload_complete' not in st.session_state:
    st.session_state['upload_complete'] = False
    
if 'upload_status' not in st.session_state:
    st.session_state['upload_status'] = None
    
if 'uploaded_files' not in st.session_state:
    st.session_state['uploaded_files'] = []

# Función para subir archivos a S3
def upload_to_s3(file, bucket_name):
    try:
        # Configurar cliente AWS S3 (asumiendo credenciales configuradas)
        s3_client = boto3.client('s3')
        
        # Generar ruta en S3
        current_date = datetime.now().strftime("%Y-%m-%d")
        s3_path = f"uploads/{current_date}/{file.name}"
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

# Interfaz de usuario
def main():
    if not st.session_state['upload_complete']:
        # Mostrar el formulario de carga completo
        st.markdown('<div class="upload-container">', unsafe_allow_html=True)
        st.markdown("<h1>Cargar Documentos</h1>", unsafe_allow_html=True)
        st.markdown("<p class='description'>Arrastra tus archivos a la zona indicada para subirlos a la nube</p>", unsafe_allow_html=True)
        
        # Área de carga de archivos
        uploaded_files = st.file_uploader(
            "Arrastra tus documentos aquí",
            accept_multiple_files=True,
            type=["pdf", "doc", "docx", "jpg", "jpeg", "png"],
            label_visibility="collapsed"
        )
        
        # Botón para iniciar la carga
        if uploaded_files:
            button_text = f"Cargar {len(uploaded_files)} documento{'s' if len(uploaded_files) > 1 else ''}"
            if st.button(button_text, use_container_width=True):
                # Nombre del bucket S3
                bucket_name = "citas-conciliacion"  # Reemplaza con tu bucket
                
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
        else:
            st.button("Seleccionar documentos", use_container_width=True, disabled=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    else:
        # Mostrar versión minimizada después de cargar
        st.markdown('<div class="upload-container">', unsafe_allow_html=True)
        st.markdown("<h1>Cargar Documentos</h1>", unsafe_allow_html=True)
        st.markdown("<p class='description'>Arrastra tus archivos a la zona indicada para subirlos a la nube</p>", unsafe_allow_html=True)
        
        # Formulario minimizado
        with st.expander("Cargar más documentos", expanded=False):
            more_files = st.file_uploader(
                "Arrastra más documentos aquí",
                accept_multiple_files=True,
                type=["pdf", "doc", "docx", "jpg", "jpeg", "png"],
                key="more_files"
            )
            
            if more_files:
                if st.button("Subir archivos adicionales", use_container_width=True):
                    # Lógica de carga similar...
                    pass
        
        # Mostrar resultado de la carga
        if st.session_state['upload_status'] == 'success':
            st.markdown('<div class="success-message fade-in">', unsafe_allow_html=True)
            st.markdown("### ✅ Carga Exitosa")
            st.markdown("Los archivos se han subido correctamente al servidor.")
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Mostrar archivos subidos
            st.subheader("Archivos cargados:")
            for file_info in st.session_state['uploaded_files']:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"📄 {file_info['name']}")
                with col2:
                    if file_info['success']:
                        st.markdown(f"[Ver archivo]({file_info['url']})")
        
        else:
            st.markdown('<div class="error-message fade-in">', unsafe_allow_html=True)
            st.markdown("### ❌ Error en la Carga")
            st.markdown("Se produjo un error al subir algunos archivos.")
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Mostrar errores
            st.subheader("Detalles del error:")
            for file_info in st.session_state['uploaded_files']:
                if not file_info['success']:
                    st.error(f"{file_info['name']}: {file_info['error']}")
        
        # Botón para reiniciar
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("Cargar nuevos documentos", use_container_width=True):
                st.session_state['upload_complete'] = False
                st.session_state['upload_status'] = None
                st.session_state['uploaded_files'] = []
                st.experimental_rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

# Ejecutar la aplicación
if __name__ == "__main__":
    main()