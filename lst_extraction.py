import ee 
import geemap

ee.Authenticate(force=True)

# insert your project ID
project_id = None 
if project_id is None:
    proj_id = input("Please input your Project ID: ")
    print(f"Project ID {proj_id} retrieved")

else:
    print("Project ID already defined.")

ee.Initialize(project=proj_id) 

HPSCGS_ADM3 = ee.FeatureCollection('projects/earthengine-legacy/assets/projects/sat-io/open-datas' \
'ets/geoboundaries/HPSCGS-ADM3')

city = 'Quezon City'

filteredFc = HPSCGS_ADM3.filter(ee.Filter.inList('shapeName', [city]))
studyArea = filteredFc.geometry()

m = geemap.Map(center=[40,-100], zoom=4)
m.addLayer(studyArea, {}, 'Study Area')
m.centerObject(studyArea, 6)

list_dates = [{'analysisStart': '2026-03-01', 'analysisEnd': '2026-05-31'}]

# 3. Apply scaling factors to convert digital numbers to physical values
def applyImageScaling(image):

    # Scale optical bands (SR_B) to reflectance values
    opticalScaled = image.select('SR_B.').multiply(0.0000275).add(-0.2)

    # Scale thermal bands (ST_B*) to temperature values in Kelvin
    thermalScaled = image.select('ST_B.*').multiply(0.00341802).add(149.0)

    # Replace original bands with scaled bands
    return image.addBands(opticalScaled, None, True) \
    .addBands(thermalScaled, None, True)


# 4. Function to mask clouds and cloud shadows using the QA_PIXEL band
def applyCloudMask(imageCollection):

    # Define bit masks for cloud shadow (bit 3) and cloud (bit 5)
    cloudShadowMaskBit = (1 << 3)
    cloudMaskBit = (1 << 5)

    # Select the quality assessment band
    qualityAssessment = imageCollection.select('QA_PIXEL')

    # Create mask where both cloud and cloud shadow bits are 0 (clear conditions)
    clearSkyMask = qualityAssessment.bitwiseAnd(cloudShadowMaskBit).eq(0) \
    .And(qualityAssessment.bitwiseAnd(cloudMaskBit).eq(0))

    # Apply the mask to the image
    return imageCollection.updateMask(clearSkyMask)

def clip(image):
    clippedImage = image.clip(studyArea)
    return clippedImage



from pathlib import Path

# checking if the directory demo_folder 
# exist or not.
saved_path = 'raw'
out_dir = Path(saved_path)
out_dir.mkdir(exist_ok=True)

# 5. Filter, scale, and mask the Landsat 8 collection

imgs_list = []

for dict in list_dates:

    analysisStart = dict.get('analysisStart')
    analysisEnd = dict.get('analysisEnd')
    landsatCollection = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
    .filterDate(analysisStart, analysisEnd)  \
    .map(clip) \
    .map(applyImageScaling) \
    .map(applyCloudMask)

    compositeImage = landsatCollection.median()
    compositeImage = compositeImage.set({'analysisStart':analysisStart, 'analysisEnd':analysisEnd})
    imgs_list.append(compositeImage)


# 5. Filter, scale, and mask the Landsat 8 collection

imgs_list = []

for dict in list_dates:

    analysisStart = dict.get('analysisStart')
    analysisEnd = dict.get('analysisEnd')
    landsatCollection = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
    .filterDate(analysisStart, analysisEnd)  \
    .map(clip) \
    .map(applyImageScaling) \
    .map(applyCloudMask)

    compositeImage = landsatCollection.median()
    compositeImage = compositeImage.set({'analysisStart':analysisStart, 'analysisEnd':analysisEnd})
    imgs_list.append(compositeImage)


LST_list = []

# 8. Calculate Normalized Difference Vegetation Index (NDVI)

# NDVI = (NIR - Red) / (NIR + Red) | Landsat 8: NIR = Band5, Red = Band4
for compositeImage in imgs_list:

    start = compositeImage.get('analysisStart').getInfo()
    end = compositeImage.get('analysisEnd').getInfo()

    lst_filename = out_dir / Path(f'LST_{start}To{end}_{city}')
    print(lst_filename)


# 5. Filter, scale, and mask the Landsat 8 collection

imgs_list = []

for dict in list_dates:

    analysisStart = dict.get('analysisStart')
    analysisEnd = dict.get('analysisEnd')
    landsatCollection = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
    .filterDate(analysisStart, analysisEnd)  \
    .map(clip) \
    .map(applyImageScaling) \
    .map(applyCloudMask)

    compositeImage = landsatCollection.median()
    compositeImage = compositeImage.set({'analysisStart':analysisStart, 'analysisEnd':analysisEnd})
    imgs_list.append(compositeImage)


LST_list = []

# 8. Calculate Normalized Difference Vegetation Index (NDVI)

# NDVI = (NIR - Red) / (NIR + Red) | Landsat 8: NIR = Band5, Red = Band4
for compositeImage in imgs_list:

    start = compositeImage.get('analysisStart').getInfo()
    end = compositeImage.get('analysisEnd').getInfo()

    lst_filename = out_dir / Path(f'LST_{start}_To_{end}_{city}.tif')
    if not lst_filename.exists():

        vegetationIndex = compositeImage.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI')
        m.addLayer(vegetationIndex, {'min': -1, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'Vegetation Index (NDVI)', False)

        # 9. Calculate statistics for NDVI to establish range for vegetation fraction
        minVegetationIndex = ee.Number(vegetationIndex.reduceRegion(
        reducer=ee.Reducer.min(),
        geometry=studyArea,
        scale=30,
        maxPixels=1e9
        ).values().get(0))

        maxVegetationIndex = ee.Number(vegetationIndex.reduceRegion(
        reducer=ee.Reducer.max(),
        geometry=studyArea,
        scale=30,
        maxPixels=1e9
        ).values().get(0))

        # 10. Calculate Fraction of Vegetation (FV) using normalized NDVI values
        vegetationFraction = vegetationIndex \
        .subtract(minVegetationIndex) \
        .divide(maxVegetationIndex.subtract(minVegetationIndex)) \
        .pow(ee.Number(2)) \
        .rename('FV')

        # 11. Calculate Emissivity (EM) based on vegetation fraction

        # More vegetation = higher emissivity (closer to 0.99)

        surfaceEmissivity = vegetationFraction \
        .multiply(ee.Number(0.004)) \
        .add(ee.Number(0.986)) \
        .rename('EM')

        # 12. Select thermal band (Band 10) for temperature calculation
        thermalBand = compositeImage.select('ST_B10').rename('thermal')

        # 13. Calculate Land Surface Temperature (LST) using emissivity correction

        # Formula: LST = (BT / (1 + (λ * (BT / ρ) * ln(ε)))) - 273.15

        # Where λ = wavelength (11.5μm), ρ = h*c/σ (14380 μm·K), BT = brightness temperature

        landSurfaceTemp = thermalBand.expression(
        '(brightnessTemp / (1 + ((11.5 * (brightnessTemp / 14380)) * log(emissivity)))) - 273.15',
        {
            'brightnessTemp': thermalBand.select('thermal'), 
            'emissivity': surfaceEmissivity                 
        }
        ).rename('LST')
        
        LST_list.append(landSurfaceTemp)

        geemap.download_ee_image(landSurfaceTemp, crs = 'EPSG:32651', region = studyArea, filename = lst_filename, scale = 100)

        