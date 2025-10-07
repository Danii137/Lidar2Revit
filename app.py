import streamlit as st
from streamlit_folium import st_folium
import folium
from shapely.geometry import shape, Polygon, mapping
from shapely.ops import unary_union
import geopandas as gpd
import io, json, requests, zipfile
from datetime import datetime

st.set_page_config(page_title="LiDAR 2ª cobertura · Downloader", layout="wide")
st.title("PNOA LiDAR 2ª cobertura (RGB) — v0.1")

st.markdown("1) Dibuja el AOI · 2) Sube **índice GeoJSON** con las teselas (campo `url`) · 3) Descarga")

# --- MAPA + DRAW ---
m = folium.Map(location=[40.3,-3.7], zoom_start=6, tiles="cartodbpositron")
draw = folium.plugins.Draw(export=False, draw_options={
    "polyline": False, "circle": False, "circlemarker": False,
    "rectangle": True, "polygon": True, "marker": False
})
draw.add_to(m)
out = st_folium(m, height=520, width=1000, returned_objects=["all_drawings"])

def get_aoi_geom(out):
    feats = out.get("all_drawings") or []
    if not feats: 
        return None
    geoms = [shape(f["geometry"]) for f in feats]
    return unary_union(geoms).buffer(0)

aoi = get_aoi_geom(out)
if not aoi:
    st.info("Dibuja un **rectángulo** o **polígono** con el área de interés.")
    st.stop()

st.success("AOI listo.")
with st.expander("Ver AOI GeoJSON"):
    st.code(json.dumps({"type":"Feature","geometry":mapping(aoi),"properties":{}}, ensure_ascii=False), language="json")

# --- ÍNDICE DE TESELAS ---
idx_file = st.file_uploader("Sube el **índice GeoJSON** de teselas LiDAR 2ª cobertura (con campo `url` al .LAZ)", type=["geojson","json"])
if not idx_file:
    st.warning("Falta el índice de teselas. Sube el GeoJSON (cada feature = tesela con `geometry` y `properties.url`).")
    st.stop()

gdf = gpd.read_file(idx_file)
if "url" not in gdf.columns:
    st.error("El GeoJSON no tiene columna `url`. Asegúrate de que cada tesela tenga `properties.url` con el enlace al .laz")
    st.stop()

# Asegura CRS métrico (asumimos ETRS89 / UTM 30N; si viene en 4326, reproyecta)
if gdf.crs is None:
    st.warning("Índice sin CRS. Asumiendo EPSG:4326…")
    gdf.set_crs(epsg=4326, inplace=True)

# Reproyecta AOI al CRS del índice para intersectar correctamente
aoi_gdf = gpd.GeoDataFrame(geometry=[aoi], crs="EPSG:4326")
if aoi_gdf.crs != gdf.crs:
    aoi_gdf = aoi_gdf.to_crs(gdf.crs)

# Intersección
sel = gdf[gdf.intersects(aoi_gdf.geometry.iloc[0])].copy()
st.write(f"Teselas encontradas: **{len(sel)}**")

if len(sel):
    st.dataframe(sel[["url"]].assign(area_m2=sel.geometry.area.round(2)).head(50))
    # Descargar todas en un ZIP en memoria
    if st.button("Descargar teselas seleccionadas (.laz) como ZIP"):
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for i, row in sel.iterrows():
                url = row["url"]
                try:
                    with requests.get(url, stream=True, timeout=180) as r:
                        r.raise_for_status()
                        # nombre de archivo desde URL
                        fname = url.split("/")[-1].split("?")[0] or f"tile_{i}.laz"
                        zf.writestr(fname, r.content)
                except Exception as e:
                    zf.writestr(f"ERROR_{i}.txt", f"{url}\n{repr(e)}")
        mem.seek(0)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(f"Descargar ZIP ({len(sel)} teselas)", data=mem.getvalue(),
                           file_name=f"pnoa_lidar_2c_{stamp}.zip", mime="application/zip")
