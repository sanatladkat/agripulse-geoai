# 🌾 Agri-Pulse: Geospatial Decision Intelligence System

> **Research Prototype:** A satellite-driven decision system that converts SAR + optical + rainfall data into real-time agricultural risk signals for supply chain planning.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.103.0-009688)
![Streamlit](https://img.shields.io/badge/Streamlit-1.26.0-FF4B4B)
![Google Earth Engine](https://img.shields.io/badge/Google_Earth_Engine-Cloud-green)

---

## 🎥 Demo

![Demo](demo.gif)

---

## 🎯 Problem

In monsoon-dependent agricultural regions, **2–3 week delays in paddy transplanting** directly impact:

* Procurement scheduling
* Milling operations
* Storage logistics
* Insurance risk models

Traditional systems rely on **delayed, coarse, survey-based reporting**.

Agri-Pulse replaces this with **near-real-time satellite-derived phenology intelligence**.

---

## 🧠 What This System Does

For any district and year, the system:

* Detects **paddy transplanting Day-of-Year (DOY)** from satellite data
* Computes **delay vs historical baseline**
* Quantifies **spatial uncertainty (heterogeneity of farming behavior)**
* Fuses rainfall anomalies into a **risk scoring engine (0–100)**
* Outputs **actionable operational recommendations**

---

## 🏗️ Architecture

```text
Sentinel-1 SAR + Sentinel-2 Optical + NASA GPM Rainfall
                │
                ▼
     Google Earth Engine Pipeline
 (masking + temporal smoothing + export)
                │
                ▼
   Cloud-Optimized GeoTIFF + Metadata
                │
                ▼
        FastAPI Decision Engine
 (risk scoring + anomaly detection)
                │
                ▼
        Streamlit Dashboard UI
 (interactive map + pixel inspector)
```

---

## 🔬 Core Engineering Design

### 1. Phenology Detection (Satellite Layer)

* **Sentinel-2 optical**

  * Cropland masking using NDVI + slope constraints
* **Sentinel-1 SAR**

  * VH backscatter used to detect flooding / transplanting window
  * Temporal smoothing (noise reduction across monsoon season)

**Output:** Field-level transplanting DOY raster

---

### 2. Risk Engine (Backend Logic)

FastAPI computes:

* **Delay anomaly**

  * deviation from historical median DOY
* **Z-scores**

  * phenology + rainfall deviations
* **Spatial uncertainty**

  * standard deviation of DOY across fields
* **Risk score (0–100)**

Simple weighting model:

* Delay anomaly → primary driver
* Rainfall deficit → secondary driver
* Spatial heterogeneity → uncertainty penalty

---

### 3. O(1) Pixel Query System

Instead of loading full rasters into memory:

```python
window = rasterio.windows.Window(col, row, 1, 1)
pixel_value = src.read(1, window=window)[0, 0]
```

**Result:**

* Constant-time spatial lookup
* No full raster decoding
* Enables interactive map inspection

---

### 4. Frontend (Streamlit)

* Folium-based interactive satellite map
* Click-to-inspect pixel DOY
* Risk dashboard (score + drivers + explanation)
* Year-over-year comparison mode

---

## 📊 API Output Example

```json
{
  "district": "Bhandara",
  "year": 2025,
  "median_doy": 212,
  "spatial_uncertainty_days": 9.4,
  "risk_engine": {
    "score": 82,
    "classification": "Severe",
    "drivers": [
      "Phenological Delay",
      "Precipitation Deficit"
    ],
    "recommended_action": "Adjust procurement and storage planning immediately."
  }
}
```

---

## 📂 Repository Structure

```text
src/
├── api/
│   └── main.py              # FastAPI risk engine
├── frontend/
│   └── app.py               # Streamlit dashboard
├── gee_core/
│   ├── sar_phenology.py     # Sentinel-1 processing
│   ├── optical_masking.py   # Sentinel-2 masking
│   └── precipitation.py     # Rainfall integration
├── batch_export.py          # GEE pipeline runner
data/
└── cache/                   # GeoTIFF + metadata (ignored)
```

---

## ⚙️ Run Locally

```bash
# environment
conda env create -f environment.yml
conda activate agripulse_env

# backend
uvicorn src.api.main:app --reload

# frontend
streamlit run src.frontend.app.py
```

---

## 🔭 Future Improvements

* Replace Folium with **Deck.gl vector tiles** for scalability
* Migrate storage to **PostGIS / Cloud storage**
* Extend model to **multi-crop phenology (wheat, sugarcane)**
* Introduce probabilistic risk scoring (Bayesian update layer)
