"""Guards against the 'missing return True' defect class in validate_record().

A past code-repair batch shipped a validate_record() whose final
`return True` was missing, so every valid record was silently rejected
(function fell through to an implicit None). These tests make MAMMON's
own suite responsible for catching that class of defect:

1. Structural check: validate_record() must end with an explicit
   `return True` statement.
2. Mutation check: a mutant with the final `return True` removed is
   created and executed; the suite asserts the mutant misbehaves,
   proving the behavioral tests are sensitive to this exact defect.
"""
import ast
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

MODULES = [
    ("revenue.py", "RevenueEngine", "src.revenue"),
    ("expenses.py", "ExpenseEngine", "src.expenses"),
    ("fees.py", "FeeEngine", "src.fees"),
    ("refunds.py", "RefundEngine", "src.refunds"),
]


def find_validate_method(source: str, class_name: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "validate_record":
                    return item
    raise AssertionError(f"validate_record not found in {class_name}")


def load_mutated_validate(module_file: str, class_name: str):
    """Load validate_record from a copy of the module with the final
    `return True` removed. Returns the mutated engine class."""
    source = (SRC / module_file).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "validate_record":
                    last = item.body[-1]
                    if (isinstance(last, ast.Return)
                            and isinstance(last.value, ast.Constant)
                            and last.value.value is True):
                        item.body.pop()
    mutated_src = ast.unparse(tree)
    with tempfile.TemporaryDirectory() as tmp:
        pkg = Path(tmp) / "mutatedpkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "core.py").write_text(
            (SRC / "core.py").read_text(encoding="utf-8"), encoding="utf-8"
        )
        target = module_file.replace(".py", "_mutated.py")
        (pkg / target).write_text(mutated_src, encoding="utf-8")
        parent = types.ModuleType("mutatedpkg")
        parent.__path__ = [str(pkg)]
        sys.modules["mutatedpkg"] = parent
        spec = importlib.util.spec_from_file_location(
            f"mutatedpkg.{target[:-3]}", pkg / target
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop(spec.name, None)
            sys.modules.pop("mutatedpkg", None)
        return getattr(module, class_name)


class TestValidateRecordStructure(unittest.TestCase):
    """The final statement of validate_record() must be `return True`."""

    def test_validate_record_ends_with_explicit_return_true(self):
        for module_file, class_name, _ in MODULES:
            with self.subTest(module=module_file):
                source = (SRC / module_file).read_text(encoding="utf-8")
                method = find_validate_method(source, class_name)
                last = method.body[-1]
                self.assertIsInstance(last, ast.Return)
                self.assertIsInstance(last.value, ast.Constant)
                self.assertIs(last.value.value, True)

    def test_validate_record_declared_to_return_bool(self):
        for module_file, class_name, _ in MODULES:
            with self.subTest(module=module_file):
                source = (SRC / module_file).read_text(encoding="utf-8")
                method = find_validate_method(source, class_name)
                self.assertEqual(
                    method.returns.id if method.returns else None, "bool"
                )


class TestValidateRecordMutationDetection(unittest.TestCase):
    """Prove the suite detects the missing-`return True` defect.

    For each engine, a mutant with the final `return True` removed is
    executed. The mutant MUST reject a valid record (return a non-True
    value). If a future refactor makes the mutant behave correctly
    (e.g. the final return becomes unreachable), this test fails and
    forces a review of the guard.
    """

    def _valid_record(self, engine_cls):
        if hasattr(engine_cls, "create_record"):
            return engine_cls().create_record("guard-check", 42.0)
        if hasattr(engine_cls, "create_fee"):
            return engine_cls().create_fee("guard-check", 42.0)
        return engine_cls().create_refund("guard-check", 42.0)

    def test_mutant_without_return_true_is_detectable(self):
        for module_file, class_name, _ in MODULES:
            with self.subTest(module=module_file):
                mutated_cls = load_mutated_validate(module_file, class_name)
                valid = self._valid_record(mutated_cls)
                result = mutated_cls().validate_record(valid)
                self.assertIsNot(
                    result, True,
                    "Mutant with missing `return True` still returned True; "
                    "the defect would go undetected."
                )

    def test_real_validate_accepts_valid_record(self):
        from src.revenue import RevenueEngine
        from src.expenses import ExpenseEngine
        from src.fees import FeeEngine
        from src.refunds import RefundEngine
        for engine_cls in (RevenueEngine, ExpenseEngine, FeeEngine, RefundEngine):
            with self.subTest(engine=engine_cls.__name__):
                valid = self._valid_record(engine_cls)
                self.assertIs(engine_cls().validate_record(valid), True)


if __name__ == "__main__":
    unittest.main()
