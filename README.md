# Semi-Automated UHI (Urban Heat Index) Risk Calculation

This collection of scripts calculate the UHI Risk for any area. In this case, the UHI risk for Quezon City is computed.

To use this script, do the following:

Create and activate a Conda environment, then install the required geospatial and remote sensing packages from conda-forge.

```
conda create -n uhi-risk python=3.12 -c conda-forge
conda activate uhi-risk

conda install -c conda-forge earthengine-api geemap osmnx geopandas pandas numpy rasterio shapely pystac-client rioxarray xarray odc-stac requests h3pandas
```
