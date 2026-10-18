"""Generate plots, machine-readable metrics, LaTeX, and a PDF report."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .metrics import calculate_metrics, read_trace


def _plot_scenario(name: str, trace, output: Path) -> None:
    figure, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True, constrained_layout=True)
    axes[0].plot(trace.time_s, trace.wind_mps, color="#4472C4", linewidth=1.5)
    axes[0].set_ylabel("Wind (m/s)")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(trace.time_s, trace.rotor_speed_rpm, label="Rotor speed", color="#ED7D31")
    axes[1].plot(trace.time_s, trace.rated_speed_rpm, "--", label="Rated speed", color="#555555")
    axes[1].set_ylabel("Speed (rpm)")
    axes[1].legend(loc="best")
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(trace.time_s, trace.pitch_angle_deg, label="Pitch angle", color="#70AD47")
    axes[2].plot(trace.time_s, trace.pitch_command_deg, ":", label="Pitch command", color="#8064A2")
    axes[2].set_ylabel("Pitch (deg)")
    axes[2].set_xlabel("Time (s)")
    axes[2].legend(loc="best")
    axes[2].grid(True, alpha=0.3)

    figure.suptitle(f"{name.title()} scenario")
    figure.savefig(output, dpi=160)
    plt.close(figure)


def _format(value: float | None, unit: str = "") -> str:
    return "N/A" if value is None else f"{value:.2f}{unit}"


def _write_latex(metrics: list, output: Path) -> None:
    lines = [
        r"\documentclass[11pt]{article}",
        r"\usepackage[margin=1in]{geometry}",
        r"\usepackage{graphicx}",
        r"\usepackage{float}",
        r"\title{Wind Turbine Controller Validation Report}",
        r"\author{Automated validation framework}",
        r"\date{\today}",
        r"\begin{document}",
        r"\maketitle",
        r"\section{Purpose}",
        "This report summarizes deterministic simulation scenarios for a simplified rotor-speed pitch controller. "
        "The model is an educational validation example, not an industrial turbine model.",
        r"\section{Results}",
        r"\begin{tabular}{lrrrrrrr}",
        r"Scenario & Ref. error (\%) & Overshoot (\%) & Settle (s) & Recover (s) & Peak dev. (\%) & Max pitch (deg) & Max speed (rpm) \\",
        r"\hline",
    ]
    for item in metrics:
        reference = item.steady_state_reference or "N/A"
        lines.append(
            f"{item.scenario.title()} ({reference.replace('_', ' ')}) & "
            f"{_format(item.steady_state_error_pct)} & "
            f"{item.overshoot_pct:.2f} & {_format(item.settling_time_s)} & "
            f"{_format(item.recovery_time_s)} & "
            f"{item.peak_speed_deviation_pct:.2f} & {item.max_pitch_deg:.2f} & "
            f"{item.max_speed_rpm:.2f} " + r"\\"
        )
    lines.extend([
        r"\end{tabular}",
        r"\section{Scenario responses}",
    ])
    for item in metrics:
        lines.extend([
            r"\begin{figure}[H]",
            r"\centering",
            rf"\includegraphics[width=0.92\linewidth]{{{item.scenario}.png}}",
            rf"\caption{{Wind, rotor speed, and pitch response for the {item.scenario} scenario.}}",
            r"\end{figure}",
        ])
    lines.extend([
        r"\section{Interpretation}",
        "Acceptance thresholds are checked by pytest and the corresponding JUnit XML is preserved with this report. "
        "CSV traces and a JSON metrics summary are included as build artifacts for review.",
        r"\end{document}",
    ])
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_report(input_dir: Path, output_dir: Path, compile_pdf: bool = True) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    scenario_paths = sorted(input_dir.glob("*.csv"))
    if not scenario_paths:
        raise FileNotFoundError(f"No scenario CSV files found in {input_dir}")

    results = []
    for path in scenario_paths:
        name = path.stem
        trace = read_trace(path)
        result = calculate_metrics(name, trace)
        results.append(result)
        _plot_scenario(name, trace, figures_dir / f"{name}.png")

    summary_path = output_dir / "metrics_summary.json"
    summary_path.write_text(
        json.dumps([item.to_dict() for item in results], indent=2) + "\n", encoding="utf-8"
    )
    # Keep images beside the .tex file so LaTeX paths stay simple.
    for image in figures_dir.glob("*.png"):
        shutil.copy2(image, output_dir / image.name)
    tex_path = output_dir / "report.tex"
    _write_latex(results, tex_path)

    if compile_pdf:
        pdflatex = shutil.which("pdflatex")
        if pdflatex is None:
            raise RuntimeError("pdflatex is required to build the PDF; install TeX Live or pass --no-pdf")
        for _ in range(2):
            subprocess.run(
                [pdflatex, "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
                cwd=output_dir,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
    return tex_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("artifacts/raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/report"))
    parser.add_argument("--no-pdf", action="store_true", help="write plots, JSON, and LaTeX only")
    args = parser.parse_args()
    tex_path = build_report(args.input_dir, args.output_dir, compile_pdf=not args.no_pdf)
    print(f"Wrote report source: {tex_path}")


if __name__ == "__main__":
    main()
