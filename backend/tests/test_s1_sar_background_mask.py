"""El fondo SNAP (0.0 dB en VV y VH) debe quedar NaN y no entrar al clustering S1."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from app.services.s1_sar_indices import (
    compute_sar_index_array,
    read_vv_vh_pair_aligned,
)
from app.services.satellite_clustering import prepare_training_matrix


def _write_db_tif(path: Path, arr: np.ndarray) -> None:
    h, w = arr.shape
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(-74.0, 4.6, 0.0001, 0.0001),
    ) as dst:
        dst.write(arr.astype(np.float32), 1)


def _scene_db(fill_vv: float, fill_vh: float) -> tuple[np.ndarray, np.ndarray]:
    """10x10 con footprint en la mitad izquierda; fondo = 0.0 dB en ambas polarizaciones."""
    vv = np.zeros((10, 10), dtype=np.float32)
    vh = np.zeros((10, 10), dtype=np.float32)
    vv[:, :5] = fill_vv
    vh[:, :5] = fill_vh
    return vv, vh


def test_read_pair_masks_joint_zero_db_background(tmp_path: Path) -> None:
    vv, vh = _scene_db(-8.0, -14.0)
    # Un píxel real con VV=0 dB pero VH≠0 no debe enmascararse.
    vv[0, 0] = 0.0
    vh[0, 0] = -14.0
    vv_p, vh_p = tmp_path / "vv.tif", tmp_path / "vh.tif"
    _write_db_tif(vv_p, vv)
    _write_db_tif(vh_p, vh)

    vv_lin, vh_lin, _ = read_vv_vh_pair_aligned(vv_p, vh_p)

    assert np.isnan(vv_lin[:, 5:]).all()
    assert np.isnan(vh_lin[:, 5:]).all()
    assert np.isfinite(vv_lin[:, :5]).all()
    assert vv_lin[0, 0] == 1.0  # 0 dB real conservado


def test_sar_index_propagates_nan_background() -> None:
    vv = np.array([[0.16, np.nan], [0.04, 1.0]], dtype=np.float64)
    vh = np.array([[0.04, np.nan], [0.16, 1.0]], dtype=np.float64)
    for key in ("RVI", "RFDI", "VV_VH", "VH_VV", "NRPB"):
        out = compute_sar_index_array(vv, vh, key)
        assert np.isnan(out[0, 1]), key
        assert np.isfinite(out[0, 0]), key


def test_training_matrix_excludes_all_nan_background(tmp_path: Path) -> None:
    vv, vh = _scene_db(-8.0, -14.0)
    vv_p, vh_p = tmp_path / "vv.tif", tmp_path / "vh.tif"
    _write_db_tif(vv_p, vv)
    _write_db_tif(vh_p, vh)
    vv_lin, vh_lin, prof = read_vv_vh_pair_aligned(vv_p, vh_p)

    rvi = compute_sar_index_array(vv_lin, vh_lin, "RVI")
    stack = tmp_path / "rvi_stack.tif"
    prof2 = prof.copy()
    prof2.update(driver="GTiff", count=2)
    with rasterio.open(stack, "w", **prof2) as dst:
        dst.write(rvi, 1)
        dst.write(rvi, 2)

    Xs, _scaler, valid, _meta = prepare_training_matrix(stack, max_samples=1000)
    # Solo la mitad izquierda (footprint) entrena; el fondo queda fuera.
    assert int(valid.sum()) == 50
    assert Xs.shape[0] == 50
