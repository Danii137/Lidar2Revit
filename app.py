"""
Descargador LiDAR IGN - Versión Simple que FUNCIONA
"""

import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import json
import zipfile
import io
import time
from datetime import datetime

st.set_page_config(
    page_title="🗺️ Descargador LiDAR IGN",
    page_icon="🗺️",
    layout="wide"
)

# LISTA HARDCODEADA DE SECUENCIALES REALES (Toledo - FUNCIONAN 100%)
SECUENCIALES_DISPONIBLES = [
    "11123726", "11123727", "11123728", "11123729", 
    "11123730", "11123731", "11123732", "11123733"
]

class CNIGDownloader:
    """Descargador simple y funcional"""
    
    BASE_URL = "https://centrodedescargas.cnig.es/CentroDescargas"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://centrodedescargas.cnig.es/CentroDescargas/',
        })
    
    def descargar_laz(self, sec):
        """Descarga un archivo .laz"""
        try:
            # Paso 1: initDescargaDir
            init_url = f"{self.BASE_URL}/initDescargaDir"
            response = self.session.get(init_url, params={'secuencial': sec}, timeout=30)
            response.raise_for_status()
            
            sec_desc_dir = response.text.strip()
            
            if not sec_desc_dir or len(sec_desc_dir) < 5:
                return None, None
            
            time.sleep(1.5)
            
            # Paso 2: descargaDir
            download_url = f"{self.BASE_URL}/descargaDir"
            response = self.session.post(
                download_url,
                data={'secDescDirLA': sec_desc_dir},
                timeout=300,
                stream=True
            )
            response.raise_for_status()
            
            content = response.content
            
            # Validar
            if len(content) < 2048:
                return None, None
            
            if b'<!doctype' in content[:100].lower() or b'<html' in content[:100].lower():
                return None, None
            
            filename = f"PNOA_LIDAR_{sec}.laz"
            return content, filename
            
        except Exception as e:
            st.error(f"Error descargando {sec}: {e}")
            return None, None

# === INTERFAZ ===

st.markdown("""
<div style='text-align: center; padding: 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; margin-bottom: 2rem;'>
    <h1 style='color: white; margin: 0;'>🗺️ Descargador LiDAR IGN</h1>
    <p style='color: white; margin: 1rem 0 0 0;'>Descarga archivos LiDAR de Toledo automáticamente</p>
</div>
""", unsafe_allow_html=True)

# Info
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("""
    ### 📋 Cómo funciona
    
    1. **Selecciona** cuántos archivos quieres descargar (1-4)
    2. **Haz clic** en el botón "DESCARGAR LIDAR"
    3. **Espera** 2-5 minutos mientras se descargan
    4. **Descarga** el archivo ZIP generado
    
    ### 📍 Región disponible
    
    - **Toledo** (España) - LiDAR 2ª Cobertura
    - Archivos .laz de ~10-50 MB cada uno
    - Formato: PNOA LiDAR 2015-2021
    """)

with col2:
    st.info(f"""
    ### ✅ Archivos disponibles
    
    **{len(SECUENCIALES_DISPONIBLES)} archivos** de Toledo listos para descargar
    
    ### ⏱️ Tiempo estimado
    
    - 1 archivo: ~1 min
    - 2 archivos: ~2 min
    - 4 archivos: ~4 min
    """)

st.markdown("---")

# Mapa (solo visual)
st.subheader("📍 Región: Toledo, España")

m = folium.Map(
    location=[39.86, -4.03],  # Toledo
    zoom_start=12,
    tiles="OpenStreetMap"
)

# Añadir marcador en Toledo
folium.Marker(
    [39.86, -4.03],
    popup="Toledo - Archivos LiDAR disponibles",
    tooltip="Zona de descarga",
    icon=folium.Icon(color='blue', icon='info-sign')
).add_to(m)

st_folium(m, width=700, height=400)

st.markdown("---")

# Configuración
st.subheader("⚙️ Configuración de Descarga")

col_a, col_b = st.columns([1, 2])

with col_a:
    num_archivos = st.selectbox(
        "Número de archivos a descargar",
        options=[1, 2, 3, 4],
        index=1,  # Default: 2 archivos
        help="Más archivos = más tiempo de descarga"
    )

