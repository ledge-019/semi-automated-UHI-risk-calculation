import os
import matplotlib.pyplot as plt
import os
import pystac_client
import rioxarray as rxr
import xarray as xr
from odc.stac import configure_s3_access, stac_load

if 'COLAB_RELEASE_TAG' in os.environ:
    environment = 'colab'
    if os.environ.get('VERTEX_PRODUCT') == 'COLAB_ENTERPRISE':
        environment = 'colab_enterprise'
else:
    environment = 'local'

print(f'Environment: {environment}')

latitude = 14.64
longitude = 121.04
year = 2025

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

collections = catalog.get_collections()
PHL_col = catalog.get_collection("PHL")

search = catalog.search(
    collections=['PHL'],
    bbox=bbox,
    datetime=f'{year}'
)

for child in PHL_col.get_children():
    print(f"Child ID: {child.id} | Type: {type(child)}")

child_collection = PHL_col.get_child("PHL-Age and Sex Structures")

if child_collection is not None:
    print("Found child:", child_collection.id)
else:
    print("Child ID not found.")



items = child_collection.get_item('Philippines, Age and Sex Structures in 2026 at 100m')

ds = stac_load(
    items,
    bands=['red', 'green', 'blue', 'nir'],
    resolution=10,
    crs='utm',
    bbox=bbox,
    chunks={},  # <-- use Dask
    groupby='solar_day',
)