# Wind Turbine Controller Validation Framework

A compact MATLAB and Python project that simulates a simplified wind turbine pitch controller, checks its response across deterministic operating scenarios, and builds a repeatable engineering report.

> This is an educational control-validation example. It is not an industrial turbine model or a safety-certified controller.

## What it demonstrates

- A discrete-time MATLAB simulation of rotor-speed dynamics, PI pitch control with wind-based feed-forward, anti-windup, and pitch actuator limits.
- Python trace validation and pytest regression checks for tracking, gust recovery, and actuator saturation.
- Automated response plots, JSON metrics, JUnit XML test results, and a compiled LaTeX PDF.
- GitHub Actions execution of the MATLAB simulation and Python validation on pushes, pull requests, and manual runs.

## Requirements

- MATLAB R2021a or newer for the simulation.
- Python 3.10 or newer.
- TeX Live with `pdflatex` to compile the PDF report. Use `--no-pdf` to generate its source, plots, and metrics without TeX.

The public GitHub Actions workflow uses MathWorks' MATLAB setup and run-command actions. MathWorks' public-project licensing path applies to public repositories; private repositories need a configured MATLAB batch licensing token.

## Run locally

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
matlab -batch "run('matlab/run_scenarios.m')"
pytest --junitxml=artifacts/test-results.xml
python -m wind_validation.report
```

To build report source and plots without compiling the PDF:

```powershell
python -m wind_validation.report --no-pdf
```

MATLAB writes one CSV per scenario to `artifacts/raw/`. The Python validation suite reads those files; the report command writes plots, `metrics_summary.json`, LaTeX source, and the PDF under `artifacts/report/`.

## Scenarios and acceptance criteria

The simulation uses a fixed 0.02-second time step, a 12 rpm rated-speed target, pitch travel from 0 to 30 degrees, and a maximum pitch rate of 8 degrees per second.

| Scenario | Input | Validation |
| --- | --- | --- |
| Tracking | Wind steps from 10 to 13 m/s at 5 s | Final tracking error ≤ 2%; overshoot ≤ 10%; settling within 20 s |
| Gust | Wind rises from 11 to 14 m/s between 25 and 30 s | Peak deviation ≤ 30% of rated speed; return to pre-gust speed within 10 s |
| Saturation | Wind ramps from 10 to 18 m/s between 5 and 10 s, holds until 25 s, then ramps down by 30 s | Overshoot ≤ 25%; pitch stays within travel/rate limits and reaches its upper travel limit |

All scenarios also check pitch travel and rate limits. pytest exits nonzero on a failed acceptance check, so CI marks a regression run as failed while still uploading available artifacts.

In `metrics_summary.json`, `steady_state_reference` names the reference used for `steady_state_error_pct` (`rated_speed` for tracking and `pre_gust_speed` for gust). The saturation case is a transient actuator-limit test, so its steady-state reference and error are `null`; use its overshoot and actuator metrics instead. Gust recovery time is reported separately from tracking settling time.

## Report outputs

- `artifacts/raw/*.csv`: MATLAB simulation traces.
- `artifacts/test-results.xml`: pytest results in JUnit format.
- `artifacts/report/metrics_summary.json`: machine-readable response metrics.
- `artifacts/report/*.png`: wind, rotor-speed, and pitch plots.
- `artifacts/report/report.tex` and `report.pdf`: report source and compiled report.

## Model limitations

The rotor plant maps wind speed to a cubic free-running rotor-speed target and models pitch as a linear speed-reduction effect. Wind feed-forward uses that simplified plant map to anticipate required pitch. The simulation does not model blade aerodynamics, structural loads, drivetrain flexibility, sensor noise, grid interaction, or safety systems. Parameters and thresholds are illustrative and should not be used to predict a real turbine's performance.
