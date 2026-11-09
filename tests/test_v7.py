import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

V7_PATH = Path(__file__).resolve().parents[1] / "v7" / "mammon7_v7.py"


def run_v7_snippet(code: str) -> dict:
    """Run code in a subprocess with HOME redirected to a temp dir."""
    tmp = tempfile.TemporaryDirectory()
    env = dict(os.environ)
    env["HOME"] = tmp.name
    env.pop("MISTRAL_API_KEY", None)
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, env=env, timeout=60,
    )
    return {"tmp": tmp, "proc": proc}


class TestV7Script(unittest.TestCase):

    def test_script_compiles(self):
        self.assertTrue(V7_PATH.exists())
        compile(V7_PATH.read_text(encoding="utf-8"), str(V7_PATH), "exec")

    def test_task_collision_no_crash(self):
        result = run_v7_snippet(
            "import importlib.util, io, json, sys\n"
            f"spec = importlib.util.spec_from_file_location('m7', {str(V7_PATH)!r})\n"
            "m = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(m)\n"
            "sys.stdin = io.StringIO('')\n"
            "m.run_task('goal A')\n"
            "sys.stdin = io.StringIO('')\n"
            "m.run_task('goal B')\n"
            "dirs = sorted(p.name for p in m.TASKS.iterdir())\n"
            "print(json.dumps(dirs))\n"
        )
        try:
            self.assertEqual(result["proc"].returncode, 0,
                             msg=result["proc"].stderr[-800:])
            tasks_root = Path(result["tmp"].name) / "mammon7_v7" / "tasks"
            dirs = sorted(p.name for p in tasks_root.iterdir())
            self.assertEqual(len(dirs), 2)
            self.assertNotEqual(dirs[0], dirs[1])
            for d in tasks_root.iterdir():
                task_json = d / "task.json"
                self.assertTrue(task_json.exists())
                data = json.loads(task_json.read_text(encoding="utf-8"))
                self.assertEqual(data["status"], "error")
        finally:
            result["tmp"].cleanup()

    def test_approval_eof_treated_as_no(self):
        result = run_v7_snippet(
            "import importlib.util, sys\n"
            f"spec = importlib.util.spec_from_file_location('m7', {str(V7_PATH)!r})\n"
            "m = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(m)\n"
            "try:\n"
            "    m.mistral([{'role':'user','content':'hi'}])\n"
            "except RuntimeError as e:\n"
            "    print('KEYLESS_OK')\n"
        )
        try:
            self.assertEqual(result["proc"].returncode, 0,
                             msg=result["proc"].stderr[-800:])
            self.assertIn("KEYLESS_OK", result["proc"].stdout)
        finally:
            result["tmp"].cleanup()


if __name__ == "__main__":
    unittest.main()
