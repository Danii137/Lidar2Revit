"""
CNIG LiDAR Downloader - Herramienta Cloud
Marca región en mapa → Descarga archivos LiDAR automáticamente
Deployable en Streamlit Cloud + GitHub

© 2025 - Datos del IGN bajo licencia CC-BY 4.0
"""

import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import json
import zipfile
import io
import time
import logging
from datetime import datetime
from shapely.geometry import shape, mapping

# Configuración
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de página
st.set_page_config(
    page_title="Descargador LiDAR IGN",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Clase principal
class CNIGDownloader:
    """Descargador de archivos LiDAR del CNIG"""
    
    BASE_URL = "https://centrodedescargas.cnig.es/CentroDescargas"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Referer': 'https://centrodedescargas.cnig.es/CentroDescargas/',
        })
    
    def buscar_por_geometria(self, geojson_geometry, cod_serie="LIDA2"):
        """
        Busca archivos LiDAR por geometría usando endpoint buscarGeom
        
        Args:
            geojson_geometry: Geometría GeoJSON del AOI
            cod_serie: LIDA2 (2ª cobertura) o LIDA3 (3ª cobertura)
        """
        try:
            # Preparar GeoJSON según formato CNIG
            geojson_aoi = {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "geometry": geojson_geometry
                }]
            }
            
            # Datos del formulario
            form_data = {
                'coordenadas': json.dumps(geojson_aoi),
                'series': cod_serie,
                'codSerie': cod_serie,
            }
            
            logger.info(f"Buscando archivos LiDAR en la región especificada...")
            
            # Llamar al endpoint
            url = f"{self.BASE_URL}/buscarGeom"
            response = self.session.post(url, data=form_data, timeout=60)
            response.raise_for_status()
            
            # Extraer secuenciales del HTML
            import re
            html = response.text
            
            # Buscar todos los secuenciales en el HTML
            pattern = r'secuencial["\s:=]+(\d{8,10})'
            secs = list(set(re.findall(pattern, html, re.IGNORECASE)))
            
            # También buscar en atributos data-sec, onclick, etc.
            pattern2 = r'data-sec["\s:=]+(\d{8,10})'
            secs.extend(re.findall(pattern2, html, re.IGNORECASE))
            
            # Buscar en scripts JavaScript
            pattern3 = r'"secuencial":\s*"?(\d{8,10})"?'
            secs.extend(re.findall(pattern3, html, re.IGNORECASE))
            
            secs = list(set(secs))  # Eliminar duplicados
            
            logger.info(f"✅ Encontrados {len(secs)} archivos LiDAR")
            return secs
            
        except Exception as e:
            logger.error(f"Error buscando por geometría: {e}")
            return []
    
    def descargar_laz(self, sec, max_retries=3):
        """
        Descarga un archivo .laz por su secuencial
        
        Args:
            sec: Secuencial del archivo
            max_retries: Número de reintentos
        """
        for attempt in range(max_retries):
            try:
                # Paso 1: Obtener secuencialDescDir
                init_url = f"{self.BASE_URL}/initDescargaDir"
                response = self.session.get(init_url, params={'secuencial': sec}, timeout=30)
                response.raise_for_status()
                
                sec_desc_dir = response.text.strip()
                
                if not sec_desc_dir or len(sec_desc_dir) < 5:
                    logger.warning(f"[{sec}] secuencialDescDir inválido")
                    time.sleep(2 * (attempt + 1))
                    continue
                
                time.sleep(1.5)  # Throttling
                
                # Paso 2: Descargar archivo
                download_url = f"{self.BASE_URL}/descargaDir"
                response = self.session.post(
                    download_url,
                    data={'secDescDirLA': sec_desc_dir},
                    timeout=300,
                    stream=True
                )
                response.raise_for_status()
                
                content = response.content
                
                # Validar que sea archivo válido
                if len(content) < 2048:
                    logger.warning(f"[{sec}] Archivo muy pequeño")
                    time.sleep(2 * (attempt + 1))
                    continue
                
                if b'<!doctype' in content[:100].lower() or b'<html' in content[:100].lower():
                    logger.warning(f"[{sec}] Respuesta HTML (error)")
                    time.sleep(2 * (attempt + 1))
                    continue
                
                # Extraer nombre
                filename = f"PNOA_LIDAR_{sec}.laz"
                content_disp = response.headers.get('Content-Disposition', '')
                if 'filename=' in content_disp:
                    import re
                    match = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', content_disp)
                    if match:
                        filename = match.group(1).strip('"\'')
                
                logger.info(f"✅ [{sec}] Descargado: {filename} ({len(content)/1024/1024:.1f} MB)")
                return content, filename
                
            except Exception as e:
                logger.error(f"❌ [{sec}] Error intento {attempt+1}: {e}")
                time.sleep(2 * (attempt + 1))
        
        logger.error(f"❌ [{sec}] Falló después de {max_retries} intentos")
        return None, None

