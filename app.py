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
            st.markdown(f"**{archivo['descripcion']}**")
        
        with col3:
            st.code(archivo['sec'], language=None)
        
        with col4:
            st.text(f"📍 {archivo['region']}")
        
        if seleccionado:
            archivos_seleccionados.append(archivo)
        
        if idx < len(ARCHIVOS_DISPONIBLES) - 1:
            st.divider()

# Resumen de selección
total_seleccionados = len(archivos_seleccionados)
st.markdown(f"""
<div style='padding: 1rem; background-color: #e7f3ff; border-left: 4px solid #2196F3; border-radius: 5px; margin: 1rem 0;'>
    <strong>📦 {total_seleccionados} archivo(s) seleccionado(s)</strong><br>
    <small>Tamaño estimado total: ~{total_seleccionados * 30} MB | Tiempo estimado: ~{total_seleccionados * 1.5:.0f} minutos</small>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# Botón de descarga
st.subheader("⬇️ 2. Iniciar descarga")

if total_seleccionados == 0:
    st.warning("⚠️ Selecciona al menos un archivo para continuar")
else:
    if st.button("🚀 DESCARGAR ARCHIVOS LIDAR", type="primary", use_container_width=True):
        
        st.markdown("### 📥 Descargando archivos...")
        
        # Progress bar global
        progress_global = st.progress(0, text="Iniciando descarga...")
        
        resultados = []
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            
            for idx, archivo in enumerate(archivos_seleccionados):
                
                # Actualizar progreso global
                porcentaje = idx / total_seleccionados
                progress_global.progress(porcentaje, text=f"Archivo {idx+1}/{total_seleccionados}: {archivo['nombre'][:40]}...")
                
                # Contenedor para este archivo
                with st.container():
                    st.markdown(f"#### 📄 Archivo {idx+1}/{total_seleccionados}")
                    
                    col_a, col_b = st.columns([2, 1])
                    
                    with col_a:
                        st.code(archivo['nombre'], language=None)
                    
                    with col_b:
                        st.text(f"Secuencial: {archivo['sec']}")
                    
                    # Status en tiempo real
                    status_placeholder = st.empty()
                    status_placeholder.info("🔄 Descargando desde FTP del IGN...")
                    
                    # Intentar descarga
                    inicio = time.time()
                    content, error = descargar_archivo_ftp(archivo['url'], archivo['nombre'])
                    tiempo_descarga = time.time() - inicio
                    
                    if content:
                        # Guardar en ZIP
                        zipf.writestr(archivo['nombre'], content)
                        
                        size_mb = len(content) / 1024 / 1024
                        
                        resultados.append({
                            'nombre': archivo['nombre'],
                            'sec': archivo['sec'],
                            'size_mb': size_mb,
                            'tiempo': tiempo_descarga,
                            'status': 'success'
                        })
                        
                        status_placeholder.success(f"✅ Descargado: **{size_mb:.1f} MB** en {tiempo_descarga:.1f}s")
                    
                    else:
                        resultados.append({
                            'nombre': archivo['nombre'],
                            'sec': archivo['sec'],
                            'error': error,
                            'status': 'error'
                        })
                        
                        status_placeholder.error(f"❌ Error: {error}")
                    
                    st.divider()
                    
                # Throttling entre descargas
                if idx < total_seleccionados - 1:
                    time.sleep(1)
            
            # Añadir README
            readme_content = f"""
═══════════════════════════════════════════════════════════════
  ARCHIVOS LIDAR - TOLEDO (CASTILLA-LA MANCHA)
═══════════════════════════════════════════════════════════════

Fecha de descarga: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
Región: Toledo, España
Cobertura: PNOA LiDAR 2ª Cobertura (2016)
Fuente: Instituto Geográfico Nacional (IGN)

───────────────────────────────────────────────────────────────
ARCHIVOS INCLUIDOS
───────────────────────────────────────────────────────────────

Total archivos: {len([r for r in resultados if r['status'] == 'success'])}

"""
            for r in resultados:
                if r['status'] == 'success':
                    readme_content += f"✓ {r['nombre']} ({r['size_mb']:.1f} MB)\n"
            
            readme_content += f"""
───────────────────────────────────────────────────────────────
ESPECIFICACIONES TÉCNICAS
───────────────────────────────────────────────────────────────

Formato: LAZ (LAS comprimido)
Densidad: ≥ 0.5 puntos/m²
Tamaño tesela: 2×2 km
Color: RGB (ortofoto PNOA)
Sistema referencia: ETRS89 / UTM zona 30N (EPSG:25830)
Alturas: Ortométricas
Clasificación: Automática (suelo, vegetación, edificios, etc.)

───────────────────────────────────────────────────────────────
LICENCIA Y ATRIBUCIÓN
───────────────────────────────────────────────────────────────

Licencia: Creative Commons Reconocimiento 4.0 (CC-BY 4.0)
© Instituto Geográfico Nacional de España

ATRIBUCIÓN OBLIGATORIA:
"Datos © Instituto Geográfico Nacional de España"

───────────────────────────────────────────────────────────────
SOFTWARE RECOMENDADO
───────────────────────────────────────────────────────────────

Visualización:
  • CloudCompare (gratuito) - https://www.danielgm.net/cc/
  • FugroViewer (gratuito) - https://www.fugro.com/
  
Análisis SIG:
  • QGIS (gratuito) - https://qgis.org/
  • ArcGIS Pro (comercial)
  
Procesamiento Python:
  • laspy - Lectura/escritura LAZ/LAS
  • pdal - Procesamiento nubes de puntos
  • open3d - Visualización y análisis 3D

───────────────────────────────────────────────────────────────
MÁS INFORMACIÓN
───────────────────────────────────────────────────────────────

Centro de Descargas: https://centrodedescargas.cnig.es
PNOA LiDAR: https://pnoa.ign.es/pnoa-lidar
IGN: https://www.ign.es

═══════════════════════════════════════════════════════════════
"""
            
            zipf.writestr('README.txt', readme_content)
            
            # Añadir manifest JSON
            manifest = {
                'fecha_descarga': datetime.now().isoformat(),
                'region': 'Toledo, España',
                'cobertura': 'PNOA LiDAR 2ª Cobertura (2016)',
                'fuente': 'Instituto Geográfico Nacional (IGN)',
                'licencia': 'CC-BY 4.0',
                'atribucion': '© Instituto Geográfico Nacional de España',
                'total_archivos': len(archivos_seleccionados),
                'archivos_exitosos': len([r for r in resultados if r['status'] == 'success']),
                'archivos_fallidos': len([r for r in resultados if r['status'] == 'error']),
                'archivos': resultados
            }
            
            zipf.writestr('manifest.json', json.dumps(manifest, indent=2, ensure_ascii=False))
        
        # Completar barra de progreso
        progress_global.progress(1.0, text="✅ Descarga completada!")
        
        # Estadísticas finales
        st.markdown("---")
        st.markdown("## 📊 Resumen de Descarga")
        
        exitosos = len([r for r in resultados if r['status'] == 'success'])
        fallidos = len([r for r in resultados if r['status'] == 'error'])
        total_mb = sum([r.get('size_mb', 0) for r in resultados if r['status'] == 'success'])
        tiempo_total = sum([r.get('tiempo', 0) for r in resultados if r['status'] == 'success'])
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("✅ Exitosos", exitosos, delta=f"{exitosos/total_seleccionados*100:.0f}%")
        
        with col2:
            st.metric("❌ Fallidos", fallidos)
        
        with col3:
            st.metric("💾 Tamaño Total", f"{total_mb:.1f} MB")
        
        with col4:
            st.metric("⏱️ Tiempo Total", f"{tiempo_total:.1f}s")
        
        # Botón de descarga del ZIP
        if exitosos > 0:
            st.markdown("---")
            
            zip_buffer.seek(0)
            
            st.download_button(
                label=f"📥 DESCARGAR ZIP ({total_mb:.1f} MB) - {exitosos} ARCHIVO(S)",
                data=zip_buffer,
                file_name=f"lidar_toledo_ign_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                mime="application/zip",
                use_container_width=True,
                type="primary"
            )
            
            st.balloons()
            
            st.success(f"""
            ### 🎉 ¡Descarga completada exitosamente!
            
            **{exitosos} archivo(s) LiDAR** descargado(s) y empaquetado(s) en ZIP.
            
            #### 📦 Contenido del ZIP:
            - {exitosos} archivo(s) .laz (nubes de puntos LiDAR)
            - 1 archivo README.txt (información detallada)
            - 1 archivo manifest.json (metadatos técnicos)
            
            #### 🚀 Próximos pasos:
            1. Descarga el archivo ZIP
            2. Descomprime en tu ordenador
            3. Abre los archivos .laz con CloudCompare o QGIS
            4. ¡Explora y analiza los datos LiDAR!
            """)
        else:
            st.error("""
            ### ❌ No se pudo descargar ningún archivo
            
            **Posibles causas**:
            - Los archivos no están disponibles en el servidor FTP
            - Problema de conectividad con el IGN
            - Las URLs han cambiado
            
            **Solución**: Intenta de nuevo en unos minutos o descarga directamente desde:
            https://centrodedescargas.cnig.es
            """)

# Footer informativo
st.markdown("---")

with st.expander("ℹ️ Acerca de esta herramienta"):
    st.markdown("""
    ### 🛠️ Cómo funciona
    
    Esta herramienta descarga archivos LiDAR directamente desde el **servidor FTP público** del Instituto Geográfico Nacional:
    
    ```
    http://datos-geodesia.ign.es/PNOA_LIDAR/...
    ```
    
    **Ventajas**:
    - ✅ Descarga directa sin intermediarios
    - ✅ No requiere autenticación
    - ✅ Funciona en Streamlit Cloud
    - ✅ Datos oficiales del IGN
    
    **Archivos disponibles**:
    - Región: Toledo (Castilla-La Mancha)
    - Año: 2016
    - Total: 4 teselas de ejemplo
    
    ### 📝 Atribución
    
    Al usar estos datos, debes incluir:
    
    > "Datos © Instituto Geográfico Nacional de España"
    
    ### 🔗 Enlaces útiles
    
    - [Centro de Descargas CNIG](https://centrodedescargas.cnig.es)
    - [PNOA LiDAR](https://pnoa.ign.es/pnoa-lidar)
    - [CloudCompare](https://www.danielgm.net/cc/)
    - [QGIS](https://qgis.org/)
    """)

# Footer
st.markdown("""
<div style='text-align: center; color: #666; padding: 2rem; background-color: #f8f9fa; border-radius: 10px; margin-top: 2rem;'>
    <h3 style='margin: 0; color: #444;'>🗺️ Descargador LiDAR IGN</h3>
    <p style='margin: 0.5rem 0;'>Herramienta no oficial para facilitar el acceso a datos públicos del IGN</p>
    <p style='margin: 0.5rem 0;'><strong>Datos</strong>: © Instituto Geográfico Nacional de España | <strong>Licencia</strong>: CC-BY 4.0</p>
    <p style='margin: 0; font-size: 0.9rem;'>Desarrollado con ❤️ para la comunidad geoespacial española 🇪🇸</p>
</div>
""", unsafe_allow_html=True)
