from __future__ import annotations

from wind_validation.acceptance import validate_scenario
from wind_validation.metrics import Trace, calculate_metrics


def make_trace(name: str) -> Trace:
    if name == "tracking":
        times = tuple(i * 0.02 for i in range(1501))
        wind = tuple(10.0 if t < 5 else 13.0 for t in times)
        speed = tuple(10.8 if t < 5 else 12.0 for t in times)
        pitch = tuple(min(3.0, max(0.0, 8.0 * (t - 5.0))) for t in times)
    elif name == "gust":
        times = tuple(i * 0.02 for i in range(2001))
        wind = tuple(14.0 if 5 <= t < 10 else 11.0 for t in times)
        speed = tuple(10.78 + (2.0 if 5 <= t < 10 else 0.0) for t in times)
        pitch = tuple(
            min(2.0, max(0.0, 8.0 * (t - 5.0))) if t < 10
            else max(0.0, 2.0 - 8.0 * (t - 10.0))
            for t in times
        )
    else:
        times = tuple(i * 0.02 for i in range(1001))
        wind = tuple(18.0 if 2 <= t < 20 else 10.0 for t in times)
        speed = tuple(12.0 for _ in times)
        pitch = tuple(min(30.0, max(0.0, 3.0 * (t - 2))) if t < 20 else 30.0 for t in times)

    return Trace(
        time_s=times,
        wind_mps=wind,
        rotor_speed_rpm=speed,
        rated_speed_rpm=tuple(12.0 for _ in times),
        pitch_command_deg=pitch,
        pitch_angle_deg=pitch,
    )


def test_acceptance_rules_pass_reference_scenario_shapes():
    for name in ("tracking", "gust", "saturation"):
        trace = make_trace(name)
        failures = validate_scenario(name, trace, calculate_metrics(name, trace))
        assert failures == []


def test_acceptance_rejects_pitch_outside_bounds():
    trace = make_trace("tracking")
    bad = Trace(**{**trace.__dict__, "pitch_angle_deg": tuple(-0.1 for _ in trace.time_s)})
    failures = validate_scenario("tracking", bad, calculate_metrics("tracking", bad))
    assert any("fell below" in failure for failure in failures)
