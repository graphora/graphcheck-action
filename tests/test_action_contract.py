import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
ACTION_TEXT = (ROOT / "action.yml").read_text(encoding="utf-8")
ACTION = yaml.safe_load(ACTION_TEXT)


class ActionContractTests(unittest.TestCase):
    def step(self, name: str) -> dict:
        return next(step for step in ACTION["runs"]["steps"] if step.get("name") == name)

    def test_cli_release_is_pinned_and_overridable(self):
        self.assertEqual(ACTION["inputs"]["version"]["default"], "0.2.0")
        self.assertIn("defaults to one", ACTION["inputs"]["concurrency"]["description"])
        self.assertIn("inputs.version != ''", ACTION_TEXT)
        self.assertIn('"graphcheck==$GC_VERSION"', ACTION_TEXT)

    def test_wrapper_invokes_only_graphcheck_run_and_restores_its_exit_code(self):
        run = self.step("Run GraphCheck")["run"]
        self.assertIn('graphcheck run "${args[@]}"', run)
        self.assertIn("code=$?", run)
        self.assertIn('echo "exit_code=$code"', run)
        self.assertIn("exit 0", run)
        self.assertEqual(
            self.step("Set final job status")["run"],
            "exit ${{ steps.graphcheck_run.outputs.exit_code || 3 }}",
        )
        self.assertEqual(
            ACTION["outputs"]["exit-code"]["value"],
            "${{ steps.graphcheck_run.outputs.exit_code }}",
        )

    def test_upload_contains_all_cli_artifacts(self):
        upload = self.step("Upload results")
        self.assertEqual(upload["uses"], "actions/upload-artifact@v4")
        self.assertEqual(
            upload["with"]["path"].splitlines(),
            [
                "${{ env.GRAPHCHECK_ARTIFACTS_DIR }}/runs/latest/results.json",
                "${{ env.GRAPHCHECK_ARTIFACTS_DIR }}/runs/latest/summary.json",
                "${{ env.GRAPHCHECK_ARTIFACTS_DIR }}/runs/latest/report.html",
            ],
        )


if __name__ == "__main__":
    unittest.main()
