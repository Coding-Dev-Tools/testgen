"""Tests for the test code generator module."""

from pathlib import Path

import pytest

from testgen.analyzer import analyze_file
from testgen.generator import GeneratorConfig, PytestStubGenerator, generate_test

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_python_file(tmp_path):
    """Create a temporary Python file with given content."""

    def _make(content: str, name: str = "sample.py") -> Path:
        # Create a proper src/package structure for module name resolution
        pkg_dir = tmp_path / "src" / "mypackage"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
        f = pkg_dir / name
        f.write_text(content, encoding="utf-8")
        return f

    return _make


# ── Basic generation ─────────────────────────────────────────────────────────


class TestBasicGeneration:
    def test_generates_test_for_function(self, tmp_python_file):
        path = tmp_python_file("def add(a: int, b: int) -> int:\n    return a + b")
        module = analyze_file(path)
        code = generate_test(module)
        assert "def test_add_" in code
        assert "import pytest" in code

    def test_generates_import_for_source(self, tmp_python_file):
        path = tmp_python_file("def hello(): pass")
        module = analyze_file(path)
        code = generate_test(module)
        assert "from mypackage.sample import" in code

    def test_empty_module(self, tmp_python_file):
        path = tmp_python_file("")
        module = analyze_file(path)
        code = generate_test(module)
        assert "No testable units" in code

    def test_header_comment(self, tmp_python_file):
        path = tmp_python_file("def func(): pass")
        module = analyze_file(path)
        code = generate_test(module)
        assert "Auto-generated tests" in code


# ── Function test generation ─────────────────────────────────────────────────


class TestFunctionTestGeneration:
    def test_basic_call_test(self, tmp_python_file):
        path = tmp_python_file("def greet(name: str) -> str:\n    return f'Hello {name}'")
        module = analyze_file(path)
        code = generate_test(module)
        assert "test_greet_runs" in code

    def test_return_type_test(self, tmp_python_file):
        path = tmp_python_file("def get_count() -> int:\n    return 0")
        module = analyze_file(path)
        code = generate_test(module)
        assert "test_get_count_return_type" in code
        assert "isinstance" in code

    def test_none_input_test(self, tmp_python_file):
        path = tmp_python_file("def func(required: str, optional: str = None):\n    pass")
        module = analyze_file(path)
        code = generate_test(module)
        assert "test_func_none_inputs" in code

    def test_edge_case_test(self, tmp_python_file):
        path = tmp_python_file("def process(count: int) -> int:\n    return count * 2")
        module = analyze_file(path)
        config = GeneratorConfig(include_edge_cases=True)
        generator = PytestStubGenerator(config)
        code = generator.generate(module)
        assert "test_process_edge_cases" in code

    def test_max_tests_per_func_limit(self, tmp_python_file):
        path = tmp_python_file("def func(a: int, b: str = '') -> int:\n    return a")
        module = analyze_file(path)
        config = GeneratorConfig(max_tests_per_func=2)
        generator = PytestStubGenerator(config)
        code = generator.generate(module)
        test_count = code.count("def test_func_")
        assert test_count <= 2


# ── Class test generation ────────────────────────────────────────────────────


class TestClassTestGeneration:
    def test_class_instantiation_test(self, tmp_python_file):
        path = tmp_python_file("class Service:\n    def __init__(self, name: str): pass\n    def run(self): pass")
        module = analyze_file(path)
        code = generate_test(module)
        assert "test_Service_instantiation" in code

    def test_method_tests_generated(self, tmp_python_file):
        path = tmp_python_file("class Calc:\n    def add(self, a: int, b: int) -> int:\n        return a + b")
        module = analyze_file(path)
        code = generate_test(module)
        assert "test_Calc_add" in code

    def test_abstract_class_no_instantiation(self, tmp_python_file):
        content = """
from abc import ABC, abstractmethod
class Base(ABC):
    @abstractmethod
    def required(self): pass
"""
        path = tmp_python_file(content)
        module = analyze_file(path)
        code = generate_test(module)
        assert "test_Base_instantiation" not in code

    def test_staticmethod_test(self, tmp_python_file):
        path = tmp_python_file("class Util:\n    @staticmethod\n    def parse(s: str) -> dict:\n        return {}")
        module = analyze_file(path)
        code = generate_test(module)
        assert "Util.parse" in code

    def test_classmethod_test(self, tmp_python_file):
        path = tmp_python_file(
            "class Config:\n    @classmethod\n    def from_env(cls) -> 'Config':\n        return cls()"
        )
        module = analyze_file(path)
        code = generate_test(module)
        assert "Config.from_env" in code


# ── Config options ───────────────────────────────────────────────────────────


class TestGeneratorConfig:
    def test_disable_edge_cases(self, tmp_python_file):
        path = tmp_python_file("def func(count: int): pass")
        module = analyze_file(path)
        config = GeneratorConfig(include_edge_cases=False)
        generator = PytestStubGenerator(config)
        code = generator.generate(module)
        assert "edge_cases" not in code

    def test_disable_none_checks(self, tmp_python_file):
        path = tmp_python_file("def func(a: str = None): pass")
        module = analyze_file(path)
        config = GeneratorConfig(include_none_checks=False)
        generator = PytestStubGenerator(config)
        code = generator.generate(module)
        assert "none_inputs" not in code

    def test_disable_type_validation(self, tmp_python_file):
        path = tmp_python_file("def func() -> int:\n    return 0")
        module = analyze_file(path)
        config = GeneratorConfig(include_type_validation=False)
        generator = PytestStubGenerator(config)
        code = generator.generate(module)
        assert "return_type" not in code

    def test_disable_docstring_tests(self, tmp_python_file):
        path = tmp_python_file('def func():\n    """Docstring."""\n    pass')
        module = analyze_file(path)
        config = GeneratorConfig(include_docstring_tests=False)
        generator = PytestStubGenerator(config)
        code = generator.generate(module)
        assert "docstring_example" not in code

    def test_no_header(self, tmp_python_file):
        path = tmp_python_file("def func(): pass")
        module = analyze_file(path)
        config = GeneratorConfig(header_comment=False)
        generator = PytestStubGenerator(config)
        code = generator.generate(module)
        assert "Auto-generated" not in code


