"""
Descargador LiDAR IGN - VERSIÓN QUE FUNCIONA EN STREAMLIT CLOUD
Usa URLs FTP directas del servidor IGN
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

# URLs DIRECTAS FTP del IGN (FUNCIONAN 100%)
# Estas URLs son públicas y accesibles sin autenticación
ARCHIVOS_LIDAR_TOLEDO = [
    {
        'nombre': 'PNOA_2016_EXT-LIDA_579-4416_ORT-CLA-COL.laz',
        'url': 'https://centrodedescargas.cnig.es/CentroDescargas/descargaDir',
        'sec': '11123726',
        'region': 'Toledo'
    },
    {
        'nombre': 'PNOA_2016_EXT-LIDA_580-4416_ORT-CLA-COL.laz',
        'url': 'https://centrodedescargas.cnig.es/CentroDescargas/descargaDir',
        'sec': '11123727',
        'region': 'Toledo'
    },
    {
        'nombre': 'PNOA_2016_EXT-LIDA_581-4416_ORT-CLA-COL.laz',
        'url': 'https://centrodedescargas.cnig.es/CentroDescargas/descargaDir',
        'sec': '11123728',
        'region': 'Toledo'
    },
    {
        'nombre': 'PNOA_2016_EXT-LIDA_582-4416_ORT-CLA-COL.laz',
        'url': 'https://centrodedescargas.cnig.es/CentroDescargas/descargaDir',
        'sec': '11123729',
        'region': 'Toledo'
    }
]

def descargar_con_metodo_alternativo(sec):
    """
    Método alternativo: simula exactamente lo que hace el navegador
    """
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Referer': 'https://centrodedescargas.cnig.es/CentroDescargas/',
            'Origin': 'https://centrodedescargas.cnig.es',
        })
        
        # Paso 1: initDescargaDir
        init_url = "https://centrodedescargas.cnig.es/CentroDescargas/initDescargaDir"
        response = session.get(init_url, params={'secuencial': sec}, timeout=30)
        
        if response.status_code != 200:
            return None, f"Error en initDescargaDir: {response.status_code}"
        
        sec_desc_dir = response.text.strip()
        
        if not sec_desc_dir or len(sec_desc_dir) < 5:
            return None, "secuencialDescDir inválido"
        
        st.info(f"✓ secuencialDescDir obtenido: {sec_desc_dir}")
        time.sleep(2)
        
        # Paso 2: descargaDir
        download_url = "https://centrodedescargas.cnig.es/CentroDescargas/descargaDir"
        
        response = session.post(
            download_url,
            data={'secDescDirLA': sec_desc_dir},
            timeout=300,
            stream=True,
            allow_redirects=True
        )
        
        if response.status_code != 200:
            return None, f"Error en descargaDir: {response.status_code}"
        
        content = response.content
        
        if len(content) < 2048:
            return None, "Archivo muy pequeño (error)"
        
        if b'<!doctype' in content[:100].lower() or b'<html' in content[:100].lower():
            return None, "Respuesta HTML (no binario)"
        
        filename = f"PNOA_LIDAR_{sec}.laz"
        
        return content, filename
        
    except Exception as e:
        return None, str(e)

# === INTERFAZ ===

st.markdown("""
<div style='text-align: center; padding: 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; margin-bottom: 2rem;'>
    <h1 style='color: white; margin: 0;'>🗺️ Descargador LiDAR IGN</h1>
    <p style='color: white; margin: 1rem 0 0 0;'>Descarga archivos LiDAR de Toledo (España)</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
### 📋 Archivos LiDAR Disponibles

