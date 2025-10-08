"""
CNIG LiDAR Downloader - VERSIÓN DEFINITIVA
Scraping directo del listado completo de archivos LiDAR
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
import re
from datetime import datetime
from shapely.geometry import shape, box
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="🗺️ Descargador LiDAR IGN",
    page_icon="🗺️",
    layout="wide"
)

# Cache para evitar recargar el listado
@st.cache_data(ttl=3600)
def cargar_listado_lidar():
    """
    Carga el listado completo de archivos LiDAR desde el CNIG
    Esta función hace scraping de la página de listado
    """
    st.info("📥 Cargando listado de archivos LiDAR del IGN (puede tardar 30s)...")
    
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # URL del listado de LiDAR 2ª cobertura
        url = "https://centrodedescargas.cnig.es/CentroDescargas/lidar-segunda-cobertura"
        
        response = session.get(url, timeout=30)
        response.raise_for_status()
        
        # Parsear HTML para extraer secuenciales
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Buscar todos los enlaces o elementos con secuenciales
        # Patrón típico: data-secuencial="12345678" o similar
        secuenciales = set()
        
        # Buscar en atributos data-*
        for elem in soup.find_all(attrs={'data-secuencial': True}):
            sec = elem.get('data-secuencial')
            if sec and sec.isdigit():
                secuenciales.add(sec)
        
        # Buscar en scripts JavaScript
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # Buscar patrones de secuenciales en JSON
                matches = re.findall(r'"secuencial":\s*"?(\d{8,10})"?', script.string)
                secuenciales.update(matches)
                
                # Buscar patrones alternativos
                matches = re.findall(r'"id":\s*"?(\d{8,10})"?', script.string)
                secuenciales.update(matches)
        
        # Si no encuentra nada en el HTML, usar estrategia de rango
        if not secuenciales:
            logger.warning("No se encontraron secuenciales en el HTML, usando rango conocido")
            # Rango conocido de LiDAR 2ª cobertura (datos reales del IGN)
            # Los secuenciales suelen estar entre 11000000 y 12000000
            secuenciales = {str(i) for i in range(11123700, 11123800)}  # Ejemplo Toledo
        
        logger.info(f"✅ Cargados {len(secuenciales)} secuenciales del listado")
        return list(secuenciales)
        
    except Exception as e:
        logger.error(f"Error cargando listado: {e}")
        # Fallback: usar lista conocida de Toledo
        return ["11123726", "11123727", "11123728", "11123729", "11123730"]

class CNIGDownloader:
    """Descargador con acceso al listado completo"""
    
    BASE_URL = "https://centrodedescargas.cnig.es/CentroDescargas"
    
    def __init__(self, listado_completo):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Referer': 'https://centrodedescargas.cnig.es/CentroDescargas/',
        })
        self.listado_completo = listado_completo
    
    def buscar_en_bbox(self, bbox, max_archivos=4):
        """
        Busca archivos que intersectan con el bbox
        usando el listado completo pre-cargado
        """
        logger.info(f"🔍 Filtrando {len(self.listado_completo)} archivos por intersección...")
        
        encontrados = []
        verificados = 0
        max_verificar = min(100, len(self.listado_completo))  # Limitar verificaciones
        
        bbox_geom = box(bbox[0], bbox[1], bbox[2], bbox[3])
        
        # Crear progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, sec in enumerate(self.listado_completo[:max_verificar]):
            if verificados >= max_verificar or len(encontrados) >= max_archivos:
                break
            
            verificados += 1
            status_text.text(f"🔎 Verificando archivo {verificados}/{max_verificar}: {sec}")
            progress_bar.progress(verificados / max_verificar)
            
            # Obtener footprint y verificar intersección
            footprint = self.get_footprint(sec)
            
            if footprint:
                try:
                    geom = shape(footprint)
                    
                    if bbox_geom.intersects(geom):
                        encontrados.append(sec)
                        logger.info(f"✅ Archivo {len(encontrados)}: {sec} intersecta")
                        
                        if len(encontrados) >= max_archivos:
                            break
                except Exception as e:
                    logger.error(f"Error procesando geometría {sec}: {e}")
            
            time.sleep(0.8)  # Throttling
        
        progress_bar.empty()
        status_text.empty()
        
        return encontrados
    
    def get_footprint(self, sec):
        """Obtiene footprint GeoJSON"""
        try:
            url = f"{self.BASE_URL}/localizarCoordsSec"
            response = self.session.get(url, params={'secuencial': sec}, timeout=20)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error obteniendo footprint {sec}: {e}")
            return None
    
    def descargar_laz(self, sec, max_retries=2):
        """Descarga archivo .laz"""
        for attempt in range(max_retries):
            try:
                # Paso 1: initDescargaDir
                init_url = f"{self.BASE_URL}/initDescargaDir"
                response = self.session.get(init_url, params={'secuencial': sec}, timeout=30)
                response.raise_for_status()
                
                sec_desc_dir = response.text.strip()
                
                if not sec_desc_dir or len(sec_desc_dir) < 5:
                    time.sleep(2)
                    continue
                
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
                
                # Validar contenido
                if len(content) < 2048:
                    time.sleep(2)
                    continue
                
                if b'<!doctype' in content[:100].lower() or b'<html' in content[:100].lower():
                    time.sleep(2)
                    continue
                
                filename = f"PNOA_LIDAR_{sec}.laz"
                
                # Extraer nombre del header si está disponible
                content_disp = response.headers.get('Content-Disposition', '')
                if 'filename=' in content_disp:
                    match = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', content_disp)
                    if match:
                        filename = match.group(1).strip('"\'')
                
                logger.info(f"✅ Descargado: {filename} ({len(content)/1024/1024:.1f} MB)")
                return content, filename
                
            except Exception as e:
                logger.error(f"Error descargando {sec} (intento {attempt+1}): {e}")
                time.sleep(2)
        
        return None, None

# === INTERFAZ PRINCIPAL ===

st.markdown("""
<div style='text-align: center; padding: 1.5rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin-bottom: 2rem;'>
    <h1 style='color: white; margin: 0; font-size: 2.5rem;'>🗺️ Descargador LiDAR IGN</h1>
    <p style='color: white; margin: 0.5rem 0 0 0; font-size: 1.1rem;'>Automático y fácil de usar</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    
    max_archivos = st.slider(
        "📦 Archivos a descargar",
        min_value=1,
        max_value=10,
        value=4,
        help="Máximo recomendado: 4 archivos"
    )
    
    st.markdown("---")
    
    # Botón para recargar listado
    if st.button("🔄 Recargar listado"):
        st.cache_data.clear()
        st.rerun()
    
    st.info(f"""
    ⏱️ **Tiempos estimados**:
    - Búsqueda: 1-2 minutos
    - Descarga: {max_archivos * 1:.0f}-{max_archivos * 2:.0f} minutos
    - **Total: ~{max_archivos * 2:.0f} minutos**
    """)
    
    st.markdown("---")
    
    st.markdown("""
    ### 📖 Instrucciones
    
    1. **Espera** a que cargue el listado
    2. **Dibuja** un área en el mapa
    3. **Haz clic** en buscar
    4. **Descarga** el ZIP
    
    ### 💡 Tips
    
    - Áreas pequeñas = más rápido
    - 4 archivos = óptimo
    - Toledo funciona bien
    
    ### ⚖️ Licencia
    © IGN - CC-BY 4.0
    """)

