
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest

from app.risk.community_report_analyzer import (
    analyze_community_reports,
)


def make_report(
    status="verified",
    depth=50,
    age_days=0,
    latitude=23.0225,
    longitude=72.5714,
):
    return SimpleNamespace(
        status=status,
        water_depth_cm=depth,
        created_at=datetime.now(timezone.utc)
        - timedelta(days=age_days),
        latitude=latitude,
        longitude=longitude,
    )


def test_nearby_verified_report():
    now = datetime.now(timezone.utc)

    report = make_report(depth=50)

    result = analyze_community_reports(
        [report],
        latitude=23.0225,
        longitude=72.5714,
        now=now,
    )

    assert result["available"] is True
    assert result["score"] == 75
    assert result["category"] == "severe"
    assert result["nearby_verified_reports"] == 1


def test_pending_report_is_ignored():
    now = datetime.now(timezone.utc)

    report = make_report(status="pending")

    result = analyze_community_reports(
        [report],
        latitude=23.0225,
        longitude=72.5714,
        now=now,
    )

    assert result["available"] is False
    assert result["score"] is None


def test_old_report_is_ignored():
    now = datetime.now(timezone.utc)

    report = make_report(age_days=10)

    result = analyze_community_reports(
        [report],
        latitude=23.0225,
        longitude=72.5714,
        now=now,
    )

    assert result["available"] is False


def test_report_outside_radius_is_ignored():
    now = datetime.now(timezone.utc)

    report = make_report(
        latitude=23.2,
        longitude=72.8,
    )

    result = analyze_community_reports(
        [report],
        latitude=23.0225,
        longitude=72.5714,
        now=now,
    )

    assert result["available"] is False


def test_invalid_coordinates_are_rejected():
    with pytest.raises(ValueError):
        analyze_community_reports(
            [],
            latitude=100,
            longitude=72.5714,
        )


def test_unknown_water_depth():
    now = datetime.now(timezone.utc)

    report = make_report(depth=None)

    result = analyze_community_reports(
        [report],
        latitude=23.0225,
        longitude=72.5714,
        now=now,
    )

    assert result["available"] is True
    assert result["score"] == 50

@pytest.mark.parametrize(
    "latitude,longitude",
    [
        (True, 72.5714),
        (23.0225, False),
        ("23.0225", 72.5714),
        (float("nan"), 72.5714),
        (23.0225, float("inf")),
        (91, 72.5714),
        (23.0225, -181),
    ],
)
def test_invalid_coordinates_are_rejected(latitude, longitude):
    with pytest.raises(ValueError):
        analyze_community_reports(
            [],
            latitude=latitude,
            longitude=longitude,
        )


@pytest.mark.parametrize(
    "radius",
    [True, False, 0, -1, float("nan"), float("inf"), "3"],
)
def test_invalid_radius_is_rejected(radius):
    with pytest.raises(ValueError):
        analyze_community_reports(
            [],
            latitude=23.0225,
            longitude=72.5714,
            radius_km=radius,
        )

@pytest.mark.parametrize(
    "latitude,longitude",
    [
        (True, 72.5714),
        (100, 72.5714),
        (23.0225, False),
        (23.0225, -181),
    ],
)
def test_invalid_report_coordinates_are_rejected(latitude, longitude):
    report = make_report(
        latitude=latitude,
        longitude=longitude,
    )

    result = analyze_community_reports(
        [report],
        latitude=23.0225,
        longitude=72.5714,
    )

    assert result["available"] is False
    assert result["observations_rejected"] == 1


def test_invalid_report_timestamp_is_rejected():
    report = make_report()
    report.created_at = "invalid timestamp"

    result = analyze_community_reports(
        [report],
        latitude=23.0225,
        longitude=72.5714,
    )

    assert result["available"] is False
    assert result["observations_rejected"] == 1


def test_future_report_is_rejected():
    report = make_report()
    report.created_at = datetime.now(timezone.utc) + timedelta(days=1)

    result = analyze_community_reports(
        [report],
        latitude=23.0225,
        longitude=72.5714,
    )

    assert result["available"] is False
    assert result["observations_rejected"] == 1


