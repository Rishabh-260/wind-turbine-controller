"""Trace loading and controller-response metrics."""

from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

REQUIRED_COLUMNS = (
    "time_s",
    "wind_mps",
    "rotor_speed_rpm",
    "rated_speed_rpm",
    "pitch_command_deg",
    "pitch_angle_deg",
)


class TraceError(ValueError):
    """Raised when a simulation trace is missing or malformed."""


@dataclass(frozen=True)
class Trace:
    time_s: tuple[float, ...]
    wind_mps: tuple[float, ...]
    rotor_speed_rpm: tuple[float, ...]
    rated_speed_rpm: tuple[float, ...]
    pitch_command_deg: tuple[float, ...]
    pitch_angle_deg: tuple[float, ...]

    def __len__(self) -> int:
        return len(self.time_s)


@dataclass(frozen=True)
class ScenarioMetrics:
    scenario: str
    steady_state_reference: str | None
    steady_state_reference_rpm: float | None
    steady_state_error_pct: float | None
    overshoot_pct: float
    settling_time_s: float | None
    peak_speed_deviation_pct: float
    recovery_time_s: float | None
    max_pitch_deg: float
    max_pitch_rate_deg_s: float
    pitch_limit_reached: bool
    max_speed_rpm: float

    def to_dict(self) -> dict[str, str | float | bool | None]:
        return asdict(self)


def read_trace(path: str | Path) -> Trace:
    """Read and validate a MATLAB-generated CSV trace."""
    source = Path(path)
    if not source.is_file():
        raise TraceError(f"Trace file does not exist: {source}")

    try:
        with source.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            headers = reader.fieldnames or []
            missing = [column for column in REQUIRED_COLUMNS if column not in headers]
            if missing:
                raise TraceError(f"{source}: missing required columns: {', '.join(missing)}")
            columns: dict[str, list[float]] = {column: [] for column in REQUIRED_COLUMNS}
            for row_number, row in enumerate(reader, start=2):
                for column in REQUIRED_COLUMNS:
                    try:
                        value = float(row[column])
                    except (TypeError, ValueError) as exc:
                        raise TraceError(
                            f"{source}:{row_number}: invalid number in {column!r}"
                        ) from exc
                    if not math.isfinite(value):
                        raise TraceError(f"{source}:{row_number}: non-finite value in {column!r}")
                    columns[column].append(value)
    except OSError as exc:
        raise TraceError(f"Could not read trace {source}: {exc}") from exc

    if not columns["time_s"]:
        raise TraceError(f"{source}: trace contains no samples")
    if any(b <= a for a, b in zip(columns["time_s"], columns["time_s"][1:])):
        raise TraceError(f"{source}: time_s must be strictly increasing")
    if any(value <= 0 for value in columns["rated_speed_rpm"]):
        raise TraceError(f"{source}: rated_speed_rpm must be positive")
    return Trace(**{column: tuple(values) for column, values in columns.items()})


def _settling_time(
    time_s: tuple[float, ...],
    signal: tuple[float, ...],
    target: float,
    after_s: float,
    band: float,
) -> float | None:
    candidates = [i for i, time in enumerate(time_s) if time >= after_s]
    for index in candidates:
        if all(abs(value - target) <= band for value in signal[index:]):
            return time_s[index] - after_s
    return None


def _max_rate(trace: Trace) -> float:
    rates = [
        abs(b - a) / (t1 - t0)
        for t0, t1, a, b in zip(
            trace.time_s,
            trace.time_s[1:],
            trace.pitch_angle_deg,
            trace.pitch_angle_deg[1:],
        )
    ]
    return max(rates, default=0.0)


def calculate_metrics(name: str, trace: Trace) -> ScenarioMetrics:
    """Calculate common response and actuator metrics from one trace."""
    time = trace.time_s
    speed = trace.rotor_speed_rpm
    rated = trace.rated_speed_rpm[-1]
    max_pitch = max(trace.pitch_angle_deg)
    rate = _max_rate(trace)

    if name == "tracking":
        transition = next(
            (i for i in range(1, len(trace)) if trace.wind_mps[i] != trace.wind_mps[i - 1]),
            0,
        )
        transition_time = time[transition]
        end = [value for t, value in zip(time, speed) if t >= max(time[-1] - 5.0, transition_time)]
        reference_speed = rated
        reference_name = "rated_speed"
        steady_error = abs(sum(end) / len(end) - reference_speed) / reference_speed * 100.0
        post_step = [value for t, value in zip(time, speed) if t >= transition_time]
        overshoot = max(0.0, max(post_step) - rated) / rated * 100.0
        settling = _settling_time(time, speed, rated, transition_time, 0.02 * rated)
        peak_deviation = overshoot
        recovery = None
    elif name == "gust":
        gust_start = next(
            (i for i in range(1, len(trace)) if trace.wind_mps[i] > trace.wind_mps[i - 1]),
            0,
        )
        gust_end = next(
            (i for i in range(gust_start + 1, len(trace))
             if trace.wind_mps[i] < trace.wind_mps[i - 1]),
            len(trace) - 1,
        )
        baseline = speed[max(0, gust_start - 1)]
        reference_speed = baseline
        reference_name = "pre_gust_speed"
        peak_deviation = max(abs(value - baseline) for value in speed[gust_start:]) / rated * 100.0
        recovery = _settling_time(
            time, speed, baseline, time[gust_end], 0.02 * rated
        )
        steady_error = abs(speed[-1] - reference_speed) / reference_speed * 100.0
        overshoot = max(0.0, max(speed[gust_start:]) - rated) / rated * 100.0
        settling = None
    else:
        # The saturation scenario is a transient actuator-limit test, not a
        # rated-speed steady-state test; do not report a misleading error.
        reference_speed = None
        reference_name = None
        steady_error = None
        overshoot = max(0.0, max(speed) - rated) / rated * 100.0
        peak_deviation = overshoot
        settling = None
        recovery = None

    return ScenarioMetrics(
        scenario=name,
        steady_state_reference=reference_name,
        steady_state_reference_rpm=reference_speed,
        steady_state_error_pct=steady_error,
        overshoot_pct=overshoot,
        settling_time_s=settling,
        peak_speed_deviation_pct=peak_deviation,
        recovery_time_s=recovery,
        max_pitch_deg=max_pitch,
        max_pitch_rate_deg_s=rate,
        pitch_limit_reached=max_pitch >= 29.9,
        max_speed_rpm=max(speed),
    )


def all_finite(values: Iterable[float]) -> bool:
    """Small utility retained for callers that validate derived vectors."""
    return all(math.isfinite(value) for value in values)
