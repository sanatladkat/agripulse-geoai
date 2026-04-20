import ee
import argparse
import json
import os
from gee_core.optical_masking import get_robust_paddy_mask
from gee_core.sar_phenology import get_transplanting_doy
from gee_core.precipitation import get_kharif_rainfall

def main():
    parser = argparse.ArgumentParser(description="Agri-Pulse: GEE Batch Export Pipeline")
    parser.add_argument("--district", type=str, default="Bhandara")
    parser.add_argument("--years", nargs='+', type=int, default=[2021, 2022, 2023, 2024, 2025])
    args = parser.parse_args()

    # Initialize with your specific project ID
    ee.Initialize(project="gee-xplore")

    roi = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(ee.Filter.eq('ADM2_NAME', args.district))
    
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
    CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
    os.makedirs(CACHE_DIR, exist_ok=True)

    tasks = []
    for year in args.years:
        print(f"\n🔄 Preparing pipeline for {args.district} ({year})...")
        
        # --- A. GEOAI: MAP PROCESSING & EXPORT ---
        mask = get_robust_paddy_mask(roi, year)
        doy_map = get_transplanting_doy(roi, year).updateMask(mask)
        
        task_name = f"{args.district}_Paddy_Transplanting_DOY_{year}"
        task = ee.batch.Export.image.toDrive(
            image=doy_map,
            description=task_name,
            folder='AgriPulse_Cache',
            region=roi.geometry(),
            scale=10, 
            crs='EPSG:4326',
            maxPixels=1e10,
            fileFormat='GeoTIFF',
            formatOptions={'cloudOptimized': True}
        )
        task.start()
        tasks.append(task)
        print(f"✅ GEE Map Export Queued (Task ID: {task.id})")

        # --- B. WEATHER: NASA GPM RAINFALL EXTRACTION ---
        print(f"🌦️ Calculating NASA GPM rainfall...")
        total_rain_mm = get_kharif_rainfall(roi, year)
        
        # Statistical Baselines (Simulated for portfolio, usually queried from PostGIS)
        historical_avg_rain_mm = 850.0 
        historical_std_rain_mm = 180.0 # Standard deviation of historical rainfall
        
        metadata = {
            "year": year,
            "total_rainfall_mm": round(total_rain_mm, 1),
            "rainfall_anomaly_mm": round(total_rain_mm - historical_avg_rain_mm, 1),
            "historical_std_rain_mm": historical_std_rain_mm
        }
        
        meta_path = os.path.join(CACHE_DIR, f"{args.district}_metadata_{year}.json")
        with open(meta_path, 'w') as f:
            json.dump(metadata, f)
            
        print(f"✅ Metadata saved: {total_rain_mm:.1f} mm recorded.")

    print("\n🚀 All Map tasks submitted. Check status at: https://code.earthengine.google.com/tasks")

if __name__ == "__main__":
    main()