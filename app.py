# app.py — PNOA LiDAR 2ª cobertura · Downloader v0.1b
import io, json, re, time, zipfile
from datetime import datetime

import requests
import streamlit as st
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from streamlit_folium import st_folium
import folium

# --------- Config ---------
st.set_page_config(page_title="PNOA LiDAR 2ª — Downloader", layout="wide")
st.title("PNOA LiDAR 2ª cobertura (RGB) — Downloader v0.1b")

# --------- Helpers ---------
def get_aoi_geom(folium_out):
    feats = folium_out.get("all_drawings") or []
    if not feats:
        return None
    geoms = [shape(f["geometry"]) for f in feats]
    return unary_union(geoms).buffer(0)

def load_index_geojson(file) -> list:
    """Devuelve una lista de dicts: {'geom': shapely_geom, 'sec': str|None, 'url': str|None}"""
    data = json.load(file)
    feats = data.get("features", [])
    tiles = []
    for f in feats:
        props = f.get("properties", {}) or {}
        sec = props.get("sec")
        url = props.get("url")
        try:
            geom = shape(f.get("geometry"))
        except Exception:
            continue
        tiles.append({"geom": geom, "sec": (str(sec).strip() if sec else None), "url": (str(url).strip() if url else None)})
    return tiles

def download_cnig_laz_by_sec(sec: str, timeout_sec=240):
    """
    Flujo oficial del Centro de Descargas:
    1) GET initDescargaDir?secuencial=<sec>  -> {secuencialDescDir: "..."}
    2) POST descargaDir con secDescDirLA=<valor anterior> -> devuelve el .LAZ (binario)
    """
    s = requests.Session()
    r1 = s.get(
        "https://centrodedescargas.cnig.es/CentroDescargas/initDescargaDir",
        params={"secuencial": sec},
        timeout=30,
    )
    r1.raise_for_status()
    j = r1.json()
    sec_tmp = j.get("secuencialDescDir")
    if not sec_tmp:
        raise RuntimeError(f"No recibí 'secuencialDescDir' para sec={sec}. Respuesta: {j}")

    r2 = s.post(
        "https://centrodedescargas.cnig.es/CentroDescargas/descargaDir",
        data={"secDescDirLA": sec_tmp},
        timeout=timeout_sec,
        allow_redirects=True,
    )
    r2.raise_for_status()

    cd = r2.headers.get("Content-Disposition", "")
    m = re.search(r'filename="?([^";]+)"?', cd)
    fname = m.group(1) if m else f"{sec}.laz"
    content = r2.content
    if not content or len(content) < 1000:
        # Por si el servidor devuelve HTML/JSON de error en lugar del LAZ
        raise RuntimeError(f"Descarga sospechosa para sec={sec} (tamaño {len(content)} bytes).")
    return fname, content

# --------- UI: mapa + dibujo ---------
m = folium.Map(location=[40.3, -3.7], zoom_start=6, tiles="cartodbpositron")
draw = folium.plugins.Draw(
    export=False,
    draw_options={
        "polyline": False, "circle": False, "circlemarker": False,
        "rectangle": True, "polygon": True, "marker": False
    }
)
draw.add_to(m)
out = st_folium(m, height=520, width=1000, returned_objects=["all_drawings"])

aoi = get_aoi_geom(out)
if not aoi:
    st.info("Dibuja un **rectángulo** o **polígono** con el área de interés (AOI).")
    st.stop()

st.success("AOI listo.")
with st.expander("Ver AOI (GeoJSON)"):
    st.code(json.dumps({"type": "Feature", "geometry": mapping(aoi), "properties": {}}, ensure_ascii=False), language="json")

# --------- Cargar índice de teselas ---------
idx_file = st.file_uploader(
    "Sube tu **índice GeoJSON** (cada feature con `properties.sec` o `properties.url`)",
    type=["geojson", "json"]
)
if not idx_file:
    st.warning("Falta el índice de teselas. Sube el GeoJSON.")
    st.stop()

tiles = load_index_geojson(idx_file)
if not tiles:
    st.error("No se pudieron leer teselas del GeoJSON. Revisa `features[].geometry` y `properties`.")
    st.stop()

# --------- Intersección AOI ↔ teselas ---------
sel = [t for t in tiles if t["geom"].intersects(aoi)]
st.write(f"Teselas encontradas que intersectan el AOI: **{len(sel)}**")

if sel:
    # Tabla ligera
    preview = []
    for i, t in enumerate(sel[:50]):
        preview.append({
            "i": i,
            "sec": t["sec"] or "",
            "url": t["url"] or "",
            "area_m2_aprox": round(t["geom"].area * (111_000**2), 2) if t["geom"].geom_type in ("Polygon","MultiPolygon") else ""
        })
    st.dataframe(preview)

# --------- Descarga a ZIP ---------
if sel and st.button("Descargar teselas seleccionadas (.laz) como ZIP"):
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i, t in enumerate(sel):
            try:
                if t["sec"]:
                    fname, data = download_cnig_laz_by_sec(t["sec"])
                    zf.writestr(fname, data)
                elif t["url"]:
                    r = requests.get(t["url"], timeout=240, stream=True)
                    r.raise_for_status()
                    fname = t["url"].split("/")[-1].split("?")[0] or f"tile_{i}.laz"
                    zf.writestr(fname, r.content)
                else:
                    zf.writestr(f"ERROR_{i}.txt", "Ni 'sec' ni 'url' definidos en la tesela.")
                time.sleep(0.2)  # pequeño respiro para no saturar
            except Exception as e:
                zf.writestr(f"ERROR_{i}.txt", f"Fallo en tesela {i}: {repr(e)}")
    mem.seek(0)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.download_button(
        f"Descargar ZIP ({len(sel)} teselas)",
        data=mem.getvalue(),
        file_name=f"pnoa_lidar_2c_{stamp}.zip",
        mime="application/zip"
    )

st.divider()
st.caption("Consejo: empieza con 1–3 teselas para probar. Si ves ficheros ERROR_*.txt en el ZIP, pásame el mensaje y lo pulimos.")
