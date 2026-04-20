import ee

def get_robust_paddy_mask(region: ee.FeatureCollection | ee.Geometry, year: int) -> ee.Image:
    """
    Generates a boolean mask strictly isolating physical agricultural land
    that exhibited high vegetative growth during the Kharif season.
    """
    start_date = f'{year}-08-01'
    end_date = f'{year}-10-31'
    
    # 1. Optical Greenness (Peak NDVI > 0.6)
    s2_max_ndvi = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                   .filterBounds(region)
                   .filterDate(start_date, end_date)
                   .map(lambda img: img.normalizedDifference(['B8', 'B4']))
                   .max())
    green_mask = s2_max_ndvi.gt(0.6)

    # 2. ESA WorldCover Land Cover (Strictly Cropland = 40)
    worldcover = ee.ImageCollection("ESA/WorldCover/v200").first()
    crop_mask = worldcover.eq(40)

    # 3. SRTM Topography (Slope < 5 degrees)
    dem = ee.Image("USGS/SRTMGL1_003")
    slope = ee.Terrain.slope(dem)
    flat_mask = slope.lt(5)

    # Return the combined logical AND mask
    return green_mask.And(crop_mask).And(flat_mask)