"""Tests for the AST analyzer module."""

from pathlib import Path

import pytest

from testgen.analyzer import analyze_file

# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_python_file(tmp_path):
    """Create a temporary Python file with given content."""
    def _make(content: str, name: str = "sample.py") -> Path:
        f = tmp_path / name
        f.write_text(content, encoding="utf-8")
        return f
    return _make


# ── Function parsing ─────────────────────────────────────────────────────────

class TestAnalyzeFunction:
    def test_simple_function(self, tmp_python_file):
        path = tmp_python_file("def hello(): pass")
        module = analyze_file(path)
        assert len(module.functions) == 1
        assert module.functions[0].name == "hello"
        assert module.functions[0].kind == "function"

    def test_function_with_params(self, tmp_python_file):
        path = tmp_python_file("def greet(name: str, count: int = 1) -> str:\n    return name")
        module = analyze_file(path)
        func = module.functions[0]
        assert func.name == "greet"
        assert len(func.params) == 2
        assert func.params[0].name == "name"
        assert func.params[0].annotation == "str"
        assert func.params[0].default is None
        assert func.params[1].name == "count"
        assert func.params[1].annotation == "int"
        assert func.params[1].default == "1"
        assert func.return_annotation == "str"

    def test_function_with_kwargs(self, tmp_python_file):
        path = tmp_python_file("def func(*args, **kwargs): pass")
        module = analyze_file(path)
        func = module.functions[0]
        assert any(p.is_var_positional for p in func.params)
        assert any(p.is_var_keyword for p in func.params)

    def test_private_function_excluded_by_default(self, tmp_python_file):
        path = tmp_python_file("def _private(): pass\ndef public(): pass")
        module = analyze_file(path)
        assert len(module.functions) == 1
        assert module.functions[0].name == "public"

    def test_private_function_included_when_configured(self, tmp_python_file):
        path = tmp_python_file("def _private(): pass\ndef public(): pass")
        module = analyze_file(path, include_private=True)
        assert len(module.functions) == 2

    def test_function_docstring(self, tmp_python_file):
        path = tmp_python_file('def documented():\n    """This is documented."""\n    pass')
        module = analyze_file(path)
        assert module.functions[0].docstring == "This is documented."

    def test_async_function(self, tmp_python_file):
        path = tmp_python_file("async def fetch(): pass")
        module = analyze_file(path)
        assert module.functions[0].name == "fetch"


# ── Class parsing ────────────────────────────────────────────────────────────

class TestAnalyzeClass:
    def test_simple_class(self, tmp_python_file):
        path = tmp_python_file("class Foo:\n    def bar(self): pass")
        module = analyze_file(path)
        assert len(module.classes) == 1
        assert module.classes[0].name == "Foo"
        assert len(module.classes[0].methods) == 1

    def test_class_with_bases(self, tmp_python_file):
        path = tmp_python_file("class Foo(Bar, Baz):\n    pass")
        module = analyze_file(path)
        assert module.classes[0].bases == ["Bar", "Baz"]

    def test_class_method_kinds(self, tmp_python_file):
        content = """
class MyClass:
    def regular(self): pass
    @staticmethod
    def static_func(): pass
    @classmethod
    def class_func(cls): pass
"""
        path = tmp_python_file(content)
        module = analyze_file(path)
        cls = module.classes[0]
        assert cls.methods[0].kind == "method"
        assert cls.methods[1].kind == "staticmethod"
        assert cls.methods[2].kind == "classmethod"

    def test_abstract_class(self, tmp_python_file):
        content = """
from abc import ABC, abstractmethod
class Base(ABC):
    @abstractmethod
    def required(self): pass
    def optional(self): pass
"""
        path = tmp_python_file(content)
        module = analyze_file(path)
        cls = module.classes[0]
        assert cls.is_abstract is True
        assert cls.methods[0].is_abstract is True
        assert cls.methods[1].is_abstract is False

    def test_dataclass_detection(self, tmp_python_file):
        content = """
from dataclasses import dataclass
@dataclass
class Point:
    x: int
    y: int
"""
        path = tmp_python_file(content)
        module = analyze_file(path)
        assert module.classes[0].is_dataclass is True


# ── Module-level ─────────────────────────────────────────────────────────────

class TestAnalyzeModule:
    def test_module_docstring(self, tmp_python_file):
        path = tmp_python_file('"""Module docstring."""\n\ndef func(): pass')
        module = analyze_file(path)
        assert module.docstring == "Module docstring."

    def test_module_imports(self, tmp_python_file):
        path = tmp_python_file("import os\nfrom pathlib import Path\n\ndef func(): pass")
        module = analyze_file(path)
        assert len(module.imports) >= 2

    def test_empty_file(self, tmp_python_file):
        path = tmp_python_file("")
        module = analyze_file(path)
        assert len(module.functions) == 0
        assert len(module.classes) == 0

    def test_syntax_error_handled(self, tmp_python_file):
        path = tmp_python_file("def broken(:")
        with pytest.raises(SyntaxError):
            analyze_file(path)
