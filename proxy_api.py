"""
API Proxy para descargar archivos LiDAR del CNIG
Despliega en Railway/Render/Heroku
"""

from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import requests
import io
import time

app = Flask(__name__)
CORS(app)  # Permitir peticiones desde Streamlit Cloud

BASE_URL = "https://centrodedescargas.cnig.es/CentroDescargas"

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({'status': 'ok', 'service': 'CNIG LiDAR Proxy'})

@app.route('/download/<sec>', methods=['GET'])
def download_lidar(sec):
    """
    Descarga un archivo LiDAR dado su secuencial
    Ejemplo: GET /download/11123726
    """
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://centrodedescargas.cnig.es/CentroDescargas/',
        })
        
        # Paso 1: initDescargaDir
        init_url = f"{BASE_URL}/initDescargaDir"
        response = session.get(init_url, params={'secuencial': sec}, timeout=30)
        response.raise_for_status()
        
        sec_desc_dir = response.text.strip()
        
        # Parsear JSON si es necesario
        if sec_desc_dir.startswith('{'):
            import json
            data = json.loads(sec_desc_dir)
            sec_desc_dir = data.get('secuencialDescDir', sec_desc_dir)
        
        if not sec_desc_dir or len(sec_desc_dir) < 5:
            return jsonify({'error': 'secuencialDescDir inválido'}), 400
        
        time.sleep(2)
        
        # Paso 2: descargaDir
        download_url = f"{BASE_URL}/descargaDir"
        response = session.post(
            download_url,
            data={'secDescDirLA': sec_desc_dir},
            timeout=300,
            stream=True
        )
        response.raise_for_status()
        
        content = response.content
        
        # Validar
        if len(content) < 2048:
            return jsonify({'error': 'Archivo muy pequeño'}), 400
        
        if b'<!doctype' in content[:100].lower():
            return jsonify({'error': 'Respuesta HTML (error del servidor)'}), 400
        
        # Devolver archivo
        return send_file(
            io.BytesIO(content),
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name=f'PNOA_{sec}.laz'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/batch', methods=['POST'])
def batch_download():
    """
    Descarga múltiples archivos
    POST /batch
    Body: {"secuenciales": ["11123726", "11123727"]}
    """
    try:
        data = request.get_json()
        secs = data.get('secuenciales', [])
        
        if not secs:
            return jsonify({'error': 'No secuenciales provided'}), 400
        
        # Por ahora, devolver URLs de descarga individual
        urls = [f"{request.host_url}download/{sec}" for sec in secs]
        
        return jsonify({
            'secuenciales': secs,
            'download_urls': urls
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
