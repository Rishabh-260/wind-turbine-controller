from __future__ import annotations

import csv

import pytest

from wind_validation.metrics import TraceError, calculate_metrics, read_trace


FIELDS = [
    "time_s", "wind_mps", "rotor_speed_rpm", "rated_speed_rpm",
    "pitch_command_deg", "pitch_angle_deg",
]


def write_trace(path, rows, fields=FIELDS):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_read_trace_rejects_missing_file(tmp_path):
    with pytest.raises(TraceError, match="does not exist"):
        read_trace(tmp_path / "missing.csv")


def test_read_trace_rejects_missing_column(tmp_path):
    path = tmp_path / "bad.csv"
    write_trace(path, [], fields=FIELDS[:-1])
    with pytest.raises(TraceError, match="missing required columns"):
        read_trace(path)


def test_read_trace_rejects_non_numeric_and_nonfinite_values(tmp_path):
    for filename, value, message in (("text.csv", "oops", "invalid number"),
                                     ("nan.csv", "nan", "non-finite")):
        path = tmp_path / filename
        row = dict(zip(FIELDS, [0, 10, value, 12, 0, 0]))
        write_trace(path, [row])
        with pytest.raises(TraceError, match=message):
            read_trace(path)


def test_read_trace_rejects_non_increasing_time(tmp_path):
    path = tmp_path / "time.csv"
    rows = [dict(zip(FIELDS, [t, 10, 12, 12, 0, 0])) for t in (0, 0)]
    write_trace(path, rows)
    with pytest.raises(TraceError, match="strictly increasing"):
        read_trace(path)


def test_tracking_metrics_measure_error_overshoot_and_settling(tmp_path):
    path = tmp_path / "tracking.csv"
    speeds = [10, 11, 12.6, 12.1, 12, 12, 12]
    rows = [dict(zip(FIELDS, [i, 10 if i < 1 else 13, speeds[i], 12, 1, 1]))
            for i in range(len(speeds))]
    write_trace(path, rows)
    metrics = calculate_metrics("tracking", read_trace(path))
    assert metrics.steady_state_reference == "rated_speed"
    assert metrics.steady_state_reference_rpm == pytest.approx(12.0)
    assert metrics.overshoot_pct == pytest.approx(5.0)
    assert metrics.settling_time_s == pytest.approx(2.0)
    assert metrics.steady_state_error_pct == pytest.approx(0.4167, abs=0.001)


def test_pitch_rate_metric_is_calculated_from_samples(tmp_path):
    path = tmp_path / "rate.csv"
    rows = [dict(zip(FIELDS, [0, 10, 12, 12, 0, 0])),
            dict(zip(FIELDS, [0.02, 10, 12, 12, 0.16, 0.16]))]
    write_trace(path, rows)
    metrics = calculate_metrics("saturation", read_trace(path))
    assert metrics.max_pitch_rate_deg_s == pytest.approx(8.0)
