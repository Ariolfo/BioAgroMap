"""Pruebas de extracción de órdenes composite y paquetes PSScene."""
from __future__ import annotations

import zipfile
from pathlib import Path

from app.services.planet_ps_extract import extract_planet_zips_from_raster_ps


def _write_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)


def test_extracts_psscene_analytic_sr_when_composite_is_absent(tmp_path: Path) -> None:
    source = tmp_path / "rasterPS"
    output = tmp_path / "recortesPS"
    source.mkdir()
    _write_zip(
        source / "single_scene.zip",
        {
            "PSScene/20260301_162310_32_24d3_3B_AnalyticMS_SR_8b_clip.tif": b"analytic",
            "PSScene/20260301_162310_32_24d3_3B_udm2_clip.tif": b"mask",
            "PSScene/20260301_162310_32_24d3_3B_AnalyticMS_8b_metadata_clip.xml": b"<xml/>",
            "PSScene/20260301_162310_32_24d3_metadata.json": b"{}",
        },
    )

    result = extract_planet_zips_from_raster_ps(source, output)

    assert result["ok"] is True
    assert result["processed"] == 1
    assert result["errors"] == []
    assert result["results"][0]["composite_out"] == "PS_01-03-26.tif"
    assert (output / "PS_01-03-26.tif").read_bytes() == b"analytic"
    assert any(p.name.endswith("_3B_udm2_clip.tif") for p in output.iterdir())


def test_rerun_replaces_outputs_instead_of_accumulating(tmp_path: Path) -> None:
    source = tmp_path / "rasterPS"
    output = tmp_path / "recortesPS"
    source.mkdir()
    _write_zip(
        source / "orden.zip",
        {
            "composite.tif": b"composite",
            "composite_udm2.tif": b"mask",
            "20260524_155646_98_2539_3B_AnalyticMS_8b_metadata_clip.xml": b"<xml/>",
        },
    )

    first = extract_planet_zips_from_raster_ps(source, output)
    second = extract_planet_zips_from_raster_ps(source, output)

    assert first["processed"] == second["processed"] == 1
    tifs = sorted(p.name for p in output.glob("*.tif"))
    assert tifs == ["PS_24-05-26.tif", "PS_24-05-26_composite_udm2.tif"]


def test_composite_remains_preferred_over_psscene_fallback(tmp_path: Path) -> None:
    source = tmp_path / "rasterPS"
    output = tmp_path / "recortesPS"
    source.mkdir()
    _write_zip(
        source / "mixed.zip",
        {
            "composite.tif": b"composite",
            "20260524_155646_98_2539_3B_AnalyticMS_8b_metadata_clip.xml": b"<xml/>",
            "PSScene/20260301_162310_32_24d3_3B_AnalyticMS_SR_8b_clip.tif": b"analytic",
        },
    )

    result = extract_planet_zips_from_raster_ps(source, output)

    assert result["processed"] == 1
    assert (output / "PS_24-05-26.tif").read_bytes() == b"composite"
