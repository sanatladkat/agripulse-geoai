import os
import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import rasterio
from rasterio.enums import Resampling
import numpy as np

# --- PATH & CONFIG ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
API_BASE_URL = st.secrets.get("API_URL", "http://127.0.0.1:8000") if os.path.exists(os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")) else "http://127.0.0.1:8000"

DOY_EARLY_MIN, DOY_EARLY_MAX = 166, 196
DOY_LATE_MIN, DOY_LATE_MAX = 197, 222
DOY_DELAY_MIN, DOY_DELAY_MAX = 223, 243

def classify_doy(val):
    if val == 0: return "No Data", "gray"
    if DOY_EARLY_MIN <= val <= DOY_EARLY_MAX: return "Early/Normal", "#1a9641"
    if DOY_LATE_MIN <= val <= DOY_LATE_MAX: return "Late", "#d9b300"
    if DOY_DELAY_MIN <= val <= DOY_DELAY_MAX: return "Severely Delayed", "#d7191c"
    return "Out of Range", "gray"

def render_map(district, year, key="map"):
    m = folium.Map(tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')
    tif_path = os.path.join(CACHE_DIR, f"{district}_Paddy_Transplanting_DOY_{year}.tif")
    try:
        with rasterio.open(tif_path) as src:
            bounds = src.bounds
            h, w = int(src.height / 10), int(src.width / 10)
            arr = src.read(1, out_shape=(h, w), resampling=Resampling.nearest)
            img_rgba = np.zeros((h, w, 4), dtype=np.uint8)
            img_rgba[(arr >= DOY_EARLY_MIN) & (arr <= DOY_EARLY_MAX)] = [26, 150, 65, 200]
            img_rgba[(arr >= DOY_LATE_MIN) & (arr <= DOY_LATE_MAX)] = [255, 255, 191, 200]
            img_rgba[(arr >= DOY_DELAY_MIN) & (arr <= DOY_DELAY_MAX)] = [215, 25, 28, 200]
            if src.nodata is not None: img_rgba[arr == src.nodata] = [0, 0, 0, 0]
            img_rgba[arr == 0] = [0, 0, 0, 0]
            
            bounds_list = [[bounds.bottom, bounds.left], [bounds.top, bounds.right]]
            folium.raster_layers.ImageOverlay(image=img_rgba, bounds=bounds_list).add_to(m)
            m.fit_bounds(bounds_list)
    except Exception:
        pass
    return st_folium(m, width="100%", height=400, key=key)

st.set_page_config(page_title="Agri-Pulse | Decision Engine", layout="wide")
st.title("🌾 Agri-Pulse: Phenology Decision Engine")

with st.sidebar:
    st.header("Controls")
    mode = st.radio("Analysis Mode", ["Single Year Insight", "Year-over-Year Comparison"])
    selected_district = st.selectbox("District", ["Bhandara", "Gondia", "Gadchiroli"])
    
    if mode == "Single Year Insight":
        selected_year = st.slider("Harvest Year", 2021, 2025, 2025)
    else:
        y1 = st.slider("Baseline Year (A)", 2021, 2025, 2022)
        y2 = st.slider("Comparison Year (B)", 2021, 2025, 2023)

@st.cache_data(ttl=600)
def fetch_stats(district, year):
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/phenology/stats?district={district}&year={year}")
        return response.status_code, response.json()
    except Exception:
        return 503, {"detail": "API unreachable."}

if mode == "Single Year Insight":
    status_code, data = fetch_stats(selected_district, selected_year)
    
    if status_code == 200:
        engine = data['decision_engine']
        
        # --- 1. DECISION SUMMARY CARD ---
        st.markdown("### 🧠 Decision Summary")
        card_color = "success" if engine['risk_classification'] == "Low" else "warning" if engine['risk_classification'] == "Moderate" else "error"
        
        getattr(st, card_color)(f"""
        **Risk Level:** {engine['risk_classification']} ({engine['risk_score']}/100) — *{selected_district} is currently in the {engine['risk_percentile']}th percentile for regional delay risk.* **Recommended Action:** {engine['recommended_action']}  
        **System Confidence:** {engine['confidence']} *(based on spatial signal clarity)*
        """)
        
        # --- 2. EXPLAINABILITY PANEL ---
        with st.expander("🔍 Why this alert? (Explainability Details)"):
            st.write(engine['explanation'])
            ec1, ec2, ec3 = st.columns(3)
            ec1.metric("Transplanting Delay (Z-Score)", f"{engine['z_scores']['delay']} σ")
            ec2.metric("Rainfall Deficit (Z-Score)", f"{engine['z_scores']['rainfall']} σ")
            ec3.metric("Spatial Volatility", f"±{data['spatial_uncertainty_days']} days")
            st.caption(f"Primary Drivers Detected: {', '.join(engine['drivers'])}")
            
        st.markdown("---")
        
        # --- 3. CORE METRICS ---
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Paddy Area", f"{data['total_paddy_area_ha']:,.0f} Ha")
        
        yoy_delta = data.get('yoy_delta_days')
        delta_label = f"{yoy_delta:+} Days vs Last Year" if yoy_delta is not None else f"{data['delay_anomaly_days']:+} Days vs Avg"
        c2.metric("Median DOY", f"Day {data['median_doy']}", delta=delta_label, delta_color="inverse")
        
        c3.metric("Rainfall", f"{data['weather']['total_rainfall_mm']} mm", delta=f"{data['weather']['rainfall_anomaly_mm']} mm vs Avg", delta_color="normal")
        c4.metric("Severely Delayed Area", f"{data['distribution']['delayed']}%", delta="High Risk Exposure", delta_color="inverse")
        
        st.markdown("---")

        # --- 4. MAP & CHART ---
        mc, cc = st.columns([1.5, 1])
        with mc:
            st.subheader("Spatial Distribution")
            
            m = folium.Map(tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')
            tif_path = os.path.join(CACHE_DIR, f"{selected_district}_Paddy_Transplanting_DOY_{selected_year}.tif")
            
            try:
                with rasterio.open(tif_path) as src:
                    bounds = src.bounds
                    h, w = int(src.height / 10), int(src.width / 10)
                    arr = src.read(1, out_shape=(h, w), resampling=Resampling.nearest)
                    img_rgba = np.zeros((h, w, 4), dtype=np.uint8)
                    
                    img_rgba[(arr >= DOY_EARLY_MIN) & (arr <= DOY_EARLY_MAX)] = [26, 150, 65, 200]
                    img_rgba[(arr >= DOY_LATE_MIN) & (arr <= DOY_LATE_MAX)] = [255, 255, 191, 200]
                    img_rgba[(arr >= DOY_DELAY_MIN) & (arr <= DOY_DELAY_MAX)] = [215, 25, 28, 200]
                    
                    if src.nodata is not None: img_rgba[arr == src.nodata] = [0, 0, 0, 0]
                    img_rgba[arr == 0] = [0, 0, 0, 0]
                    
                    bounds_list = [[bounds.bottom, bounds.left], [bounds.top, bounds.right]]
                    folium.raster_layers.ImageOverlay(image=img_rgba, bounds=bounds_list, name='Transplanting Layer').add_to(m)
                    
                    legend_html = """
                    <div style="position: fixed; bottom: 50px; left: 50px; width: 150px; height: 110px; background-color: white; z-index:9999; font-size:14px; border:2px solid grey; padding: 10px; border-radius: 5px;">
                    <b>Transplanting</b><br>
                    <i style="background:#1a9641;width:12px;height:12px;display:inline-block;border-radius:50%;"></i> Early/Normal<br>
                    <i style="background:#ffffbf;width:12px;height:12px;display:inline-block;border-radius:50%;border:1px solid #ccc;"></i> Late<br>
                    <i style="background:#d7191c;width:12px;height:12px;display:inline-block;border-radius:50%;"></i> Delayed
                    </div>
                    """
                    m.get_root().html.add_child(folium.Element(legend_html))
                    m.fit_bounds(bounds_list)
            except Exception as e:
                st.error(f"Map rendering error: {e}")

            # --- CRITICAL FIX: Session State for Map Clicks ---
            if "last_clicked_coords" not in st.session_state:
                st.session_state.last_clicked_coords = None

            if st.session_state.last_clicked_coords:
                lat, lon = st.session_state.last_clicked_coords
                folium.Marker(
                    [lat, lon],
                    popup="Selected Pixel",
                    icon=folium.Icon(color="blue", icon="info-sign")
                ).add_to(m)

            map_data = st_folium(m, width="100%", height=500, key="main_map")
            
            if map_data and map_data.get("last_clicked"):
                new_lat = map_data["last_clicked"]["lat"]
                new_lon = map_data["last_clicked"]["lng"]
                
                if st.session_state.last_clicked_coords != (new_lat, new_lon):
                    st.session_state.last_clicked_coords = (new_lat, new_lon)
                    st.rerun()
            
            if st.session_state.last_clicked_coords:
                lat, lon = st.session_state.last_clicked_coords
                try:
                    with rasterio.open(tif_path) as src:
                        row, col = src.index(lon, lat)
                        if 0 <= row < src.height and 0 <= col < src.width:
                            window = rasterio.windows.Window(col, row, 1, 1)
                            pixel_value = src.read(1, window=window)[0, 0]
                            category, hex_color = classify_doy(pixel_value)
                            
                            st.markdown(f"""
                            <div style="padding: 10px; border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9; margin-top: 10px;">
                                <strong>📍 Inspector Location:</strong> {lat:.4f}, {lon:.4f} <br>
                                <strong>🌾 Transplanting DOY:</strong> {int(pixel_value) if pixel_value > 0 else 'N/A'} <br>
                                <strong>📊 Status:</strong> <span style="color: {hex_color}; font-weight: bold;">{category}</span>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.info("📍 Clicked outside the district bounds.")
                except Exception:
                    st.error("Failed to query the raster file.")
            else:
                st.caption("👆 Click anywhere on the map to drop a pin and query the raw satellite data.")

        with cc:
            st.subheader("Phenology Timeline")
            df = pd.DataFrame({'Period': ['Early/Normal', 'Late', 'Severely Delayed'], 'Percentage': [data['distribution']['early'], data['distribution']['late'], data['distribution']['delayed']]})
            fig = px.pie(df, values='Percentage', names='Period', hole=0.4, color='Period', color_discrete_map={'Early/Normal': '#1a9641', 'Late': '#ffffbf', 'Severely Delayed': '#d7191c'})
            fig.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.error(data.get('detail', 'Error loading data.'))

# --- YEAR OVER YEAR COMPARISON MODE ---
elif mode == "Year-over-Year Comparison":
    st.subheader(f"Temporal Shift Analysis: {y1} vs {y2}")
    
    s1, d1 = fetch_stats(selected_district, y1)
    s2, d2 = fetch_stats(selected_district, y2)
    
    if s1 == 200 and s2 == 200:
        colA, colB = st.columns(2)
        
        with colA:
            st.markdown(f"### {y1} Baseline")
            st.metric("Median Transplanting", f"Day {d1['median_doy']}")
            st.metric("Rainfall", f"{d1['weather']['total_rainfall_mm']} mm")
            st.metric("Risk Score", f"{d1['decision_engine']['risk_score']}/100")
            render_map(selected_district, y1, key="map_a")
            
        with colB:
            st.markdown(f"### {y2} Comparison")
            delta_doy = d2['median_doy'] - d1['median_doy']
            st.metric("Median Transplanting", f"Day {d2['median_doy']}", delta=f"{delta_doy:+} Days", delta_color="inverse")
            
            delta_rain = d2['weather']['total_rainfall_mm'] - d1['weather']['total_rainfall_mm']
            st.metric("Rainfall", f"{d2['weather']['total_rainfall_mm']} mm", delta=f"{delta_rain:+} mm", delta_color="normal")
            
            delta_risk = d2['decision_engine']['risk_score'] - d1['decision_engine']['risk_score']
            st.metric("Risk Score", f"{d2['decision_engine']['risk_score']}/100", delta=f"{delta_risk:+} pts", delta_color="inverse")
            render_map(selected_district, y2, key="map_b")
    else:
        st.error("Error loading comparison data. Ensure both years are processed in the cache.")