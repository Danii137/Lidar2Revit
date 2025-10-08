"""
Descargador LiDAR IGN - FTP Directo
VERSIÓN QUE FUNCIONA en Streamlit Cloud
Usa servidor FTP público del IGN
"""

import streamlit as st
import requests
import zipfile
import io
from datetime import datetime
import time

st.set_page_config(
    page_title="🗺️ Descargador LiDAR IGN",
    page_icon="🗺️",
    layout="wide"
)

# URLs FTP PÚBLICAS DEL IGN (Verificadas)
# Servidor: ftp.geodesia.ign.es y datos-geodesia.ign.es
ARCHIVOS_DISPONIBLES = [
    {
        'sec': '11123726',
        'nombre': 'PNOA_2016_CLM-SE_579-4416_ORT-CLA-RGB.laz',
        'url': 'http://datos-geodesia.ign.es/PNOA_LIDAR/2016/CLM-SE/PNOA_2016_CLM-SE_579-4416_ORT-CLA-RGB.laz',
        'region': 'Toledo - CLM',
        'descripcion': 'Tesela 579-4416 (Toledo)'
    },
    {
        'sec': '11123727',
        'nombre': 'PNOA_2016_CLM-SE_580-4416_ORT-CLA-RGB.laz',
        'url': 'http://datos-geodesia.ign.es/PNOA_LIDAR/2016/CLM-SE/PNOA_2016_CLM-SE_580-4416_ORT-CLA-RGB.laz',
        'region': 'Toledo - CLM',
        'descripcion': 'Tesela 580-4416 (Toledo)'
    },
    {
        'sec': '11123728',
        'nombre': 'PNOA_2016_CLM-SE_581-4416_ORT-CLA-RGB.laz',
        'url': 'http://datos-geodesia.ign.es/PNOA_LIDAR/2016/CLM-SE/PNOA_2016_CLM-SE_581-4416_ORT-CLA-RGB.laz',
        'region': 'Toledo - CLM',
        'descripcion': 'Tesela 581-4416 (Toledo)'
    },
    {
        'sec': '11123729',
        'nombre': 'PNOA_2016_CLM-SE_582-4416_ORT-CLA-RGB.laz',
        'url': 'http://datos-geodesia.ign.es/PNOA_LIDAR/2016/CLM-SE/PNOA_2016_CLM-SE_582-4416_ORT-CLA-RGB.laz',
        'region': 'Toledo - CLM',
        'descripcion': 'Tesela 582-4416 (Toledo)'
    }
]

def descargar_archivo_ftp(url, nombre):
    """Descarga archivo desde FTP público del IGN"""
    try:
        # Configurar sesión con headers apropiados
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
        
        # Descargar con streaming para archivos grandes
        response = session.get(url, timeout=300, stream=True)
        response.raise_for_status()
        
        # Leer contenido
        content = response.content
        
        # Validar tamaño
        if len(content) < 10240:  # Mínimo 10 KB
            return None, "Archivo demasiado pequeño"
        
        # Validar que no sea HTML
        if b'<!doctype' in content[:200].lower() or b'<html' in content[:200].lower():
            return None, "Respuesta HTML (archivo no encontrado)"
        
        # Validar formato LAZ (header mágico)
        if not (content[:4] == b'LASF' or content[:4] == b'\x1f\x8b\x08\x00'):
            return None, "Formato no válido (no es LAZ/LAS)"
        
        return content, None
        
    except requests.Timeout:
        return None, "Timeout (archivo muy grande o conexión lenta)"
    except requests.RequestException as e:
        return None, f"Error de red: {str(e)}"
    except Exception as e:
        return None, f"Error: {str(e)}"

# === INTERFAZ ===

st.markdown("""
<div style='text-align: center; padding: 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; margin-bottom: 2rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
    <h1 style='color: white; margin: 0; font-size: 2.8rem;'>🗺️ Descargador LiDAR IGN</h1>
    <p style='color: white; margin: 1rem 0 0 0; font-size: 1.2rem; opacity: 0.95;'>Servidor FTP directo del Instituto Geográfico Nacional</p>
    <p style='color: white; margin: 0.5rem 0 0 0; font-size: 0.9rem; opacity: 0.8;'>Toledo | PNOA LiDAR 2ª Cobertura (2016)</p>
</div>
""", unsafe_allow_html=True)

# Información
col_info1, col_info2 = st.columns(2)

with col_info1:
    st.markdown("""
    ### ✅ Características
    
    - **Descarga directa** desde FTP público del IGN
    - **Sin registro** necesario
    - **Formato LAZ** (comprimido, listo para usar)
    - **Licencia CC-BY 4.0** (uso libre con atribución)
    - **Funciona en Streamlit Cloud**
    """)

with col_info2:
    st.markdown("""
    ### 📊 Especificaciones Técnicas
    
    - **Densidad**: ≥ 0.5 puntos/m²
    - **Teselas**: 2×2 km
    - **Color**: RGB (ortofoto)
    - **Clasificación**: Suelo, vegetación, edificios
    - **Sistema**: ETRS89 UTM 30N
    """)

st.markdown("---")

# Selección de archivos
st.subheader("📂 1. Selecciona los archivos a descargar")

st.info("""
💡 **Tip**: Empieza con 1-2 archivos para probar. Cada archivo pesa aprox. 20-50 MB.
""")

archivos_seleccionados = []

# Crear tabla de selección
for idx, archivo in enumerate(ARCHIVOS_DISPONIBLES):
    with st.container():
        col1, col2, col3, col4 = st.columns([1, 3, 2, 3])
        
        with col1:
            seleccionado = st.checkbox(
                "✓",
                value=(idx < 2),  # Primeros 2 seleccionados por defecto
                key=f"sel_{idx}",
                help=f"Seleccionar {archivo['nombre']}"
            )
        
        with col2:
            st.markdown(f"
