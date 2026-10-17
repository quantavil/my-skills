"""Pytest suite verifying all Typer CLI commands via CliRunner."""

import os
import pytest
from typer.testing import CliRunner
from scripts.cli import app

runner = CliRunner()
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_cli_validate_command():
    result = runner.invoke(app, ["validate", os.path.join(FIXTURES_DIR, "official_gstn_gstr1.json")])
    assert result.exit_code == 0
    assert "Validation PASSED" in result.stdout


def test_cli_reconcile_command():
    pr_file = "examples/sample_purchase_register.json"
    g2b_file = "examples/sample_gstr2b.json"
    result = runner.invoke(app, ["reconcile-cmd", pr_file, g2b_file, "--fast"])
    assert result.exit_code == 0
    assert "polars+rapidfuzz" in result.stdout


def test_cli_pdf_to_images_command(tmp_path):
    # Run against fixtures dir
    out_dir = str(tmp_path / "img_out")
    result = runner.invoke(app, ["pdf-to-images-cmd", FIXTURES_DIR, "--output-dir", out_dir, "--dpi", "150"])
    assert result.exit_code == 0


def test_cli_pipeline_command(tmp_path):
    sales = "examples/sample_sales_register.json"
    purchases = "examples/sample_purchase_register.json"
    gstr2b = "examples/sample_gstr2b.json"
    out_dir = str(tmp_path / "pipe_out")

    result = runner.invoke(app, [
        "pipeline",
        "--sales", sales,
        "--purchases", purchases,
        "--gstr2b", gstr2b,
        "--output-dir", out_dir
    ])
    assert result.exit_code == 0
    assert os.path.exists(os.path.join(out_dir, "GSTR1_portal.json"))
    assert os.path.exists(os.path.join(out_dir, "GSTR3B_portal.json"))
    assert os.path.exists(os.path.join(out_dir, "gstr1-filing-pack.md"))
    assert os.path.exists(os.path.join(out_dir, "gstr3b-filing-pack.md"))
