import ee

def process_s1_image(image: ee.Image) -> ee.Image:
    """Helper function for mapping over the S1 collection."""
    # Spatial smoothing to kill speckle
    smoothed = image.select('VH').focal_median(radius=30, units='meters')
    
    # Invert VH (Deepest water becomes highest value)
    vh_inv = smoothed.multiply(-1).rename('VH_inv')
    
    # Stamp the Day of Year
    doy = ee.Image.constant(image.date().getRelative('day', 'year')).rename('DOY').toInt()
    
    return image.addBands([vh_inv, doy])

def get_transplanting_doy(region: ee.FeatureCollection | ee.Geometry, year: int) -> ee.Image:
    """
    Calculates the Day of Year (DOY) of minimum VH backscatter (maximum water) 
    for every pixel in the region during the Kharif window.
    """
    start_date = f'{year}-06-15'
    end_date = f'{year}-08-31'

    s1_kharif = (ee.ImageCollection('COPERNICUS/S1_GRD')
                 .filterBounds(region)
                 .filterDate(start_date, end_date)
                 .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
                 .filter(ee.Filter.eq('instrumentMode', 'IW'))
                 .filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING')))

    processed_collection = s1_kharif.map(process_s1_image)

    # Extract the DOY of the maximum inverted VH (the deepest dip)
    return processed_collection.qualityMosaic('VH_inv').select('DOY').clip(region)