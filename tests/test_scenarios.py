from __future__ import annotations

import os
from pathlib import Path

import pytest

from wind_validation.acceptance import validate_scenario
from wind_validation.metrics import calculate_metrics, read_trace


SCENARIOS = ("tracking", "gust", "saturation")
RAW_DIR = Path("artifacts/raw")


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_matlab_scenario_meets_acceptance_criteria(scenario: str):
    path = RAW_DIR / f"{scenario}.csv"
    if not path.exists():
        if os.environ.get("WIND_VALIDATION_REQUIRE_SIMULATION") == "1":
            pytest.fail(f"Required MATLAB output is missing: {path}")
        pytest.skip("Run matlab/run_scenarios.m to generate integration-test traces")

    trace = read_trace(path)
    metrics = calculate_metrics(scenario, trace)
    failures = validate_scenario(scenario, trace, metrics)
    assert failures == [], "; ".join(failures)
