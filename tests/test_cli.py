"""Tests for the testgen CLI."""


import pytest
from click.testing import CliRunner

from testgen.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sample_project(tmp_path):
    """Create a minimal Python project with source code."""
    src_dir = tmp_path / "src" / "myapp"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "service.py").write_text(
        'class Service:\n    def __init__(self, name: str): pass\n    def run(self) -> bool:\n        return True\n\ndef helper(x: int) -> int:\n    return x * 2\n',
        encoding="utf-8",
    )
    return tmp_path


class TestCLIGenerate:
    def test_generate_dry_run(self, runner, sample_project):
        result = runner.invoke(cli, ["generate", str(sample_project), "--dry-run"])
        assert result.exit_code == 0
        assert "test_" in result.output

    def test_generate_writes_file(self, runner, sample_project, tmp_path):
        output_dir = tmp_path / "output"
        result = runner.invoke(cli, ["generate", str(sample_project), "-o", str(output_dir)])
        assert result.exit_code == 0
        assert "Wrote" in result.output
        # Check file was created
        written_files = list(output_dir.glob("test_*.py"))
        assert len(written_files) > 0

    def test_generate_no_overwrite(self, runner, sample_project, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True)
        (output_dir / "test_service.py").write_text("existing", encoding="utf-8")
        result = runner.invoke(cli, ["generate", str(sample_project), "-o", str(output_dir)])
        assert "Skipping" in result.output or "overwrite" in result.output.lower()

    def test_generate_overwrite(self, runner, sample_project, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True)
        (output_dir / "test_service.py").write_text("existing", encoding="utf-8")
        result = runner.invoke(cli, ["generate", str(sample_project), "-o", str(output_dir), "--overwrite"])
        assert result.exit_code == 0
        assert "Wrote" in result.output

    def test_generate_max_tests(self, runner, sample_project):
        result = runner.invoke(cli, ["generate", str(sample_project), "--dry-run", "--max-tests", "1"])
        assert result.exit_code == 0

    def test_generate_fixture_style_class(self, runner, sample_project):
        result = runner.invoke(cli, ["generate", str(sample_project), "--dry-run", "--fixture-style", "class"])
        assert result.exit_code == 0
        assert "@pytest.fixture" in result.output

    def test_generate_fixture_style_both(self, runner, sample_project):
        result = runner.invoke(cli, ["generate", str(sample_project), "--dry-run", "--fixture-style", "both"])
        assert result.exit_code == 0
        assert "@pytest.fixture" in result.output
        assert "test_Service_instantiation" in result.output

    def test_generate_hypothesis(self, runner, sample_project):
        result = runner.invoke(cli, ["generate", str(sample_project), "--dry-run", "--hypothesis"])
        assert result.exit_code == 0
        assert "@given" in result.output

    def test_generate_diff_no_git(self, runner, sample_project):
        """--diff on non-git dir should still work (falls through to all files)."""
        result = runner.invoke(cli, ["generate", str(sample_project), "--dry-run", "--diff"])
        assert result.exit_code == 0
        # Without git, diff returns empty → all files are processed
        assert "test_" in result.output


class TestCLIScan:
    def test_scan_finds_units(self, runner, sample_project):
        result = runner.invoke(cli, ["scan", str(sample_project)])
        assert result.exit_code == 0
        assert "Service" in result.output
        assert "helper" in result.output

    def test_scan_empty_dir(self, runner, tmp_path):
        result = runner.invoke(cli, ["scan", str(tmp_path)])
        assert "No Python source files" in result.output


class TestCLICoverageGaps:
    def test_coverage_gaps_finds_untested(self, runner, sample_project):
        result = runner.invoke(cli, ["coverage-gaps", str(sample_project)])
        assert result.exit_code == 0
        assert "untested" in result.output.lower() or "gap" in result.output.lower()

    def test_coverage_gaps_empty_project(self, runner, tmp_path):
        result = runner.invoke(cli, ["coverage-gaps", str(tmp_path)])
        assert "No Python source files" in result.output
