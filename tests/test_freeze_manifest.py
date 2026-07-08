import json

from portfolio_case.freeze import freeze_run, verify_checksums


def test_freeze_manifest_and_checksums(tmp_path) -> None:
    run_dir = tmp_path / "runs" / "demo_test"
    report_dir = run_dir / "reports"
    report_dir.mkdir(parents=True)
    (report_dir / "demo_report.md").write_text("# Demo\n", encoding="utf-8")

    config = {
        "run": {"output_root": "runs", "run_id_prefix": "demo"},
        "synthetic": {"random_seed": 1},
    }
    validations = [{"name": "example", "passed": True, "detail": "ok"}]
    manifest = freeze_run(
        run_dir=run_dir,
        project_root=tmp_path,
        run_id="demo_test",
        config=config,
        stages=["example"],
        row_counts={"example": 1},
        validations=validations,
    )

    manifest_path = run_dir / "frozen" / "manifest.json"
    checksums_path = run_dir / "frozen" / "checksums.json"
    assert manifest_path.exists()
    assert checksums_path.exists()
    assert manifest["validation_status"] == "passed"

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    checksums = json.loads(checksums_path.read_text(encoding="utf-8"))
    assert "reports/demo_report.md" in manifest_data["produced_artefacts"]
    assert "reports/demo_report.md" in checksums
    assert verify_checksums(run_dir)