# --- INTERFAZ DE USUARIO ---

st.markdown('<div class="main-header">🗺️ Descargador LiDAR IGN</div>', unsafe_allow_html=True)

st.markdown("""
**Herramienta automática para descargar datos LiDAR del Instituto Geográfico Nacional (IGN)**

1. 📍 Dibuja un área en el mapa
2. 🔍 La app busca automáticamente los archivos LiDAR
3. ⬇️ Descarga todo en un archivo ZIP

---
""")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    
    cobertura = st.selectbox(
        "Cobertura LiDAR",
        options=[
            ("LIDA2", "2ª Cobertura (2015-2021)"),
            ("LIDA3", "3ª Cobertura (2022-2025)")
        ],
        format_func=lambda x: x[1],
        index=0
    )
    cod_serie = cobertura[0]
    
    max_archivos = st.slider(
        "Máximo archivos a descargar",
        min_value=1,
        max_value=50,
        value=10,
        help="Limita el número de archivos (recomendado para pruebas)"
    )
    
    st.markdown("---")
    st.markdown("""
    ### 📖 Instrucciones
    
    1. **Usa las herramientas** del mapa para dibujar un polígono o rectángulo
    2. **Haz clic** en "🚀 Buscar y Descargar"
    3. **Espera** mientras se descargan los archivos
    4. **Descarga** el ZIP generado
    
    ### ⚖️ Licencia
    Datos: **CC-BY 4.0**  
    © Instituto Geográfico Nacional de España
    
    ### 🌐 Fuente
    [Centro de Descargas CNIG](https://centrodedescargas.cnig.es)
    """)

# Mapa principal
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("📍 Define el Área de Interés")
    
    # Crear mapa con Folium
    m = folium.Map(
        location=[40.4168, -3.7038],  # Madrid
        zoom_start=7,
        tiles="OpenStreetMap"
    )
    
    # Herramientas de dibujo
    from folium.plugins import Draw
    Draw(
        export=False,
        position='topleft',
        draw_options={
            'polyline': False,
            'polygon': True,
            'circle': False,
            'marker': False,
            'circlemarker': False,
            'rectangle': True
        },
        edit_options={'edit': False}
    ).add_to(m)
    
    # Mostrar mapa
    map_output = st_folium(m, width=700, height=500, key="main_map")

with col2:
    st.subheader("ℹ️ Info")
    
    if map_output and map_output.get('all_drawings'):
        num_drawings = len(map_output['all_drawings'])
        st.success(f"✅ {num_drawings} área(s) dibujada(s)")
        
        with st.expander("Ver geometría"):
            st.json(map_output['all_drawings'][0])
    else:
        st.info("👆 Dibuja un área en el mapa")
    
    st.metric("Cobertura seleccionada", cobertura[1])
    st.metric("Máximo archivos", max_archivos)

# Botón principal
st.markdown("---")

