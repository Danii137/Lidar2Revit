"""
Descargador LiDAR IGN - Con API Proxy
Tu propia API hace las descargas
"""

import streamlit as st
import requests
import zipfile
import io
from datetime import datetime

st.set_page_config(page_title="🗺️ LiDAR IGN", layout="wide")

# ⚠️ CAMBIA ESTA URL POR LA DE TU API DESPLEGADA
API_URL = "https://tu-api-proxy.railway.app"  # ← CAMBIAR AQUÍ

st.title("🗺️ Descargador LiDAR IGN")
st.success(f"✅ API Proxy: {API_URL}")

SECUENCIALES = ["11123726", "11123727", "11123728", "11123729"]

st.subheader("Selecciona archivos")

seleccionados = []
for idx, sec in enumerate(SECUENCIALES):
    if st.checkbox(f"Archivo {idx+1}: {sec}", value=(idx < 2), key=sec):
        seleccionados.append(sec)

st.info(f"📦 {len(seleccionados)} seleccionados")

if st.button("🚀 DESCARGAR", type="primary", disabled=(len(seleccionados) == 0)):
    
    progress = st.progress(0)
    zip_buffer = io.BytesIO()
    resultados = []
    
    with zipfile.ZipFile(zip_buffer, 'w') as zipf:
        
        for idx, sec in enumerate(seleccionados):
            st.write(f"📥 Descargando {idx+1}/{len(seleccionados)}: {sec}")
            progress.progress((idx+1) / len(seleccionados))
            
            try:
                # Llamar a tu API
                response = requests.get(
                    f"{API_URL}/download/{sec}",
                    timeout=300,
                    stream=True
                )
                
                if response.status_code == 200:
                    content = response.content
                    filename = f"PNOA_{sec}.laz"
                    
                    zipf.writestr(filename, content)
                    size_mb = len(content) / 1024 / 1024
                    
                    resultados.append({'sec': sec, 'status': 'success', 'size_mb': size_mb})
                    st.success(f"✅ {filename} ({size_mb:.1f} MB)")
                else:
                    resultados.append({'sec': sec, 'status': 'error'})
                    st.error(f"❌ Error {response.status_code}")
                    
            except Exception as e:
                resultados.append({'sec': sec, 'status': 'error'})
                st.error(f"❌ {sec}: {e}")
    
    exitosos = len([r for r in resultados if r['status'] == 'success'])
    
    if exitosos > 0:
        zip_buffer.seek(0)
        
        st.download_button(
            "📥 DESCARGAR ZIP",
            data=zip_buffer,
            file_name=f"lidar_{datetime.now().strftime('%Y%m%d')}.zip",
            mime="application/zip"
        )
        
        st.balloons()
        st.success(f"🎉 {exitosos} archivos descargados!")
    else:
        st.error("❌ No se descargó ningún archivo")

st.markdown("---")
st.info(f"""
### 🔧 Configuración

Tu API debe estar desplegada en: **{API_URL}**

Si no tienes API desplegada:
1. Copia `proxy_api.py` y `requirements_api.txt`
2. Despliega en Railway.app (gratis)
3. Actualiza la variable `API_URL` arriba
""")
