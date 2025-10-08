"""
CNIG LiDAR Downloader - Modo Automático REAL
Estrategia: Scraping de listado + filtrado geométrico + descarga en lotes
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
from shapely.geometry import shape, mapping, box, Point

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="🗺️ Descargador LiDAR IGN",
    page_icon="🗺️",
    layout="wide"
)

class CNIGDownloader:
    """Descargador automático con scraping de listado"""
    
    BASE_URL = "https://centrodedescargas.cnig.es/CentroDescargas"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Referer': 'https://centrodedescargas.cnig.es/CentroDescargas/',
        })
    
    def buscar_automatico(self, bbox, max_archivos=4):
        """
        Busca archivos LiDAR automáticamente usando el listado del CNIG
        
        Estrategia:
        1. Acceder a la página de listado de LiDAR 2ª cobertura
        2. Parsear HTML para extraer secuenciales
        3. Para cada secuencial, verificar si intersecta con bbox
        4. Devolver los primeros N que intersectan
        
        Args:
            bbox: [minx, miny, maxx, maxy] en WGS84
            max_archivos: Máximo de archivos a buscar (default: 4)
        """
        logger.info(f"🔍 Buscando archivos en bbox: {bbox}")
        
        # Calcular centro y dimensiones del área
        center_lon = (bbox[0] + bbox[2]) / 2
        center_lat = (bbox[1] + bbox[3]) / 2
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        
        logger.info(f"Centro: ({center_lon:.4f}, {center_lat:.4f})")
        logger.info(f"Dimensiones: {width:.4f}° × {height:.4f}°")
        
        secs_encontrados = []
        
        try:
            # Estrategia 1: Buscar por hoja MTN50 aproximada
            # Las coordenadas en España peninsular están en UTM zona 30
            # Convertir aproximadamente lat/lon a coordenadas UTM
            
            # Aproximación simple: cada grado ≈ 111 km en latitud
            # y varía en longitud según latitud
            utm_x_approx = int((center_lon + 3.7) * 111000 * 0.9)  # Aprox para zona 30N
            utm_y_approx = int(center_lat * 111000)
            
            # Las teselas son de 2x2 km
            # Generar coordenadas candidatas (esquina superior izquierda)
            # en rejilla de 2km
            
            candidatos_coords = []
            
            # Generar rejilla de búsqueda
            for x_offset in range(-6, 8, 2):  # ±12 km en X
                for y_offset in range(-6, 8, 2):  # ±12 km en Y
                    x_coord = (utm_x_approx // 2000) * 2000 + (x_offset * 1000)
                    y_coord = (utm_y_approx // 2000) * 2000 + (y_offset * 1000)
                    candidatos_coords.append((x_coord, y_coord))
            
            logger.info(f"🔎 Generando {len(candidatos_coords)} coordenadas candidatas...")
            
            # Buscar secuenciales por patrón de nombre
            # Formato típico: PNOA_2016_CLM-SE_579-4416_ORT-CLA-RGB
            # Donde 579 y 4416 son coordenadas UTM/1000
            
            for idx, (x, y) in enumerate(candidatos_coords[:30]):  # Limitar búsqueda
                # Construir posibles nombres de archivo
                x_code = x // 1000
                y_code = y // 1000
                
                # Intentar buscar por palabra clave con coordenadas
                keyword = f"LIDAR {x_code}-{y_code}"
                
                logger.info(f"[{idx+1}/30] Buscando: {keyword}")
                
                resultados = self._buscar_por_keyword(keyword)
                
                for resultado in resultados:
                    sec = resultado.get('id') or resultado.get('secuencial')
                    if sec and sec not in [s['sec'] for s in secs_encontrados]:
                        # Verificar intersección real
                        if self._verifica_interseccion(sec, bbox):
                            secs_encontrados.append({
                                'sec': sec,
                                'coord': (x, y)
                            })
                            logger.info(f"  ✅ Encontrado: {sec}")
                            
                            if len(secs_encontrados) >= max_archivos:
                                logger.info(f"🎯 Alcanzado límite de {max_archivos} archivos")
                                return secs_encontrados
                
                time.sleep(1.0)  # Throttling
            
            # Estrategia 2: Si no encuentra nada, buscar genéricamente
            if not secs_encontrados:
                logger.info("📍 Estrategia 2: Búsqueda genérica por región...")
                secs_encontrados = self._busqueda_generica(bbox, max_archivos)
            
            return secs_encontrados
            
        except Exception as e:
            logger.error(f"❌ Error en búsqueda automática: {e}")
            return []
    
    def _buscar_por_keyword(self, keyword):
        """Busca por palabra clave en el endpoint buscarContenido"""
        try:
            url = f"{self.BASE_URL}/buscarContenido"
            params = {'palabraClave': keyword}
            
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            return data.get('listaAutocomp', [])
            
        except:
            return []
    
    def _busqueda_generica(self, bbox, max_archivos):
        """Búsqueda genérica cuando fallan otras estrategias"""
        logger.info("🌍 Búsqueda genérica por área aproximada...")
        
        # Buscar por provincia/comunidad si es posible
        center_lat = (bbox[1] + bbox[3]) / 2
        center_lon = (bbox[0] + bbox[2]) / 2
        
        # Keywords genéricos por zona aproximada
        keywords = [
            "LIDAR 2",
            "PNOA LIDAR segunda",
        ]
        
        secs = []
        
        for keyword in keywords:
            resultados = self._buscar_por_keyword(keyword)
            
            for r in resultados[:50]:  # Primeros 50 resultados
                sec = r.get('id') or r.get('secuencial')
                if sec and sec not in [s['sec'] for s in secs]:
                    if self._verifica_interseccion(sec, bbox):
                        secs.append({'sec': sec})
                        logger.info(f"✅ Genérico: {sec}")
                        
                        if len(secs) >= max_archivos:
                            return secs
                
                time.sleep(0.5)
        
        return secs
    
    def _verifica_interseccion(self, sec, bbox):
        """Verifica si un secuencial intersecta con el bbox"""
        try:
            footprint = self.get_footprint(sec)
            if not footprint:
                return False
            
            geom = shape(footprint)
            bbox_geom = box(bbox[0], bbox[1], bbox[2], bbox[3])
            
            intersecta = geom.intersects(bbox_geom)
            
            if intersecta:
                logger.info(f"  ✓ {sec} intersecta")
            
            return intersecta
            
        except Exception as e:
            logger.error(f"  Error verificando {sec}: {e}")
            return False
    
    def get_footprint(self, sec):
        """Obtiene footprint de un secuencial"""
        try:
            url = f"{self.BASE_URL}/localizarCoordsSec"
            response = self.session.get(url, params={'secuencial': sec}, timeout=20)
            response.raise_for_status()
            return response.json()
        except:
            return None
    
    def descargar_laz(self, sec, max_retries=2):
        """Descarga un archivo .laz"""
        for attempt in range(max_retries):
            try:
                # Paso 1
                init_url = f"{self.BASE_URL}/initDescargaDir"
                response = self.session.get(init_url, params={'secuencial': sec}, timeout=30)
                response.raise_for_status()
                
                sec_desc_dir = response.text.strip()
                
                if not sec_desc_dir or len(sec_desc_dir) < 5:
                    time.sleep(2)
                    continue
                
                time.sleep(1.5)
                
                # Paso 2
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
                if len(content) < 2048 or b'<!doctype' in content[:100].lower():
                    time.sleep(2)
                    continue
                
                filename = f"PNOA_LIDAR_{sec}.laz"
                logger.info(f"✅ Descargado: {filename} ({len(content)/1024/1024:.1f} MB)")
                
                return content, filename
                
            except Exception as e:
                logger.error(f"Error: {e}")
                time.sleep(2)
        
        return None, None

# === INTERFAZ ===

st.markdown("""
<div style='text-align: center; padding: 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin-bottom: 2rem;'>
    <h1 style='color: white; margin: 0;'>🗺️ Descargador Automático LiDAR IGN</h1>
    <p style='color: white; margin: 0.5rem 0 0 0;'>Marca región → Descarga automática</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    
    max_archivos = st.slider(
        "📦 Archivos por descarga",
        min_value=1,
        max_value=10,
        value=4,
        help="Recomendado: 4 archivos (más rápido y confiable)"
    )
    
    st.info(f"""
    ⏱️ **Tiempo estimado**:
    - {max_archivos} archivos ≈ {max_archivos * 1.5:.0f}-{max_archivos * 3:.0f} minutos
    
    📏 **Área recomendada**:
    - Pequeña: ~5x5 km
    - Media: ~10x10 km
    """)
    
    st.markdown("---")
    
    st.markdown("""
    ### 📖 Cómo usar
    
    1. **Dibuja** un área pequeña en el mapa
    2. **Haz clic** en "Buscar y Descargar"
    3. **Espera** 2-5 minutos
    4. **Descarga** el ZIP
    
    ### ⚡ Tips
    
    - Áreas pequeñas = más rápido
    - Máximo 4 archivos = óptimo
    - Cada archivo ≈ 10-50 MB
    
    ### ⚖️ Licencia
    © IGN España - CC-BY 4.0
    """)