with col_b:
    st.info(f"""
    **Descargarás {num_archivos} archivo(s)**
    
    - Tiempo estimado: ~{num_archivos * 1.5:.0f} minutos
    - Tamaño total: ~{num_archivos * 25:.0f} MB
    - Región: Toledo
    """)

st.markdown("---")

# BOTÓN PRINCIPAL
if st.button("🚀 DESCARGAR LIDAR AHORA", type="primary", use_container_width=True):
    
    # Seleccionar secuenciales
    secs_to_download = SECUENCIALES_DISPONIBLES[:num_archivos]
    
    st.info(f"📦 Descargando {len(secs_to_download)} archivos de Toledo...")
    
    # Mostrar secuenciales
    with st.expander("Ver secuenciales"):
        for i, sec in enumerate(secs_to_download, 1):
            st.code(f"{i}. {sec}")
    
    # Inicializar descargador
    downloader = CNIGDownloader()
    
    # Crear ZIP
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    resultados = []
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        
        for idx, sec in enumerate(secs_to_download):
            status_text.markdown(f"### ⬇️ Descargando archivo {idx+1}/{len(secs_to_download)}: `{sec}`")
            progress_bar.progress((idx + 1) / len(secs_to_download))
            
            with st.spinner(f"Procesando {sec}..."):
                content, filename = downloader.descargar_laz(sec)
            
            if content:
                zipf.writestr(filename, content)
                size_mb = len(content) / 1024 / 1024
                
                resultados.append({
                    'sec': sec,
                    'filename': filename,
                    'size_mb': size_mb,
                    'status': 'success'
                })
                
                st.success(f"✅ **{filename}** - {size_mb:.1f} MB descargado")
            else:
                resultados.append({
                    'sec': sec,
                    'status': 'error'
                })
                st.error(f"❌ Error descargando {sec}")
        
        # Añadir manifest
        manifest = {
            'fecha_descarga': datetime.now().isoformat(),
            'region': 'Toledo, España',
            'cobertura': 'PNOA LiDAR 2ª Cobertura (2015-2021)',
            'total_archivos': len(secs_to_download),
            'exitosos': len([r for r in resultados if r['status'] == 'success']),
            'fallidos': len([r for r in resultados if r['status'] == 'error']),
            'archivos': resultados,
            'atribucion': '© Instituto Geográfico Nacional de España - Licencia CC-BY 4.0',
            'fuente': 'https://centrodedescargas.cnig.es'
        }
        
        zipf.writestr('README.txt', f"""
ARCHIVOS LIDAR - TOLEDO (ESPAÑA)
================================

Fecha de descarga: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
Región: Toledo, España
Cobertura: PNOA LiDAR 2ª Cobertura (2015-2021)

Archivos incluidos: {len([r for r in resultados if r['status'] == 'success'])}

LICENCIA
--------
Datos © Instituto Geográfico Nacional de España
Licencia: Creative Commons Reconocimiento 4.0 (CC-BY 4.0)
Fuente: https://centrodedescargas.cnig.es

ATRIBUCIÓN REQUERIDA
--------------------
Al usar estos datos, debes citar:
"Datos © Instituto Geográfico Nacional de España"

USO RECOMENDADO
---------------
- CloudCompare: Visualización de nubes de puntos
- QGIS: Análisis geoespacial
- Python (laspy, pdal): Procesamiento programático
- ArcGIS: Análisis SIG profesional
        """)
        
        zipf.writestr('manifest.json', json.dumps(manifest, indent=2, ensure_ascii=False))
    
    progress_bar.progress(1.0)
    status_text.empty()
    
    # Estadísticas finales
    st.markdown("---")
    st.markdown("## 📊 Resumen de Descarga")
    
    col1, col2, col3 = st.columns(3)
    
    exitosos = len([r for r in resultados if r['status'] == 'success'])
    fallidos = len([r for r in resultados if r['status'] == 'error'])
    total_mb = sum([r.get('size_mb', 0) for r in resultados if r['status'] == 'success'])
    
    with col1:
        st.metric("✅ Descargados", exitosos, delta=f"{exitosos/len(secs_to_download)*100:.0f}%")
    
    with col2:
        st.metric("❌ Errores", fallidos)
    
    with col3:
        st.metric("💾 Tamaño Total", f"{total_mb:.1f} MB")
    
    if exitosos > 0:
        # Botón de descarga del ZIP
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
        ### 🎉 ¡Descarga completada con éxito!
        
        **{exitosos} archivo(s) LiDAR** listo(s) para usar.
        
        #### 📂 Contenido del ZIP:
        - {exitosos} archivo(s) .laz (nubes de puntos)
        - 1 archivo README.txt (información)
        - 1 archivo manifest.json (metadatos)
        
        #### 🔧 Software recomendado:
        - **CloudCompare** (gratuito) - Visualización 3D
        - **QGIS** (gratuito) - Análisis geoespacial
        - **Python** - Procesamiento con laspy/pdal
        """)
    else:
        st.error("""
        ❌ No se pudo descargar ningún archivo.
        
        **Posibles causas**:
        - Problema de conexión con el servidor IGN
        - Los secuenciales no están disponibles temporalmente
        - Timeout de la petición
        
        **Solución**: Intenta de nuevo en unos minutos.
        """)

# Información adicional
st.markdown("---")

with st.expander("ℹ️ Información sobre los datos LiDAR"):
    st.markdown("""
    ### ¿Qué son los datos LiDAR?
    
    **LiDAR** (Light Detection and Ranging) es una tecnología de teledetección que usa pulsos láser 
    para medir distancias y crear modelos 3D precisos del terreno.
    
    ### Formato .laz
    
    - **Formato**: Compresión sin pérdida de archivos .las
    - **Contenido**: Nubes de puntos 3D con coordenadas X, Y, Z
    - **Atributos**: Intensidad, clasificación, número de retorno, etc.
    - **Tamaño**: Típicamente 10-50 MB por tesela de 2×2 km
    
    ### Cobertura 2ª (2015-2021)
    
    - **Densidad**: ≥ 0.5 puntos/m²
    - **Precisión vertical**: ≤ 20 cm RMSE
    - **Proyección**: ETRS89 / UTM
    - **Clasificación**: Suelo, vegetación, edificios, etc.
    
    ### Aplicaciones
    
    - Modelos digitales de elevación (DEM/DTM)
    - Análisis forestal y vegetación
    - Planificación urbana
    - Estudios de inundaciones
    - Arqueología
    - Infraestructuras
    """)

with st.expander("⚖️ Licencia y Atribución"):
    st.markdown("""
    ### Licencia de los Datos
    
    Los datos LiDAR del PNOA están publicados bajo licencia **CC-BY 4.0** 
    (Creative Commons Reconocimiento 4.0 Internacional).
    
    ### Atribución Obligatoria
    
    Al usar estos datos en cualquier trabajo, publicación o producto, 
    debes incluir la siguiente atribución:
    
    > Datos © Instituto Geográfico Nacional de España
    
    ### Más Información
    
    - **Web oficial**: [www.ign.es](https://www.ign.es)
    - **Centro de Descargas**: [centrodedescargas.cnig.es](https://centrodedescargas.cnig.es)
    - **PNOA LiDAR**: [pnoa.ign.es](https://pnoa.ign.es/pnoa-lidar)
    
    ### Licencia de esta Herramienta
    
    Esta aplicación es de código abierto y se proporciona "tal cual" 
    para facilitar el acceso a los datos públicos del IGN.
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 2rem; background-color: #f8f9fa; border-radius: 10px;'>
    <h3 style='margin: 0;'>🗺️ Descargador LiDAR IGN</h3>
    <p style='margin: 0.5rem 0;'>Herramienta gratuita para descargar datos LiDAR del Instituto Geográfico Nacional</p>
    <p style='margin: 0.5rem 0;'><strong>Datos</strong>: © IGN España | <strong>Licencia</strong>: CC-BY 4.0</p>
    <p style='margin: 0; font-size: 0.9rem;'>Desarrollado para la comunidad geoespacial española 🇪🇸</p>
</div>
""", unsafe_allow_html=True)
