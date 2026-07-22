"""El fondo nodata de composites PlanetScope debe quedar NaN en todos los índices PS."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from app.services.s2_vegetation_indices import (
    compute_ps_index_arrays,
    read_planet_eight_bands_bgri,
)

PS_INDICES = (
    "NDVI",
    "EVI",
    "NDWI",
    "MSAVI2",
    "MTVI2",
    "VARI",
    "TGI",
    "KNDVI",
    "GIYI",
    "MCARI",
    "NDRE",
    "RSTRUCTURE",
)


def _write_ps_composite(path: Path) -> None:
    """8 bandas uint16 con nodata=0; mitad derecha = fondo (0 en todas las bandas)."""
    h = w = 10
    data = np.zeros((8, h, w), dtype=np.uint16)
    rng = np.random.default_rng(7)
    data[:, :, : w // 2] = rng.integers(500, 4000, size=(8, h, w // 2), dtype=np.uint16)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=8,
        dtype="uint16",
        nodata=0,
        crs="EPSG:4326",
        transform=from_origin(-74.0, 4.6, 0.0001, 0.0001),
    ) as dst:
        dst.write(data)


def test_all_ps_indices_leave_background_as_nan(tmp_path: Path) -> None:
    tif = tmp_path / "PS_01-01-26.tif"
    _write_ps_composite(tif)
    bgri, _profile = read_planet_eight_bands_bgri(tif)

    for name in PS_INDICES:
        arr = compute_ps_index_arrays(bgri, name)
        assert np.isnan(arr[:, 5:]).all(), f"{name}: el fondo nodata no quedó NaN"
        assert np.isfinite(arr[:, :5]).any(), f"{name}: sin valores válidos en el footprint"