def test_naive_report_timestamp_is_treated_as_utc():
    now = datetime.now(timezone.utc)
    report = make_report()
    report.created_at = now.replace(tzinfo=None)

    result = analyze_community_reports(
        [report],
        latitude=23.0225,
        longitude=72.5714,
        now=now,
    )

    assert result["available"] is True


@pytest.mark.parametrize(
    "depth,expected_score",
    [
        (0, 25),
        (9.9, 25),
        (10, 50),
        (29.9, 50),
        (30, 75),
        (59.9, 75),
        (60, 100),
        (100, 100),
    ],
)
def test_water_depth_score_boundaries(depth, expected_score):
    report = make_report(depth=depth)
    now = datetime.now(timezone.utc)

    result = analyze_community_reports(
        [report],
        latitude=23.0225,
        longitude=72.5714,
        now=now,
    )

    assert result["available"] is True
    assert result["score"] == expected_score


@pytest.mark.parametrize(
    "depth",
    [True, False, "50", -1, float("nan"), float("inf")],
)
def test_invalid_water_depth_is_rejected(depth):
    report = make_report(depth=depth)

    result = analyze_community_reports(
        [report],
        latitude=23.0225,
        longitude=72.5714,
    )

    assert result["available"] is False
    assert result["observations_rejected"] == 1


def test_multiple_reports_increase_risk_signal():
    now = datetime.now(timezone.utc)

    reports = [
        make_report(depth=50),
        make_report(depth=50),
    ]

    result = analyze_community_reports(
        reports,
        latitude=23.0225,
        longitude=72.5714,
        now=now,
    )

    assert result["available"] is True
    assert result["nearby_verified_reports"] == 2
    assert result["score"] == 86


def test_zero_weight_reports_return_insufficient_data():
    report = make_report()

    result = analyze_community_reports(
        [report],
        latitude=23.0225,
        longitude=72.5714,
        radius_km=3,
    )

    # A report exactly at the radius has zero distance weight.
    report.latitude = 23.0495
    report.longitude = 72.5714

    result = analyze_community_reports(
        [report],
        latitude=23.0225,
        longitude=72.5714,
        radius_km=3,
    )

    assert result["available"] is False
    assert result["category"] == "insufficient_data"



@pytest.mark.parametrize(
    "depth,expected_category",
    [
        (0, "low"),
        (10, "high"),
        (30, "severe"),
        (60, "severe"),
    ],
)
def test_risk_categories(depth, expected_category):
    result = analyze_community_reports(
        [make_report(depth=depth)],
        latitude=23.0225,
        longitude=72.5714,
    )

    assert result["category"] == expected_category


# Tests the insufficient-data result when all report weights are zero.
def test_returns_insufficient_when_total_weight_is_zero(monkeypatch):
    from app.risk import community_report_analyzer as analyzer

    report = make_report(depth=30)
    now = datetime.now(timezone.utc)

    monkeypatch.setattr(
        analyzer,
        "calculate_distance_km",
        lambda *args: 5.0,
    )

    result = analyzer.analyze_community_reports(
        [report],
        latitude=23.0225,
        longitude=72.5714,
        radius_km=5.0,
        now=now,
    )

    assert result["available"] is False
    assert result["score"] is None
    assert result["category"] == "insufficient_data"
    assert result["nearby_verified_reports"] == 1
    assert result["message"] == (
        "Community report weights could not be calculated."
    )


# Tests the moderate category using two independent verified reports.
def test_classifies_moderate_community_risk():
    reports = [
        make_report(depth=5),
        make_report(depth=5),
    ]
    now = datetime.now(timezone.utc)

    result = analyze_community_reports(
        reports,
        latitude=23.0225,
        longitude=72.5714,
        radius_km=5.0,
        now=now,
    )

    assert result["available"] is True
    assert result["score"] == 29
    assert result["category"] == "moderate"
    assert result["nearby_verified_reports"] == 2