if st.button("🚀 Buscar y Descargar LiDAR", type="primary", use_container_width=True):
    
    # Validar que hay área dibujada
    if not map_output or not map_output.get('all_drawings'):
        st.error("❌ Por favor, dibuja un área en el mapa primero")
        st.stop()
    
    # Obtener geometría
    try:
        drawing = map_output['all_drawings'][0]
        geometry = drawing['geometry']
        
        st.info(f"📍 Área seleccionada: {geometry['type']}")
        
        # Inicializar descargador
        downloader = CNIGDownloader()
        
        # Buscar archivos
        with st.spinner("🔍 Buscando archivos LiDAR en la región..."):
            secs = downloader.buscar_por_geometria(geometry, cod_serie)
        
        if not secs:
            st.warning("⚠️ No se encontraron archivos LiDAR en esta región")
            st.info("💡 Intenta con un área más grande o diferente cobertura")
            st.stop()
        
        st.success(f"✅ Encontrados {len(secs)} archivos LiDAR")
        
        # Limitar número de archivos
        if len(secs) > max_archivos:
            st.warning(f"⚠️ Se descargarán solo {max_archivos} de {len(secs)} archivos (límite configurado)")
            secs = secs[:max_archivos]
        
        # Mostrar lista
        with st.expander("Ver lista de archivos"):
            for i, sec in enumerate(secs, 1):
                st.code(f"{i}. Secuencial: {sec}")
        
        # Descargar archivos
        st.subheader("⬇️ Descargando archivos...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        results_container = st.container()
        
        resultados = []
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for idx, sec in enumerate(secs):
                status_text.text(f"📥 Descargando {idx+1}/{len(secs)}: {sec}")
                progress_bar.progress((idx + 1) / len(secs))
                
                content, filename = downloader.descargar_laz(sec)
                
                if content:
                    zipf.writestr(filename, content)
                    resultados.append({
                        'sec': sec,
                        'filename': filename,
                        'size_mb': len(content) / 1024 / 1024,
                        'status': 'success'
                    })
                    
                    with results_container:
                        st.success(f"✅ {filename} ({len(content)/1024/1024:.1f} MB)")
                else:
                    resultados.append({
                        'sec': sec,
                        'status': 'error'
                    })
                    
                    with results_container:
                        st.error(f"❌ Error: {sec}")
            
            # Agregar manifest
            manifest = {
                'fecha_descarga': datetime.now().isoformat(),
                'cobertura': cobertura[1],
                'total_archivos': len(secs),
                'exitosos': len([r for r in resultados if r['status'] == 'success']),
                'fallidos': len([r for r in resultados if r['status'] == 'error']),
                'geometria': geometry,
                'resultados': resultados,
                'atribucion': '© Instituto Geográfico Nacional de España - CC-BY 4.0'
            }
            
            zipf.writestr('manifest.json', json.dumps(manifest, indent=2, ensure_ascii=False))
        
        progress_bar.progress(1.0)
        status_text.text("✅ ¡Descarga completada!")
        
        # Estadísticas
        st.markdown("---")
        st.subheader("📊 Resumen")
        
        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            st.metric("Total", len(secs))
        with col_b:
            exitosos = len([r for r in resultados if r['status'] == 'success'])
            st.metric("Exitosos", exitosos, delta=f"{exitosos/len(secs)*100:.0f}%")
        with col_c:
            fallidos = len([r for r in resultados if r['status'] == 'error'])
            st.metric("Errores", fallidos)
        with col_d:
            total_mb = sum([r.get('size_mb', 0) for r in resultados])
            st.metric("Tamaño total", f"{total_mb:.1f} MB")
        
        # Botón de descarga
        zip_buffer.seek(0)
        
        st.download_button(
            label="📥 DESCARGAR ZIP CON ARCHIVOS LIDAR",
            data=zip_buffer,
            file_name=f"lidar_ign_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip",
            use_container_width=True
        )
        
        st.success("🎉 ¡Descarga completada! Ya puedes usar los archivos LiDAR para tus análisis.")
        
    except Exception as e:
        st.error(f"❌ Error procesando la solicitud: {e}")
        logger.exception(e)

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.9rem;">
    Desarrollado para la comunidad geoespacial española 🇪🇸<br>
    Datos © IGN - Licencia CC-BY 4.0 | Herramienta de código abierto
</div>
""", unsafe_allow_html=True)
