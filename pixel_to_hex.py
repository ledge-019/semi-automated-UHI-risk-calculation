import geopandas as gpd
import pandas as pd
import numpy as np
import rasterio
from shapely.geometry import box
import osmnx as ox
import h3pandas


# 1. LOAD H3 HEXAGONS

quezon_city = ox.geocode_to_gdf(
    ["Quezon City, Philippines"]
)

qc_hex = quezon_city.h3.polyfill_resample(10)

# Must use the SAME CRS as the raster
qc_hex_proj = qc_hex.to_crs("EPSG:32651")

# Give every hexagon an ID
qc_hex_proj = qc_hex_proj.reset_index(drop=True)
qc_hex_proj["hex_id"] = qc_hex_proj.index


# 2. OPEN UHI RISK RASTER

with rasterio.open("final/UHI_risk_100m.tif") as src:

    print("Raster CRS:", src.crs)
    print("Raster resolution:", src.res)
    print("Raster shape:", src.height, src.width)
    print("Raster bounds:", src.bounds)

    # Read raster
    risk = src.read(1)

    # Convert raster NoData to NaN
    if src.nodata is not None:
        risk = np.where(
            risk == src.nodata,
            np.nan,
            risk
        )

    transform = src.transform
    raster_crs = src.crs

# 3. CHECK CRS

qc_hex_proj = qc_hex_proj.to_crs(raster_crs)

print("\nHexagon CRS:", qc_hex_proj.crs)
print("Raster CRS:", raster_crs)

# 4. CREATE RASTER PIXEL POLYGONS

rows, cols = np.where(~np.isnan(risk))

pixel_polygons = []

for row, col in zip(rows, cols):

    x1, y1 = rasterio.transform.xy(
        transform,
        row,
        col,
        offset="ul"
    )

    x2, y2 = rasterio.transform.xy(
        transform,
        row,
        col,
        offset="lr"
    )

    pixel_polygons.append(
        box(
            min(x1, x2),
            min(y1, y2),
            max(x1, x2),
            max(y1, y2)
        )
    )


# Create GeoDataFrame
raster_grid = gpd.GeoDataFrame(
    {
        "risk": risk[rows, cols],
        "row": rows,
        "col": cols
    },
    geometry=pixel_polygons,
    crs=raster_crs
)


# Pixel area
raster_grid["pixel_area"] = (
    raster_grid.geometry.area
)


# 5. FIND PIXELS THAT INTERSECT HEXAGONS

intersections = gpd.overlay(
    qc_hex_proj[["hex_id", "geometry"]],
    raster_grid,
    how="intersection"
)

print(intersections.head())
# print("\nNumber of intersections:", len(intersections))

# 6. CALCULATE OVERLAP AREA

intersections["overlap_area"] = (
    intersections.geometry.area
)

# 7. AREA-WEIGHTED UHI RISK

intersections["weighted_risk"] = (
    intersections["risk"]
    * intersections["overlap_area"]
)


weighted_risk = (
    intersections
    .groupby("hex_id")
    .agg(
        weighted_sum=("weighted_risk", "sum"),
        overlap_area=("overlap_area", "sum")
    )
)

weighted_risk["UHI_risk_mean"] = (
    weighted_risk["weighted_sum"]
    / weighted_risk["overlap_area"]
)


# 8. JOIN RESULT BACK TO HEXAGONS

qc_hex_proj = qc_hex_proj.join(
    weighted_risk["UHI_risk_mean"],
    on="hex_id"
)

# 9. CHECK RESULTS

print("\n===== H3 UHI RISK =====")

print(
    qc_hex_proj["UHI_risk_mean"].describe()
)

print(
    "\nNumber of hexagons:",
    len(qc_hex_proj)
)

print(
    "Hexagons with UHI risk:",
    qc_hex_proj["UHI_risk_mean"].notna().sum()
)

print(
    "Hexagons without UHI risk:",
    qc_hex_proj["UHI_risk_mean"].isna().sum()
)

# 10. SAVE

qc_hex_proj.to_file(
    "final/QC_H3_UHI_risk.gpkg",
    layer="uhi_risk",
    driver="GPKG"
)

print("\nSaved: QC_H3_UHI_risk.gpkg")