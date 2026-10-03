import pystac_client
import rioxarray as rxr
import xarray as xr
from odc.stac import configure_s3_access, stac_load, load
import requests
from pathlib import Path
from rasterio.enums import Resampling
import numpy as np
import osmnx as ox
import os


# 1. POPULATION RASTER — ORIGINAL CRS

country_abbrev = 'PHL'
country_full = 'Philippines'
latitude = 14.64
longitude = 121.04
year = 2026
resolution = 100

saved_path = "raw"
out_dir = Path(saved_path)
out_dir.mkdir(exist_ok=True)

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
           'title': {"eq":f"{country_full}, Spatial Distribution of Population in {year} at {resolution}m"}}
)
items = search.item_collection()

url = items[0].assets['data'].href
filename = Path(url).name
temp_file = out_dir / filename
clipped_file = out_dir / f"{Path(filename).stem}_clipped.tif"
print(f"\nProcessing {filename}...")

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

print("\n===== ORIGINAL POPULATION =====")
print("CRS:", raster.rio.crs)
print("Resolution:", raster.rio.resolution())
print("Shape:", raster.shape)
print("Bounds:", raster.rio.bounds())

# 2. QUEZON CITY BOUNDARY

shp = ox.geocode_to_gdf(
    ["Quezon City, Philippines"]
)

print("\n===== GEOPACKAGE =====")
print("CRS:", shp.crs)

shp_raster_crs = shp.to_crs(raster.rio.crs)

# 3. CLIP POPULATION


pop_clipped = raster.rio.clip(
    shp_raster_crs.geometry,
    shp_raster_crs.crs,
    drop=True,
    from_disk=True
)

print("\n===== CLIPPED POPULATION =====")
print("CRS:", pop_clipped.rio.crs)
print("Resolution:", pop_clipped.rio.resolution())
print("Shape:", pop_clipped.shape)

pop_clipped.rio.to_raster(
    clipped_file,
    compress="deflate"
)

print(f"  Saved: {clipped_file}")



# 4. POPULATION → EPSG:32651, 100 × 100 m

pop_100m = pop_clipped.rio.reproject(
    "EPSG:32651",
    resolution=(100, 100),
    resampling=Resampling.nearest
)

print("\n===== POPULATION 100m =====")
print("CRS:", pop_100m.rio.crs)
print("Resolution:", pop_100m.rio.resolution())
print("Shape:", pop_100m.shape)
print("Bounds:", pop_100m.rio.bounds())

res_x, res_y = pop_100m.rio.resolution()

assert np.isclose(abs(res_x), 100)
assert np.isclose(abs(res_y), 100)

pixel_area_m2 = abs(res_x * res_y)
pixel_area_km2 = pixel_area_m2 / 1_000_000

print("Pixel area:", pixel_area_m2, "m²")
print("Pixel area:", pixel_area_km2, "km²")

# 5. TOTAL POPULATION DENSITY

pop_100m_calc = pop_100m.fillna(0)

pop_density = pop_100m_calc / pixel_area_km2

print("\n===== POPULATION DENSITY =====")
print("Min:", pop_density.min().item())
print("Max:", pop_density.max().item())
print("Mean:", pop_density.mean().item())

# 6. LST
for entry in os.scandir("raw"):

    if entry.is_file() and 'LST' in entry.name and entry.name.endswith('.tif'):

        lst = rxr.open_rasterio(
            entry.path,
            masked=True
        ).squeeze(drop=True)

print("\n===== ORIGINAL LST =====")
print("CRS:", lst.rio.crs)
print("Resolution:", lst.rio.resolution())
print("Shape:", lst.shape)
print("Bounds:", lst.rio.bounds())
print("Min:", lst.min().item())
print("Max:", lst.max().item())
print("Mean:", lst.mean().item())
print("Std:", lst.std().item())

# 7. CALCULATE UHI

lst_mean = lst.mean(skipna=True)
lst_std = lst.std(skipna=True)

print("\n===== LST STATISTICS =====")
print("Mean LST:", lst_mean.item())
print("Std LST:", lst_std.item())

# UHI = (LST - mean LST) / LST

uhi = (lst - lst_mean) / lst

print("Min:", uhi.min().item())
print("Max:", uhi.max().item())
print("Mean:", uhi.mean().item())


# 8. MATCH LST AND UHI TO 100m POPULATION GRID

lst_100m = lst.rio.reproject_match(
    pop_100m,
    resampling=Resampling.bilinear
)

uhi_100m = uhi.rio.reproject_match(
    pop_100m,
    resampling=Resampling.bilinear
)

# 9. OLD POPULATION

old_pop = rxr.open_rasterio(
    r"raw/total_population_old.tif",
    masked=True
).squeeze(drop=True)

