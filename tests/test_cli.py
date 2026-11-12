import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "mammon.py"


def run_cli(inputs: list, use_data_dir=None):
    tmp = tempfile.TemporaryDirectory()
    data_dir = use_data_dir or os.path.join(tmp.name, "data")
    env = dict(os.environ)
    env["HOME"] = tmp.name
    script = "\n".join(inputs) + "\nq\n"
    proc = subprocess.run(
        [sys.executable, str(CLI), "--data-dir", data_dir],
        input=script, capture_output=True, text=True, env=env, timeout=60,
    )
    return {"tmp": tmp, "proc": proc, "data_dir": data_dir}


class TestCliBasics(unittest.TestCase):

    def test_add_revenue_and_show_profit(self):
        result = run_cli([
            "1", "web-design", "150",
            "2", "software", "30",
            "6",
        ])
        try:
            self.assertEqual(result["proc"].returncode, 0,
                             msg=result["proc"].stderr[-800:])
            out = result["proc"].stdout
            self.assertIn("Recorded revenue", out)
            self.assertIn("Recorded expense", out)
            self.assertIn('"net_profit"', out)
            self.assertIn("SIMULATED", out)
            ledger = Path(result["data_dir"]) / "records.jsonl"
            self.assertTrue(ledger.exists())
            lines = ledger.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
        finally:
            result["tmp"].cleanup()

    def test_monthly_summary_and_invoice(self):
        result = run_cli([
            "1", "service-a", "200",
            "3", "rev-x", "5",
            "4", "rev-x", "10", "goodwill",
            "5",
            "8", "Acme Corp",
        ])
        try:
            self.assertEqual(result["proc"].returncode, 0,
                             msg=result["proc"].stderr[-800:])
            out = result["proc"].stdout
            self.assertIn("VERIFIED_RECORDS", out)
            self.assertIn("INVOICE", out)
            self.assertIn("Acme Corp", out)
            self.assertIn("TOTAL DUE: 185.00", out)
            self.assertIn("SIMULATED INVOICE", out)
        finally:
            result["tmp"].cleanup()

    def test_invalid_amount_rejected_then_accepted(self):
        result = run_cli([
            "1", "svc",
            "abc",        # not a number
            "-5",         # negative
            "42",
        ])
        try:
            self.assertEqual(result["proc"].returncode, 0,
                             msg=result["proc"].stderr[-800:])
            out = result["proc"].stdout
            self.assertIn("Please enter a number", out)
            self.assertIn("must be non-negative", out)
            self.assertIn("Recorded revenue", out)
        finally:
            result["tmp"].cleanup()

    def test_records_persist_across_runs(self):
        first = run_cli(["1", "svc-persist", "75", "10"])
        try:
            self.assertEqual(first["proc"].returncode, 0,
                             msg=first["proc"].stderr[-800:])
            self.assertIn("Recorded revenue", first["proc"].stdout)
            data_dir = first["data_dir"]

            second = run_cli(["10"], use_data_dir=data_dir)
            try:
                self.assertEqual(second["proc"].returncode, 0,
                                 msg=second["proc"].stderr[-800:])
                self.assertIn("svc-persist", second["proc"].stdout)
                self.assertIn("75.00", second["proc"].stdout)
            finally:
                second["tmp"].cleanup()
        finally:
            first["tmp"].cleanup()

    def test_forecast_requires_two_months(self):
        result = run_cli(["1", "svc", "100", "9", "6"])
        try:
            self.assertEqual(result["proc"].returncode, 0,
                             msg=result["proc"].stderr[-800:])
            self.assertIn("[ERROR]", result["proc"].stdout)
            self.assertIn("at least 2 recorded months", result["proc"].stdout)
        finally:
            result["tmp"].cleanup()

    def test_quit_on_eof(self):
        tmp = tempfile.TemporaryDirectory()
        env = dict(os.environ)
        env["HOME"] = tmp.name
        proc = subprocess.run(
            [sys.executable, str(CLI), "--data-dir", os.path.join(tmp.name, "d")],
            input="", capture_output=True, text=True, env=env, timeout=60,
        )
        tmp.cleanup()
        self.assertEqual(proc.returncode, 0, msg=proc.stderr[-500:])


if __name__ == "__main__":
    unittest.main()


class TestCliPaymentsAndBackup(unittest.TestCase):

    def test_mark_paid_and_verified_profit(self):
        result = run_cli([
            "1", "web-design", "150",
            "11", "rev-x", "150",
            "6",
        ])
        try:
            self.assertEqual(result["proc"].returncode, 0,
                             msg=result["proc"].stderr[-800:])
            out = result["proc"].stdout
            self.assertIn("Recorded payment", out)
            self.assertIn("(VERIFIED)", out)
            self.assertIn("payment_status", out)
            self.assertIn("verified_revenue", out)
        finally:
            result["tmp"].cleanup()

    def test_backup_creates_verified_copy(self):
        result = run_cli([
            "1", "svc", "80",
            "12",
        ])
        try:
            self.assertEqual(result["proc"].returncode, 0,
                             msg=result["proc"].stderr[-800:])
            out = result["proc"].stdout
            self.assertIn("Backup created:", out)
            self.assertIn("Integrity: OK", out)
            backups = Path(result["data_dir"]) / "backups"
            files = list(backups.iterdir())
            self.assertEqual(len(files), 2)  # backup + manifest
            backup = next(f for f in files if f.suffix == ".jsonl")
            self.assertIn("svc", backup.read_text(encoding="utf-8"))
        finally:
            result["tmp"].cleanup()