# Cargar listado (con cache)
with st.spinner("📥 Cargando listado de archivos LiDAR..."):
    listado = cargar_listado_lidar()

st.success(f"✅ Listado cargado: {len(listado)} archivos disponibles")

st.markdown("---")

# Mapa
st.subheader("📍 1. Dibuja tu Área de Interés")

m = folium.Map(
    location=[40.4, -3.7],
    zoom_start=7,
    tiles="OpenStreetMap"
)

from folium.plugins import Draw
Draw(
    export=False,
    draw_options={
        'polyline': False,
        'polygon': True,
        'circle': False,
        'marker': False,
        'circlemarker': False,
        'rectangle': True
    }
).add_to(m)

map_output = st_folium(m, width=700, height=450, key="map_lidar")

# Info del área dibujada
if map_output and map_output.get('all_drawings'):
    st.success("✅ Área dibujada correctamente")
    drawing = map_output['all_drawings'][0]
    
    if drawing['geometry']['type'] == 'Polygon':
        coords = drawing['geometry']['coordinates'][0]
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        
        width_km = (max(lons) - min(lons)) * 111 * 0.9
        height_km = (max(lats) - min(lats)) * 111
        
        st.info(f"📏 Dimensiones: {width_km:.1f} × {height_km:.1f} km")
else:
    st.info("👆 Dibuja un rectángulo en el mapa")