# ── Fixture style generation ────────────────────────────────────────────────


class TestFixtureStyle:
    def test_function_style_no_fixtures(self, tmp_python_file):
        """Default function style should not generate @pytest.fixture."""
        path = tmp_python_file("class Service:\n def __init__(self, name: str): pass\n def run(self): pass")
        module = analyze_file(path)
        config = GeneratorConfig(fixture_style="function")
        generator = PytestStubGenerator(config)
        code = generator.generate(module)
        assert "@pytest.fixture" not in code
        assert "Service(...).run" in code

    def test_class_style_generates_fixture(self, tmp_python_file):
        """Class fixture style should generate @pytest.fixture for the class."""
        path = tmp_python_file("class Service:\n def __init__(self, name: str): pass\n def run(self): pass")
        module = analyze_file(path)
        config = GeneratorConfig(fixture_style="class")
        generator = PytestStubGenerator(config)
        code = generator.generate(module)
        assert "@pytest.fixture" in code
        assert "def service():" in code
        assert "return Service(" in code

    def test_class_style_method_uses_fixture(self, tmp_python_file):
        """Class fixture style: method calls use fixture name, not Class(...)."""
        path = tmp_python_file(
            "class Calc:\n    def __init__(self): pass\n    def add(self, a: int, b: int) -> int:\n        return a + b"
        )
        module = analyze_file(path)
        config = GeneratorConfig(fixture_style="class")
        generator = PytestStubGenerator(config)
        code = generator.generate(module)
        assert "calc.add" in code
        assert "Calc(...).add" not in code

    def test_both_style_generates_fixture_and_inline(self, tmp_python_file):
        """Both style should have fixture AND inline instantiation test."""
        path = tmp_python_file("class Service:\n def __init__(self, url: str): pass\n def run(self): pass")
        module = analyze_file(path)
        config = GeneratorConfig(fixture_style="both")
        generator = PytestStubGenerator(config)
        code = generator.generate(module)
        assert "@pytest.fixture" in code
        assert "test_Service_instantiation" in code

    def test_abstract_class_no_fixture(self, tmp_python_file):
        """Abstract classes should not generate fixtures."""
        content = """
from abc import ABC, abstractmethod
class Base(ABC):
    @abstractmethod
    def required(self): pass
"""
        path = tmp_python_file(content)
        module = analyze_file(path)
        config = GeneratorConfig(fixture_style="class")
        generator = PytestStubGenerator(config)
        code = generator.generate(module)
        assert "@pytest.fixture" not in code


# ── Hypothesis property-based test generation ────────────────────────────────


class TestHypothesisGeneration:
    def test_hypothesis_disabled_by_default(self, tmp_python_file):
        """Hypothesis tests should not be generated by default."""
        path = tmp_python_file("def add(a: int, b: int) -> int:\n return a + b")
        module = analyze_file(path)
        code = generate_test(module)
        assert "@given" not in code
        assert "hypothesis" not in code

    def test_hypothesis_enabled_for_int_params(self, tmp_python_file):
        """Hypothesis test generated for function with int params."""
        path = tmp_python_file("def add(a: int, b: int) -> int:\n return a + b")
        module = analyze_file(path)
        config = GeneratorConfig(include_hypothesis=True, max_tests_per_func=10)
        generator = PytestStubGenerator(config)
        code = generator.generate(module)
        assert "@given" in code
        assert "st.integers()" in code
        assert "test_add_property_based" in code

    def test_hypothesis_str_param(self, tmp_python_file):
        """Hypothesis test generated for function with str params."""
        path = tmp_python_file("def process(name: str) -> str:\n return name.upper()")
        module = analyze_file(path)
        config = GeneratorConfig(include_hypothesis=True, max_tests_per_func=10)
        generator = PytestStubGenerator(config)
        code = generator.generate(module)
        assert "@given" in code
        assert "st.text()" in code

    def test_hypothesis_float_param(self, tmp_python_file):
        """Hypothesis test generated for function with float params."""
        path = tmp_python_file("def scale(x: float) -> float:\n return x * 2.0")
        module = analyze_file(path)
        config = GeneratorConfig(include_hypothesis=True, max_tests_per_func=10)
        generator = PytestStubGenerator(config)
        code = generator.generate(module)
        assert "@given" in code
        assert "st.floats" in code

    def test_hypothesis_no_untyped_params(self, tmp_python_file):
        """Hypothesis test NOT generated for function without typed params."""
        path = tmp_python_file("def func(x, y):\n pass")
        module = analyze_file(path)
        config = GeneratorConfig(include_hypothesis=True, max_tests_per_func=10)
        generator = PytestStubGenerator(config)
        code = generator.generate(module)
        assert "@given" not in code

    def test_hypothesis_includes_imports(self, tmp_python_file):
        """Hypothesis tests add hypothesis imports."""
        path = tmp_python_file("def add(a: int, b: int) -> int:\n return a + b")
        module = analyze_file(path)
        config = GeneratorConfig(include_hypothesis=True, max_tests_per_func=10)
        generator = PytestStubGenerator(config)
        code = generator.generate(module)
        assert "from hypothesis import given" in code
        assert "from hypothesis.strategies import st" in code
