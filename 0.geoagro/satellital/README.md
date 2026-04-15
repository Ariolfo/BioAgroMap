# 🛰️ Automatic Download of Sentinel-1 and Sentinel-2 from Copernicus

The scripts allow you to search for and download Sentinel-1 and Sentinel-2 products directly from the Copernicus Data Space Ecosystem (CDSE) using authentication with "Keycloak" and spatial queries using a polygon in WKT format.

---

## 🚀 Características
- Compatible with **Sentinel-1** and **Sentinel-2** (configurable  
- Final summary with file sizes and total size.

---

## 📦 Requirements
Install the necessary dependencies:
- Python 3.9+ 
- Librerías:  
  - `requests`  
  - `pandas`  
  - `python-dateutil`  
  - `shapely`  
`
pip install -r requirements.txt
`

---
### Copernicus Credentials
`copernicus_user = "tu_usuario"
copernicus_password = "tu_contraseña"`

### Mission Selection
`data_collection = "SENTINEL-2"   # Change to "SENTINEL-1" if required`

### Area in WKT format (example taken from geojson.io)
`AREA_WKT = "POLYGON ((-75.5484 6.2278, -75.5484 6.2062, -75.5174 6.2062, -75.5174 6.2278, -75.5484 6.2278))"`

### Discharge period
`START_DATE = date(2024, 12, 1)
END_DATE   = date(2025, 1, 1)`

### Download directory
`DOWNLOAD_DIR = "downloads_sentinel2"`