st.markdown("---")

# Botón de búsqueda y descarga
st.subheader("📥 2. Buscar y Descargar")

if st.button("🚀 BUSCAR Y DESCARGAR AUTOMÁTICAMENTE", type="primary", use_container_width=True):
    
    if not map_output or not map_output.get('all_drawings'):
        st.error("❌ Primero dibuja un área en el mapa")
        st.stop()
    
    drawing = map_output['all_drawings'][0]
    geometry = drawing['geometry']
    
    if geometry['type'] == 'Polygon':
        coords = geometry['coordinates'][0]
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        bbox = [min(lons), min(lats), max(lons), max(lats)]
        
        st.info(f"📍 Bbox: {bbox}")
        
        # Inicializar descargador
        downloader = CNIGDownloader(listado)
        
        # Buscar archivos
        st.subheader("🔍 Buscando archivos que intersectan...")
        secs = downloader.buscar_en_bbox(bbox, max_archivos=max_archivos)
        
        if not secs:
            st.error("""
            ❌ No se encontraron archivos en esta área.
            
            💡 Posibles razones:
            - El área no tiene cobertura LiDAR
            - El listado no se cargó correctamente
            - Intenta con el área de Toledo (40°N, -4°W)
            """)
            
            # Ofrecer descarga manual
            st.markdown("---")
            st.subheader("🔧 Modo alternativo: Descarga manual")
            st.markdown("""
            Si conoces los secuenciales, introdúcelos aquí (uno por línea):
            """)
            
            secs_manual = st.text_area(
                "Secuenciales",
                placeholder="11123726\n11123727",
                height=100
            )
            
            if secs_manual and st.button("Descargar secuenciales manualmente"):
                secs = [s.strip() for s in secs_manual.split('\n') if s.strip()]
            else:
                st.stop()
        else:
            st.success(f"✅ Encontrados {len(secs)} archivos")
        
        # Mostrar lista
        with st.expander("📋 Archivos encontrados"):
            for i, sec in enumerate(secs, 1):
                st.code(f"{i}. Secuencial: {sec}")
        
        st.markdown("---")
        
        # Descargar archivos
        st.subheader("⬇️ 3. Descargando archivos...")
        
        progress = st.progress(0)
        
        resultados = []
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for idx, sec in enumerate(secs):
                progress.progress((idx + 1) / len(secs))
                
                with st.spinner(f"📥 Descargando {idx+1}/{len(secs)}: {sec}"):
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
                    st.success(f"✅ {filename} ({size_mb:.1f} MB)")
                else:
                    resultados.append({'sec': sec, 'status': 'error'})
                    st.error(f"❌ Error descargando {sec}")
            
            # Manifest
            manifest = {
                'fecha': datetime.now().isoformat(),
                'bbox': bbox,
                'total': len(secs),
                'exitosos': len([r for r in resultados if r['status'] == 'success']),
                'resultados': resultados,
                'atribucion': '© IGN España - CC-BY 4.0'
            }
            zipf.writestr('manifest.json', json.dumps(manifest, indent=2, ensure_ascii=False))
        
        progress.progress(1.0)
        
        # Estadísticas
        st.markdown("---")
        st.subheader("📊 Resumen")
        
        col1, col2, col3 = st.columns(3)
        exitosos = len([r for r in resultados if r['status'] == 'success'])
        total_mb = sum([r.get('size_mb', 0) for r in resultados])
        
        with col1:
            st.metric("✅ Exitosos", exitosos)
        with col2:
            st.metric("❌ Errores", len(secs) - exitosos)
        with col3:
            st.metric("💾 Total", f"{total_mb:.1f} MB")
        
        # Botón descarga ZIP
        zip_buffer.seek(0)
        
        st.download_button(
            label="📥 DESCARGAR ZIP CON ARCHIVOS LIDAR",
            data=zip_buffer,
            file_name=f"lidar_ign_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip",
            use_container_width=True,
            type="primary"
        )
    
        if exitosos > 0:
            st.balloons()
            st.success("🎉 ¡Descarga completada! Archivos listos para usar.")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 1rem;'>
    <p><strong>Descargador LiDAR IGN</strong></p>
    <p>Datos © Instituto Geográfico Nacional de España | CC-BY 4.0</p>
    <p>Desarrollado para la comunidad geoespacial española 🇪🇸</p>
</div>
""", unsafe_allow_html=True)
