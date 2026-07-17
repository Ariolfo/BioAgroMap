"""Tests for Sentinel-2 AOI cloud fraction from SCL."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from app.services.sentinel2 import MAX_AOI_CLOUD, aoi_cloud_fraction_from_scl


def _write_scl_tif(path: Path, arr: np.ndarray, west: float, north: float, res: float = 0.001) -> None:
    h, w = arr.shape
    transform = from_origin(west, north, res, res)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype=arr.dtype,
        crs="EPSG:4326",
        transform=transform,
        nodata=0,
    ) as dst:
        dst.write(arr, 1)


def test_aoi_cloud_fraction_below_threshold(tmp_path: Path) -> None:
    # 10x10: mostly vegetation (4), 10 cloudy pixels (8) → 10% if all valid
    arr = np.full((10, 10), 4, dtype=np.uint8)
    arr[0, :10] = 8
    scl = tmp_path / "scl.tif"
    _write_scl_tif(scl, arr, west=-74.01, north=4.61)
    aoi = box(-74.01, 4.60, -74.00, 4.61)
    frac = aoi_cloud_fraction_from_scl(scl, aoi)
    assert frac is not None
    assert 0.05 <= frac <= 0.20
    assert frac < MAX_AOI_CLOUD


def test_aoi_cloud_fraction_above_threshold(tmp_path: Path) -> None:
    arr = np.full((10, 10), 9, dtype=np.uint8)  # all high-proba cloud
    scl = tmp_path / "scl.tif"
    _write_scl_tif(scl, arr, west=-74.01, north=4.61)
    aoi = box(-74.01, 4.60, -74.00, 4.61)
    frac = aoi_cloud_fraction_from_scl(scl, aoi)
    assert frac is not None
    assert frac > MAX_AOI_CLOUD
