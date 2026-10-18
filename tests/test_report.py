from __future__ import annotations

import csv
import json

from wind_validation.report import build_report


def test_report_generates_plots_latex_and_machine_readable_metrics(tmp_path):
    raw = tmp_path / "raw"
    report = tmp_path / "report"
    raw.mkdir()
    with (raw / "tracking.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "time_s", "wind_mps", "rotor_speed_rpm", "rated_speed_rpm",
            "pitch_command_deg", "pitch_angle_deg",
        ])
        for index in range(101):
            time = index * 0.02
            writer.writerow([time, 12, 12, 12, 0, 0])

    tex_path = build_report(raw, report, compile_pdf=False)

    assert tex_path.is_file()
    assert (report / "tracking.png").is_file()
    summary = json.loads((report / "metrics_summary.json").read_text(encoding="utf-8"))
    assert summary[0]["scenario"] == "tracking"
    assert "tracking.png" in tex_path.read_text(encoding="utf-8")
