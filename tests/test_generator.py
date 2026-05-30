"""Tests for the test code generator module."""

import pytest
from pathlib import Path
from testgen.analyzer import analyze_file, FuncInfo, ClassInfo, ParamInfo, ModuleInfo
from testgen.generator import PytestStubGenerator, GeneratorConfig, generate_test


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
        assert 'Auto-generated tests' in code


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
        path = tmp_python_file("class Config:\n    @classmethod\n    def from_env(cls) -> 'Config':\n        return cls()")
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