print("\n===== ORIGINAL OLD POPULATION =====")
print("CRS:", old_pop.rio.crs)
print("Resolution:", old_pop.rio.resolution())
print("Shape:", old_pop.shape)
print("Bounds:", old_pop.rio.bounds())


old_pop_100m = old_pop.rio.reproject_match(
    pop_100m,
    resampling=Resampling.nearest
)

print("\n===== OLD POPULATION 100m =====")
print("Min:", old_pop_100m.min().item())
print("Max:", old_pop_100m.max().item())
print("Mean:", old_pop_100m.mean().item())

# 10. EXACT ALIGNMENT CHECK

uhi_100m, pop_density, old_pop_100m, pop_100m, lst_100m = xr.align(
    uhi_100m,
    pop_density,
    old_pop_100m,
    pop_100m,
    lst_100m,
    join="exact"
)

print("\n===== ALIGNMENT =====")
print("All rasters have identical x/y coordinates.")

# 11. VALID MASK

valid = (
    uhi_100m.notnull()
    & pop_density.notnull()
    & old_pop_100m.notnull()
)

print("\n===== VALID MASK =====")
print("Valid:", int(valid.sum().item()))
print("Invalid:", int((~valid).sum().item()))

# 12. CALCULATION VERSIONS — NA → 0

uhi_calc = uhi_100m.fillna(0)
density_calc = pop_density.fillna(0)
old_pop_calc = old_pop_100m.fillna(0)

# 13. NORMALIZATION

def minmax(da):

    minimum = da.min()
    maximum = da.max()

    print(
        f"Normalizing: "
        f"min={minimum.item()}, "
        f"max={maximum.item()}"
    )

    if np.isclose(
        (maximum - minimum).item(),
        0
    ):
        return da * 0

    return (da - minimum) / (maximum - minimum)


uhi_norm = minmax(uhi_calc)
density_norm = minmax(density_calc)
old_pop_norm = minmax(old_pop_calc)

# 14. CHECK THE NORMALIZED RASTERS

print("\n===== NORMALIZED UHI =====")
print("Min:", uhi_norm.min().item())
print("Max:", uhi_norm.max().item())
print("Mean:", uhi_norm.mean().item())


print("\n===== NORMALIZED POPULATION DENSITY =====")
print("Min:", density_norm.min().item())
print("Max:", density_norm.max().item())
print("Mean:", density_norm.mean().item())


print("\n===== NORMALIZED OLD POPULATION =====")
print("Min:", old_pop_norm.min().item())
print("Max:", old_pop_norm.max().item())
print("Mean:", old_pop_norm.mean().item())

# 15. MULTIPLY

uhi_risk = (
    uhi_norm
    * density_norm
    * old_pop_norm
)

uhi_risk = uhi_risk.where(valid)

# 16. CHECK THE PRODUCT
print("\n===== FINAL UHI RISK =====")

print("Min:", uhi_risk.min().item())
print("Max:", uhi_risk.max().item())
print("Mean:", uhi_risk.mean().item())
print("NA:", int(np.isnan(uhi_risk.values).sum()))

# 17. EXPORT ALL INTERMEDIATE RASTERS

print("\n===== EXPORTING =====")

out_dir = Path("intermediate")
out_dir.mkdir(exist_ok=True)

# Raw LST
lst_100m.rio.to_raster(
    out_dir / Path("LST_100m.tif"),
    dtype="float32",
    overwrite=True
)

# Standardized UHI
uhi_100m.rio.to_raster(
    "intermediate/UHI_100m.tif",
    dtype="float32"
)


# Total population
pop_100m.rio.to_raster(
    "intermediate/Total_population_100m.tif",
    dtype="float32"
)


# Population density
pop_density.rio.to_raster(
    "intermediate/Population_density_100m.tif",
    dtype="float32"
)


# Old population
old_pop_100m.rio.to_raster(
    "intermediate/Old_population_100m.tif",
    dtype="float32"
)

out_dir = Path("normalized")
out_dir.mkdir(exist_ok=True)


# Normalized UHI
uhi_calc.rio.to_raster(
    "normalized/UHI_normalized_100m.tif",
    dtype="float32"
)


# Normalized population density
density_norm.rio.to_raster(
    "normalized/Population_density_normalized_100m.tif",
    dtype="float32"
)


# Normalized old population
old_pop_norm.rio.to_raster(
    "normalized/Old_population_normalized_100m.tif",
    dtype="float32"
)


# Final product
uhi_risk.rio.to_raster(
    "final/UHI_risk_100m.tif",
    dtype="float32"
)




print("\n===== FILES CREATED =====")

print("LST_100m.tif")
print("UHI_100m.tif")
print("Total_population_100m.tif")
print("Population_density_100m.tif")
print("Old_population_100m.tif")
print("UHI_normalized_100m.tif")
print("Population_density_normalized_100m.tif")
print("Old_population_normalized_100m.tif")
print("UHI_risk_100m.tif")


