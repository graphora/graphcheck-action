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


    def test_cli_produced_changes_render_in_step_summary(self):
        rendered = self.render_fixture("schema_2_changes")

        self.assertIn("### What changed", rendered)
        self.assertIn("**New failures (1):**", rendered)
        self.assertIn("customer-360::account-no-orphans</code>: pass → fail", rendered)
        self.assertIn("**Fixed checks (1):**", rendered)
        self.assertIn(
            "customer-360::customer-tax-id-fixed</code>: fail → pass", rendered
        )
        self.assertIn("| Nodes | 1,250 | 1,251 | +1 |", rendered)
        self.assertIn("| Relationships | 3,480 | 3,478 | -2 |", rendered)
        self.assertEqual(rendered, self.render_fixture("schema_2_changes"))

    def test_old_artifacts_and_missing_summaries_silently_omit_changes(self):
        for fixture, include in (
            ("schema_1_2_complete", True),
            ("schema_2_complete", True),
            ("schema_2_complete", False),
        ):
            with self.subTest(fixture=fixture, include_summary=include):
                rendered = self.render_fixture(fixture, include_summary=include)
                self.assertNotIn("What changed", rendered)
                self.assertNotIn("changes unavailable", rendered.lower())

    def test_changes_are_bounded_and_report_omitted_checks(self):
        _, summary = self.load_fixture_pair("schema_2_changes")
        summary["changes"]["new_failures"] *= 25
        summary["changes"]["dropped"]["new_failures"] = 3
        rendered = "\n".join(write_summary._changes_lines(summary))

        self.assertIn("**New failures (28):**", rendered)
        self.assertEqual(rendered.count("account-no-orphans"), 20)
        self.assertIn("8 more checks omitted.", rendered)

    def test_empty_changes_and_unknown_counts_render_without_errors(self):
        _, summary = self.load_fixture_pair("schema_2_changes")
        summary["changes"].update(new_failures=[], fixed_checks=[], count_deltas={})
        rendered = "\n".join(write_summary._changes_lines(summary))

        self.assertIn("**New failures (0):**", rendered)
        self.assertIn("**Fixed checks (0):**", rendered)
        self.assertIn("Count deltas unavailable.", rendered)

    def test_change_identifiers_cannot_inject_summary_markup(self):
        _, summary = self.load_fixture_pair("schema_2_changes")
        summary["changes"]["previous_run_id"] = '<script>alert("x")</script>'
        summary["changes"]["new_failures"][0]["check_id"] = (
            "`\n### Injected <img src=x>" + "x" * 1000
        )
        rendered = "\n".join(write_summary._changes_lines(summary))

        self.assertNotIn("<script>", rendered)
        self.assertNotIn("<img", rendered)
        self.assertNotIn("\n### Injected", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("&#96;", rendered)
        self.assertLess(len(rendered), 1500)

    def test_malformed_optional_block_silently_falls_back(self):
        for changes in (
            None,
            [],
            "bad",
            {},
            {"previous_run_id": "before", "count_deltas": {}, "new_failures": "bad"},
        ):
            with self.subTest(changes=changes):
                self.assertEqual(write_summary._changes_lines({"changes": changes}), [])

    def test_malformed_count_or_check_silently_falls_back(self):
        for field, value in (("delta", True), ("delta", 99), ("before", "1250")):
            _, summary = self.load_fixture_pair("schema_2_changes")
            summary["changes"]["count_deltas"]["nodes"][field] = value
            with self.subTest(field=field, value=value):
                self.assertEqual(write_summary._changes_lines(summary), [])
        _, summary = self.load_fixture_pair("schema_2_changes")
        summary["changes"]["fixed_checks"] = [None]
        self.assertEqual(write_summary._changes_lines(summary), [])


if __name__ == "__main__":
    unittest.main()
