# Semi-Automated UHI (Urban Heat Index) Risk Calculation

This collection of scripts calculate the UHI Risk for any area. In this case, the UHI risk for Quezon City is computed.

**To use this script, do the following:**

Create and activate a Conda environment, then install the required geospatial and remote sensing packages from conda-forge.

```
conda create -n uhi-risk python=3.12 -c conda-forge
conda activate uhi-risk

conda install -c conda-forge earthengine-api geemap osmnx geopandas pandas numpy rasterio shapely pystac-client rioxarray xarray odc-stac requests h3pandas
```
**Note:** Make sure to have a google earth engine account for the LST extraction.

**Run the following scripts**

1. Run **lst_extraction.py** to download the LST for the specified month in your selected study area.
2. Execute **oldpop_extraction.py** to calculate the total elderly population aged 60 and above.
3. Use **UHI_risk_comp.py** to compute the UHI risk per cell using the obtained spatial datasets (LST, total population, and total elderly population)
4. Convert the pixels into H3 polygons using pixel_to_hex for better visualization.

