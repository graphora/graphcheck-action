import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import write_summary  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


class WriteSummaryStatusTests(unittest.TestCase):
    def load_fixture_pair(self, name: str) -> tuple[dict, dict]:
        fixture = FIXTURES / name
        return (
            json.loads((fixture / "results.json").read_text(encoding="utf-8")),
            json.loads((fixture / "summary.json").read_text(encoding="utf-8")),
        )

    def render_fixture(self, name: str, include_summary: bool = True) -> str:
        fixture = FIXTURES / name
        with tempfile.TemporaryDirectory() as temp_dir:
            latest = Path(temp_dir) / "artifacts" / "runs" / "latest"
            latest.mkdir(parents=True)
            (latest / "results.json").write_bytes((fixture / "results.json").read_bytes())
            if include_summary:
                (latest / "summary.json").write_bytes((fixture / "summary.json").read_bytes())
            step_summary = Path(temp_dir) / "step-summary.md"
            environment = {
                "GRAPHCHECK_ARTIFACTS_DIR": str(Path(temp_dir) / "artifacts"),
                "GITHUB_STEP_SUMMARY": str(step_summary),
                "GITHUB_WORKSPACE": temp_dir,
            }
            with patch.dict(os.environ, environment, clear=False):
                write_summary.main()
            return step_summary.read_text(encoding="utf-8")

    def test_schema_2_uses_run_status_and_canonical_coverage_status(self):
        results, summary = self.load_fixture_pair("schema_2_complete")
        rendered = self.render_fixture("schema_2_complete")

        self.assertEqual(results["schema_version"], "2.0")
        self.assertNotIn("status", results["run"])
        self.assertEqual(summary["schema_version"], "2.0")
        self.assertNotIn("status", summary)
        self.assertIn("**Run status:** `complete`", rendered)
        self.assertIn("**Coverage status:** `complete`", rendered)

    def test_schema_1_2_falls_back_to_run_status(self):
        results, summary = self.load_fixture_pair("schema_1_2_complete")
        rendered = self.render_fixture("schema_1_2_complete")

        self.assertEqual(results["schema_version"], "1.2")
        self.assertNotIn("run_status", results["run"])
        self.assertEqual(summary["schema_version"], "1.0")
        self.assertIn("**Run status:** `complete`", rendered)

    def test_schema_2_keeps_different_run_and_coverage_statuses(self):
        rendered = self.render_fixture("schema_2_partial")

        self.assertIn("**Run status:** `complete`", rendered)
        self.assertIn("**Coverage status:** `partial`", rendered)
        self.assertIn("**Exit code:** `2`", rendered)

    def test_historical_summary_falls_back_to_status(self):
        rendered = self.render_fixture("schema_1_2_complete")

        self.assertIn("**Coverage status:** `partial`", rendered)

    def test_missing_summary_renders_unknown_coverage_status(self):
        rendered = self.render_fixture("schema_2_complete", include_summary=False)

        self.assertIn("**Coverage status:** `unknown`", rendered)


if __name__ == "__main__":
    unittest.main()
