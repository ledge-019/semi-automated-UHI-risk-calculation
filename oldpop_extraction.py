import os
import matplotlib.pyplot as plt
import pystac_client
import rioxarray as rxr
import xarray as xr
from odc.stac import configure_s3_access, stac_load, load
import geopandas as gpd
import requests
from pathlib import Path

country_abbrev = 'PHL'
country_full = 'Philippines'
latitude = 14.64
longitude = 121.04
year = 2026
resolution = 100

catalog = pystac_client.Client.open(
    'https://api.stac.worldpop.org')

# Configure settings for reading from Earth Search STAC
configure_s3_access(
    aws_unsigned=True,
)

# Define a small bounding box around the chosen point
km2deg = 1.0 / 111
x, y = (longitude, latitude)
r = 1 * km2deg  # radius in degrees
bbox = (x - r, y - r, x + r, y + r)

search = catalog.search(
    collections=['PHL'],
    bbox=bbox,
    query={'year': {'eq': 2026}, 
           'title': {"eq":f"{country_full}, Age and Sex Structures in {year} at {resolution}m"}}
)
items = search.item_collection()

bands = [
    'total_60_2026',
    'total_65_2026',
    'total_70_2026',
    'total_75_2026',
    'total_80_2026',
    'total_85_2026',
    'total_90_2026'
]


shp = gpd.read_file("quezon_city.gpkg")
out_dir = Path("worldpop_clipped")
out_dir.mkdir(exist_ok=True)

for band in bands:
    url = items[0].assets[band].href
    filename = Path(url).name
    temp_file = out_dir / filename
    clipped_file = out_dir / f"{band}_clipped.tif"
    print(f"\nProcessing {band}...")

    if not temp_file.exists():

        print("  Downloading...")
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with open(temp_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)



    raster = rxr.open_rasterio(
        temp_file,
        masked=True
    ).squeeze(drop=True)

    shp_raster_crs = shp.to_crs(raster.rio.crs)

    clipped = raster.rio.clip(
        shp_raster_crs.geometry,
        shp_raster_crs.crs,
        drop=True,
        from_disk=True
    )

    clipped.rio.to_raster(
        clipped_file,
        compress="deflate"
    )

    print(f"  Saved: {clipped_file}")


worldpop_path = "worldpop_clipped"

total_pop_old = None

for entry in os.scandir(worldpop_path):

    if entry.is_file() and 'total' in entry.name and entry.name.endswith('.tif'):

        raster = rxr.open_rasterio(
            entry,
            masked=True
        ).squeeze(drop=True)

        if total_pop_old is None:
            total_pop_old = raster.fillna(0)
        else:
            total_pop_old = total_pop_old + raster.fillna(0)

total_pop_old = total_pop_old.fillna(0)
total_pop_old.rio.to_raster(
    "total_population_old.tif"
)


