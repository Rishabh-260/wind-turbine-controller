"""Pass/fail limits for the deterministic validation scenarios."""

from __future__ import annotations

import math

from .metrics import ScenarioMetrics, Trace

SAMPLE_PERIOD_S = 0.02
PITCH_MIN_DEG = 0.0
PITCH_MAX_DEG = 30.0
PITCH_RATE_MAX_DEG_S = 8.0


def validate_scenario(name: str, trace: Trace, metrics: ScenarioMetrics) -> list[str]:
    failures: list[str] = []
    sample_periods = [b - a for a, b in zip(trace.time_s, trace.time_s[1:])]
    if any(not math.isclose(period, SAMPLE_PERIOD_S, rel_tol=0.0, abs_tol=1e-9)
           for period in sample_periods):
        failures.append(f"simulation time step must be {SAMPLE_PERIOD_S:.2f} s")
    if min(trace.pitch_angle_deg) < PITCH_MIN_DEG - 1e-9:
        failures.append(f"pitch angle fell below {PITCH_MIN_DEG:g} deg")
    if max(trace.pitch_angle_deg) > PITCH_MAX_DEG + 1e-9:
        failures.append(f"pitch angle exceeded {PITCH_MAX_DEG:g} deg")
    if metrics.max_pitch_rate_deg_s > PITCH_RATE_MAX_DEG_S + 1e-6:
        failures.append(
            f"pitch rate {metrics.max_pitch_rate_deg_s:.3f} deg/s exceeds "
            f"{PITCH_RATE_MAX_DEG_S:g} deg/s"
        )

    if name == "tracking":
        if metrics.steady_state_error_pct > 2.0:
            failures.append(f"steady-state error {metrics.steady_state_error_pct:.2f}% exceeds 2.00%")
        if metrics.overshoot_pct > 10.0:
            failures.append(f"overshoot {metrics.overshoot_pct:.2f}% exceeds 10.00%")
        if metrics.settling_time_s is None or metrics.settling_time_s > 20.0:
            failures.append("tracking did not settle within 20.0 s of the wind step")
    elif name == "gust":
        if metrics.peak_speed_deviation_pct > 30.0:
            failures.append(
                f"gust speed deviation {metrics.peak_speed_deviation_pct:.2f}% exceeds 30.00%"
            )
        if metrics.recovery_time_s is None or metrics.recovery_time_s > 10.0:
            failures.append("rotor speed did not recover within 10.0 s after the gust")
    elif name == "saturation":
        if not metrics.pitch_limit_reached:
            failures.append("pitch actuator did not reach its upper travel limit")
        if metrics.overshoot_pct > 25.0:
            failures.append(f"overshoot {metrics.overshoot_pct:.2f}% exceeds 25.00%")
    else:
        failures.append(f"unknown scenario: {name}")
    return failures
