import ee

def get_kharif_rainfall(region: ee.FeatureCollection | ee.Geometry, year: int) -> float:
    """
    Calculates the total accumulated rainfall (mm) for the critical 
    transplanting window (June 1st to August 31st).
    Uses NASA GPM (IMERG V07) half-hourly data, aggregated to a season total.
    """
    start_date = f'{year}-06-01'
    end_date = f'{year}-08-31'
    
    # 1. Upgrade to V07 and use the new 'precipitation' band
    gpm = (ee.ImageCollection("NASA/GPM_L3/IMERG_V07")
           .filterBounds(region)
           .filterDate(start_date, end_date)
           .select('precipitation'))
    
    # 2. Convert rate (mm/hr) to depth (mm) for 30-minute intervals
    def compute_depth(img):
        return img.multiply(0.5).copyProperties(img, img.propertyNames())
        
    total_rainfall_img = gpm.map(compute_depth).sum()
    
    district_rainfall = total_rainfall_img.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=region.geometry(),
        scale=10000, 
        maxPixels=1e9
    )
    
    try:
        # 3. Fetch the corrected band name
        val = district_rainfall.get('precipitation').getInfo()
        return float(val) if val is not None else 0.0
    except Exception as e:
        print(f"⚠️ Error fetching precipitation data: {e}")
        return 0.0