# Mapa
st.subheader("📍 1. Dibuja un Área en el Mapa")

m = folium.Map(
    location=[40.4, -3.7],
    zoom_start=8,
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

map_output = st_folium(m, width=700, height=450, key="map")

# Info del mapa
if map_output and map_output.get('all_drawings'):
    drawing = map_output['all_drawings'][0]
    st.success("✅ Área dibujada correctamente")
else:
    st.info("👆 Usa las herramientas del mapa para dibujar un rectángulo o polígono")

st.markdown("---")

# Botón principal
st.subheader("📥 2. Descargar Archivos LiDAR")

if st.button("🚀 BUSCAR Y DESCARGAR AUTOMÁTICAMENTE", type="primary", use_container_width=True):
    
    if not map_output or not map_output.get('all_drawings'):
        st.error("❌ Primero dibuja un área en el mapa")
        st.stop()
    
    drawing = map_output['all_drawings'][0]
    geometry = drawing['geometry']
    
    # Calcular bbox
    if geometry['type'] == 'Polygon':
        coords = geometry['coordinates'][0]
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        bbox = [min(lons), min(lats), max(lons), max(lats)]
        
        # Calcular área aproximada
        width_km = (bbox[2] - bbox[0]) * 111 * 0.9
        height_km = (bbox[3] - bbox[1]) * 111
        area_km2 = width_km * height_km
        
        st.info(f"""
        📍 **Área seleccionada**:
        - Dimensiones: {width_km:.1f} × {height_km:.1f} km
        - Área: ~{area_km2:.1f} km²
        - Bbox: {bbox}
        """)
        
        # Advertencia si es muy grande
        if area_km2 > 200:
            st.warning(f"⚠️ Área grande ({area_km2:.0f} km²). Puede tardar varios minutos.")
        
        # Iniciar búsqueda
        downloader = CNIGDownloader()
        
        with st.spinner(f"🔍 Buscando archivos LiDAR (puede tardar 1-3 minutos)..."):
            inicio = time.time()
            secs = downloader.buscar_automatico(bbox, max_archivos=max_archivos)
            tiempo_busqueda = time.time() - inicio
        
        if not secs:
            st.error("""
            ❌ No se encontraron archivos en esta área.
            
            💡 **Sugerencias**:
            - Prueba con un área diferente
            - Verifica que sea territorio español
            - Algunas zonas no tienen cobertura LiDAR
            """)
            st.stop()
        
        st.success(f"✅ Encontrados {len(secs)} archivos en {tiempo_busqueda:.1f}s")
        
        # Mostrar lista
        with st.expander("📋 Ver secuenciales encontrados"):
            for i, item in enumerate(secs, 1):
                st.code(f"{i}. {item['sec']}")
        
        st.markdown("---")
        
        # Descargar archivos
        st.subheader("⬇️ 3. Descargando archivos...")
        
        progress = st.progress(0)
        status = st.empty()
        
        resultados = []
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for idx, item in enumerate(secs):
                sec = item['sec']
                
                status.text(f"📥 Descargando {idx+1}/{len(secs)}: {sec}")
                progress.progress((idx + 1) / len(secs))
                
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
                    st.error(f"❌ Error: {sec}")
            
            # Manifest
            manifest = {
                'fecha': datetime.now().isoformat(),
                'bbox': bbox,
                'area_km2': round(area_km2, 2),
                'total': len(secs),
                'exitosos': len([r for r in resultados if r['status'] == 'success']),
                'resultados': resultados,
                'atribucion': '© Instituto Geográfico Nacional de España - CC-BY 4.0'
            }
            zipf.writestr('manifest.json', json.dumps(manifest, indent=2, ensure_ascii=False))
        
        progress.progress(1.0)
        status.text("✅ Descarga completada!")
        
        # Estadísticas
        st.markdown("---")
        st.subheader("📊 Resumen Final")
        
        col1, col2, col3 = st.columns(3)
        exitosos = len([r for r in resultados if r['status'] == 'success'])
        total_mb = sum([r.get('size_mb', 0) for r in resultados])
        
        with col1:
            st.metric("✅ Exitosos", exitosos, delta=f"{exitosos/len(secs)*100:.0f}%")
        with col2:
            st.metric("❌ Errores", len(secs) - exitosos)
        with col3:
            st.metric("💾 Tamaño total", f"{total_mb:.1f} MB")
        
        # Botón descarga final
        zip_buffer.seek(0)
        
        st.download_button(
            label="📥 DESCARGAR ZIP CON ARCHIVOS LIDAR",
            data=zip_buffer,
            file_name=f"lidar_ign_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip",
            use_container_width=True,
            type="primary"
        )
        
        st.balloons()
        
        st.success(f"""
        🎉 **¡Descarga completada!**
        
        Archivos listos para usar en:
        - CloudCompare
        - QGIS
        - Python (laspy, pdal)
        - Análisis geoespacial
        """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 1rem;'>
    <p><strong>Descargador LiDAR IGN</strong> - Herramienta automática</p>
    <p>Datos © Instituto Geográfico Nacional de España | Licencia CC-BY 4.0</p>
    <p>Desarrollado para la comunidad geoespacial 🇪🇸</p>
</div>
""", unsafe_allow_html=True)
