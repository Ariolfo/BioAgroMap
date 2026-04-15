import importlib

packages = ["gdal", "rasterio", "tslearn", "statsmodels", "geopandas"]

for pkg in packages: 
    try:
        m = importlib.import_module(pkg)
        version = getattr(m, "__version__", None) or getattr(m, "VERSION", None)
        print(f"{pkg:15s} {version}")
    except ImportError:
        print(f"{pkg:15s} not installed")