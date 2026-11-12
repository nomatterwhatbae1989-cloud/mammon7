import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

V7_PATH = Path(__file__).resolve().parents[1] / "v7" / "mammon7_v7.py"

PLAN = "GOAL: demo\nDELIVERABLE: files\nSTEPS: none\nRISKS: none\nACCEPTANCE: files exist"

PACKAGE_OK = json.dumps({
    "files": [
        {"path": "README.md", "content": "# Demo\nHello.\n"},
        {"path": "notes.txt", "content": "some notes\n"},
    ]
})

PACKAGE_DUP = json.dumps({
    "files": [
        {"path": "README.md", "content": "first\n"},
        {"path": "README.md", "content": "second\n"},
        {"path": "notes.txt", "content": "notes\n"},
    ]
})


def run_v7_task(package_json: str) -> dict:
    """Run one full /task flow in a subprocess with a mocked mistral()."""
    tmp = tempfile.TemporaryDirectory()
    env = dict(os.environ)
    env["HOME"] = tmp.name
    env["MAMMON_AUTO_APPROVE"] = "1"
    env.pop("MISTRAL_API_KEY", None)
    code = f"""
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location('m7', {str(V7_PATH)!r})
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

responses = [{PLAN!r}, {package_json!r}]
calls = []
def fake_mistral(messages, max_tokens=1800):
    calls.append(messages)
    return responses[len(calls) - 1]
m.mistral = fake_mistral
m.run_task("Create a starter package with a README and notes")
out = {{
    "calls": len(calls),
    "tasks": sorted(p.name for p in m.TASKS.iterdir()),
    "outputs": sorted(p.name for p in m.OUTPUTS.iterdir()),
}}
print("RESULT_JSON:" + json.dumps(out))
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, env=env, timeout=60,
    )
    return {"tmp": tmp, "proc": proc}


class TestV71EndToEnd(unittest.TestCase):

    def _task_dir(self, result):
        return Path(result["tmp"].name) / "mammon7_v7" / "tasks"

    def _outputs_dir(self, result):
        return Path(result["tmp"].name) / "mammon7_v7" / "outputs"

    def test_end_to_end_package_passes_checks(self):
        result = run_v7_task(PACKAGE_OK)
        try:
            self.assertEqual(result["proc"].returncode, 0,
                             msg=result["proc"].stderr[-800:])
            task_dir = self._task_dir(result)
            task_name = next(iter(task_dir.iterdir())).name
            task = json.loads(
                (task_dir / task_name / "task.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                task["status"], "deliverable_created_automated_checks_passed"
            )
            self.assertTrue(task["deliverable_sha256"])

            report = json.loads(
                (task_dir / task_name / "verification_report.json")
                .read_text(encoding="utf-8")
            )
            results = {c["name"]: c["result"] for c in report["checks"]}
            self.assertEqual(results.get("files_written"), "PASS")
            self.assertEqual(results.get("nonempty_files"), "PASS")
            self.assertEqual(results.get("zip_integrity"), "PASS")
            self.assertTrue(report["manual_review_required"])

            package_dir = self._outputs_dir(result) / f"{task_name}_package"
            self.assertTrue((package_dir / "README.md").exists())
            self.assertTrue((package_dir / "notes.txt").exists())
            zip_path = self._outputs_dir(result) / f"{task_name}_package.zip"
            self.assertTrue(zip_path.exists())
        finally:
            result["tmp"].cleanup()

    def test_end_to_end_duplicate_paths_fail_checks(self):
        result = run_v7_task(PACKAGE_DUP)
        try:
            self.assertEqual(result["proc"].returncode, 0,
                             msg=result["proc"].stderr[-800:])
            task_dir = self._task_dir(result)
            task_name = next(iter(task_dir.iterdir())).name
            task = json.loads(
                (task_dir / task_name / "task.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                task["status"], "deliverable_created_verification_failed"
            )
            report = json.loads(
                (task_dir / task_name / "verification_report.json")
                .read_text(encoding="utf-8")
            )
            files_check = next(
                c for c in report["checks"] if c["name"] == "files_written"
            )
            self.assertEqual(files_check["result"], "FAIL")
            self.assertTrue(
                any("Duplicate file path" in e for e in files_check["errors"]),
                msg=str(files_check["errors"]),
            )
            self.assertEqual(files_check["count"], 2)
            package_dir = self._outputs_dir(result) / f"{task_name}_package"
            readme = (package_dir / "README.md").read_text(encoding="utf-8")
            self.assertEqual(readme, "first\n")
            self.assertFalse(
                (self._outputs_dir(result) / f"{task_name}_package.zip").exists()
            )
        finally:
            result["tmp"].cleanup()

    def test_end_to_end_invalid_json_fails_gracefully(self):
        result = run_v7_task("this is not json at all")
        try:
            self.assertEqual(result["proc"].returncode, 0,
                             msg=result["proc"].stderr[-800:])
            task_dir = self._task_dir(result)
            task_name = next(iter(task_dir.iterdir())).name
            task = json.loads(
                (task_dir / task_name / "task.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                task["status"], "deliverable_created_verification_failed"
            )
            report = json.loads(
                (task_dir / task_name / "verification_report.json")
                .read_text(encoding="utf-8")
            )
            self.assertEqual(report["checks"][0]["name"], "structured_json")
            self.assertEqual(report["checks"][0]["result"], "FAIL")
            fallback = (
                self._outputs_dir(result) / f"{task_name}_deliverable.md"
            )
            self.assertTrue(fallback.exists())
        finally:
            result["tmp"].cleanup()


if __name__ == "__main__":
    unittest.main()
