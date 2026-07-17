from datetime import datetime, timezone

from app.services.sentinel1 import filter_images_per_month


def _feat(day: int, month: int = 1, year: int = 2024) -> dict:
    return {
        "id": f"S1_{year}{month:02d}{day:02d}",
        "properties": {"datetime": datetime(year, month, day, 12, 0, tzinfo=timezone.utc).isoformat()},
    }


def test_filter_images_per_month_keeps_all_when_zero():
    feats = [_feat(d) for d in range(1, 8)]
    out = filter_images_per_month(feats, 0)
    assert len(out) == 7


def test_filter_images_per_month_picks_two_spaced_in_month():
    feats = [_feat(d) for d in range(1, 8)]
    out = filter_images_per_month(feats, 2)
    assert len(out) == 2
    days = [int(f["id"][-2:]) for f in out]
    assert days == [1, 7]


def test_filter_images_per_month_applies_per_calendar_month():
    jan = [_feat(d, month=1) for d in range(1, 6)]
    feb = [_feat(d, month=2) for d in range(1, 6)]
    out = filter_images_per_month(jan + feb, 2)
    assert len(out) == 4