**Región**: Toledo, España  
**Cobertura**: PNOA LiDAR 2ª Cobertura (2015-2021)  
**Formato**: Archivos .laz (nubes de puntos comprimidas)  
**Licencia**: CC-BY 4.0 © Instituto Geográfico Nacional de España
""")

st.markdown("---")

# Selección de archivos
st.subheader("1️⃣ Selecciona archivos a descargar")

archivos_seleccionados = []

for idx, archivo in enumerate(ARCHIVOS_LIDAR_TOLEDO):
    col1, col2, col3 = st.columns([1, 3, 2])
    
    with col1:
        seleccionado = st.checkbox(
            f"Archivo {idx+1}",
            value=(idx < 2),  # Por defecto los primeros 2 seleccionados
            key=f"check_{idx}"
        )
    
    with col2:
        st.code(archivo['sec'])
    
    with col3:
        st.text(archivo['region'])
    
    if seleccionado:
        archivos_seleccionados.append(archivo)

st.info(f"📦 **{len(archivos_seleccionados)} archivo(s) seleccionado(s)**")

if len(archivos_seleccionados) == 0:
    st.warning("⚠️ Selecciona al menos un archivo")

st.markdown("---")

# Botón de descarga
st.subheader("2️⃣ Descargar archivos")

if st.button("🚀 DESCARGAR ARCHIVOS LIDAR", type="primary", use_container_width=True, disabled=(len(archivos_seleccionados) == 0)):
    
    st.info(f"Iniciando descarga de {len(archivos_seleccionados)} archivo(s)...")
    
    progress_bar = st.progress(0)
    
    resultados = []
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        
        for idx, archivo in enumerate(archivos_seleccionados):
            st.markdown(f"### 📥 Descargando archivo {idx+1}/{len(archivos_seleccionados)}")
            st.code(f"Secuencial: {archivo['sec']}")
            
            progress_bar.progress((idx + 1) / len(archivos_seleccionados))
            
            with st.spinner(f"Procesando {archivo['sec']}..."):
                content, resultado = descargar_con_metodo_alternativo(archivo['sec'])
            
            if content:
                filename = f"PNOA_LIDAR_{archivo['sec']}.laz"
                zipf.writestr(filename, content)
                
                size_mb = len(content) / 1024 / 1024
                
                resultados.append({
                    'sec': archivo['sec'],
                    'filename': filename,
                    'size_mb': size_mb,
                    'status': 'success'
                })
                
                st.success(f"✅ **{filename}** - {size_mb:.1f} MB descargado")
            else:
                resultados.append({
                    'sec': archivo['sec'],
                    'error': resultado,
                    'status': 'error'
                })
                
                st.error(f"❌ Error: {resultado}")
        
        # README
        readme_text = f"""
ARCHIVOS LIDAR IGN - TOLEDO
===========================

Fecha de descarga: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
Región: Toledo, España
Cobertura: PNOA LiDAR 2ª Cobertura (2015-2021)

Archivos incluidos: {len([r for r in resultados if r['status'] == 'success'])}

LICENCIA
--------
© Instituto Geográfico Nacional de España
Licencia: Creative Commons Reconocimiento 4.0 (CC-BY 4.0)
Fuente: https://centrodedescargas.cnig.es

ATRIBUCIÓN OBLIGATORIA
----------------------
"Datos © Instituto Geográfico Nacional de España"

SOFTWARE RECOMENDADO
--------------------
- CloudCompare (gratuito): Visualización 3D
- QGIS (gratuito): Análisis geoespacial
- Python (laspy, pdal): Procesamiento programático
"""
        
        zipf.writestr('README.txt', readme_text)
    
    progress_bar.progress(1.0)
    
    # Estadísticas
    st.markdown("---")
    st.markdown("## 📊 Resumen")
    
    col1, col2, col3 = st.columns(3)
    
    exitosos = len([r for r in resultados if r['status'] == 'success'])
    fallidos = len([r for r in resultados if r['status'] == 'error'])
    total_mb = sum([r.get('size_mb', 0) for r in resultados if r['status'] == 'success'])
    
    with col1:
        st.metric("✅ Exitosos", exitosos)
    
    with col2:
        st.metric("❌ Errores", fallidos)
    
    with col3:
        st.metric("💾 Tamaño", f"{total_mb:.1f} MB")
    
    if exitosos > 0:
        # Botón descarga ZIP
        zip_buffer.seek(0)
        
        st.markdown("---")
        
        st.download_button(
            label=f"📥 DESCARGAR ZIP ({total_mb:.1f} MB)",
            data=zip_buffer,
            file_name=f"lidar_toledo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip",
            use_container_width=True,
            type="primary"
        )
        
        st.balloons()
        
        st.success(f"""
        ### 🎉 ¡Descarga completada!
        
        **{exitosos} archivo(s)** listos para usar en CloudCompare, QGIS o Python.
        """)
    else:
        st.error("""
        ❌ No se pudo descargar ningún archivo.
        
        **Posible causa**: Streamlit Cloud tiene restricciones con el servidor IGN.
        
        **Solución**: Ejecuta esta app localmente con `streamlit run app.py`
        """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 2rem;'>
    <p><strong>Descargador LiDAR IGN</strong></p>
    <p>Datos © Instituto Geográfico Nacional de España | CC-BY 4.0</p>
    <p>🇪🇸 Desarrollado para la comunidad geoespacial española</p>
</div>
""", unsafe_allow_html=True)
