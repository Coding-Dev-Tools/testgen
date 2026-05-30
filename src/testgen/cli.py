"""testgen CLI — automated test generator for Python projects."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .analyzer import ModuleAnalyzer, analyze_file
from .generator import GeneratorConfig, PytestStubGenerator, generate_test

console = Console()

# ── Helpers ──────────────────────────────────────────────────────────────────


def _find_python_files(target: Path, recursive: bool = True) -> list[Path]:
    """Discover Python source files under a target path."""
    if target.is_file() and target.suffix == ".py":
        return [target]

    pattern = "**/*.py" if recursive else "*.py"
    files = sorted(f for f in target.glob(pattern) if _is_source_file(f))
    return files


def _is_source_file(path: Path) -> bool:
    """Check if a file looks like a source file (not a test, __pycache__, etc.)."""
    parts = path.parts
    # Skip test files themselves
    if path.name.startswith("test_") or path.name.endswith("_test.py"):
        return False
    # Skip __pycache__, .venv, node_modules
    for part in parts:
        if part in ("__pycache__", ".venv", "venv", "node_modules", ".git", ".tox", ".mypy_cache", ".ruff_cache"):
            return False
    # Skip conftest
    if path.name == "conftest.py":
        return False
    # Skip setup.py
    if path.name == "setup.py":
        return False
    return True


def _compute_test_path(source_path: Path, project_root: Path | None = None) -> Path:
    """Compute where the generated test file should go."""
    # Convention: src/package/module.py → tests/test_module.py
    parts = source_path.with_suffix("").parts

    # Find 'src' boundary
    src_idx = None
    for i, part in enumerate(parts):
        if part == "src":
            src_idx = i
            break

    if src_idx is not None and src_idx + 2 < len(parts):
        # src/package/module → tests/test_module.py
        module_name = parts[-1]
        return Path("tests") / f"test_{module_name}.py"
    else:
        # Fallback: same directory
        return source_path.parent / f"test_{source_path.stem}.py"


# ── Commands ─────────────────────────────────────────────────────────────────


@click.group()
@click.version_option()
def cli():
    """testgen — automated pytest test generator."""
    pass


@cli.command()
@click.argument("target", type=click.Path(exists=True, path_type=Path))
@click.option("--recursive/--no-recursive", default=True, help="Recursively scan directories.")
@click.option("--include-private/--no-include-private", default=False, help="Include private members.")
@click.option("--include-dunder/--no-include-dunder", default=False, help="Include __dunder__ methods.")
@click.option("--max-tests", default=6, help="Max tests per function.", type=int)
@click.option("--edge-cases/--no-edge-cases", default=True, help="Generate edge-case tests.")
@click.option("--none-checks/--no-none-checks", default=True, help="Generate None-input tests.")
@click.option("--type-validation/--no-type-validation", default=True, help="Generate return-type tests.")
@click.option("--docstring-tests/--no-docstring-tests", default=True, help="Generate docstring-based tests.")
@click.option("--output", "-o", type=click.Path(path_type=Path), default=None, help="Output directory for test files.")
@click.option("--overwrite/--no-overwrite", default=False, help="Overwrite existing test files.")
@click.option("--dry-run/--no-dry-run", default=False, help="Print generated tests without writing.")
def generate(
    target: Path,
    recursive: bool,
    include_private: bool,
    include_dunder: bool,
    max_tests: int,
    edge_cases: bool,
    none_checks: bool,
    type_validation: bool,
    docstring_tests: bool,
    output: Path | None,
    overwrite: bool,
    dry_run: bool,
):
    """Generate pytest test stubs for Python source files."""
    files = _find_python_files(target, recursive)
    if not files:
        console.print("[yellow]No Python source files found.[/yellow]")
        return

    analyzer = ModuleAnalyzer(include_private=include_private, include_dunder=include_dunder)
    config = GeneratorConfig(
        include_edge_cases=edge_cases,
        include_none_checks=none_checks,
        include_type_validation=type_validation,
        include_docstring_tests=docstring_tests,
        max_tests_per_func=max_tests,
        overwrite=overwrite,
    )
    generator = PytestStubGenerator(config)

    total_tests = 0
    total_files = 0

    for src_file in files:
        try:
            module = analyzer.analyze_file(src_file)
        except SyntaxError as e:
            console.print(f"[red]Syntax error in {src_file}: {e}[/red]")
            continue

        test_code = generator.generate(module)
        test_count = test_code.count("def test_")

        if test_count == 0:
            console.print(f"[dim]{src_file.name} — no testable units found[/dim]")
            continue

        if dry_run:
            console.print(f"\n[bold]# {src_file.name} → {test_count} tests[/bold]\n")
            console.print(test_code)
        else:
            # Determine output path
            if output:
                out_path = output / f"test_{src_file.stem}.py"
            else:
                out_path = _compute_test_path(src_file)

            if out_path.exists() and not overwrite:
                console.print(f"[yellow]Skipping {out_path} (exists, use --overwrite)[/yellow]")
                continue

            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(test_code, encoding="utf-8")
            console.print(f"[green]Wrote {out_path} ({test_count} tests)[/green]")

        total_tests += test_count
        total_files += 1

    console.print(f"\n[bold]Summary:[/bold] {total_tests} tests generated across {total_files} files")


@cli.command()
@click.argument("target", type=click.Path(exists=True, path_type=Path))
@click.option("--recursive/--no-recursive", default=True)
@click.option("--include-private/--no-include-private", default=False)
def scan(target: Path, recursive: bool, include_private: bool):
    """Scan and display testable units found in Python files."""
    files = _find_python_files(target, recursive)
    if not files:
        console.print("[yellow]No Python source files found.[/yellow]")
        return

    analyzer = ModuleAnalyzer(include_private=include_private)

    total_funcs = 0
    total_classes = 0
    total_methods = 0

    for src_file in files:
        try:
            module = analyzer.analyze_file(src_file)
        except SyntaxError as e:
            console.print(f"[red]Syntax error in {src_file}: {e}[/red]")
            continue

        if not module.functions and not module.classes:
            continue

        table = Table(title=str(src_file), show_lines=True)
        table.add_column("Type", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Params", style="yellow")
        table.add_column("Returns", style="magenta")
        table.add_column("Line", justify="right")

        for func in module.functions:
            params = ", ".join(p.name for p in func.params if p.name not in ("self", "cls"))
            ret = func.return_annotation or "-"
            table.add_row("func", func.name, params or "-", ret, str(func.line_number))
            total_funcs += 1

        for cls in module.classes:
            table.add_row("class", cls.name, f"bases: {', '.join(cls.bases) or '-'}", "-", str(cls.line_number))
            total_classes += 1
            for method in cls.methods:
                params = ", ".join(p.name for p in method.params if p.name not in ("self", "cls"))
                ret = method.return_annotation or "-"
                table.add_row(f"  {method.kind}", method.name, params or "-", ret, str(method.line_number))
                total_methods += 1

        console.print(table)

    console.print(f"\n[bold]Totals:[/bold] {total_funcs} functions, {total_classes} classes, {total_methods} methods")


@cli.command()
@click.argument("target", type=click.Path(exists=True, path_type=Path))
@click.option("--recursive/--no-recursive", default=True)
@click.option("--include-private/--no-include-private", default=False)
def coverage_gaps(target: Path, recursive: bool, include_private: bool):
    """Find functions/classes with missing test coverage."""
    files = _find_python_files(target, recursive)
    if not files:
        console.print("[yellow]No Python source files found.[/yellow]")
        return

    analyzer = ModuleAnalyzer(include_private=include_private)
    gaps: list[tuple[Path, str, str]] = []

    for src_file in files:
        try:
            module = analyzer.analyze_file(src_file)
        except SyntaxError:
            continue

        # Check for corresponding test file
        test_path = _compute_test_path(src_file)
        existing_tests = set()
        if test_path.exists():
            test_content = test_path.read_text(encoding="utf-8")
            for line in test_content.splitlines():
                if line.strip().startswith("def test_"):
                    existing_tests.add(line.strip())

        for func in module.functions:
            expected_test = f"def test_{func.name}_"
            if not any(expected_test in t for t in existing_tests):
                gaps.append((src_file, "function", func.name))

        for cls in module.classes:
            for method in cls.methods:
                if method.is_abstract:
                    continue
                expected_test = f"test_{cls.name}_{method.name}"
                if not any(expected_test in t for t in existing_tests):
                    gaps.append((src_file, f"{cls.name}.method", method.name))

    if not gaps:
        console.print("[green]All testable units appear to have test coverage![/green]")
        return

    table = Table(title="Coverage Gaps")
    table.add_column("File", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Name", style="red")

    for path, kind, name in gaps:
        table.add_row(path.name, kind, name)

    console.print(table)
    console.print(f"\n[bold]{len(gaps)} untested units found[/bold]")


if __name__ == "__main__":
    cli()
