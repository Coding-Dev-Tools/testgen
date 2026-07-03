Automated improvement by dev-engineer.

**Changes:**
- Fix `ast.Index` handling in analyzer.py (deprecated in Python 3.9+, removed in 3.10+)
- Update `_get_decorators` to accept `ast.ClassDef` for class decorators
- Add `hasattr` checks for `sys.stdout/stderr.reconfigure` on Windows

**Verification:**
- All 67 tests pass
- mypy: Success (no issues found in 6 source files)
- ruff: All checks passed
- Coverage: 79% (same as before)