import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
ACTION_TEXT = (ROOT / "action.yml").read_text(encoding="utf-8")
ACTION = yaml.safe_load(ACTION_TEXT)
WORKFLOW_TEXT = (ROOT / ".github" / "workflows" / "contract.yml").read_text(encoding="utf-8")
WORKFLOW = yaml.safe_load(WORKFLOW_TEXT)


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
        final = self.step("Set final job status")
        self.assertEqual(final["id"], "final_status")
        self.assertEqual(
            final["env"]["GC_EXIT_CODE"],
            "${{ steps.graphcheck_run.outputs.exit_code || 3 }}",
        )
        self.assertIn('echo "exit_code=$GC_EXIT_CODE"', final["run"])
        self.assertIn('exit "$GC_EXIT_CODE"', final["run"])
        self.assertEqual(
            ACTION["outputs"]["exit-code"]["value"],
            "${{ steps.final_status.outputs.exit_code }}",
        )

    def test_upload_contains_all_cli_artifacts(self):
        upload = self.step("Upload results")
        self.assertEqual(ACTION["inputs"]["artifact-name"]["default"], "graphcheck-results")
        self.assertEqual(upload["with"]["name"], "${{ inputs.artifact-name }}")
        self.assertEqual(
            upload["with"]["path"].splitlines(),
            [
                "${{ env.GRAPHCHECK_ARTIFACTS_DIR }}/runs/latest/results.json",
                "${{ env.GRAPHCHECK_ARTIFACTS_DIR }}/runs/latest/summary.json",
                "${{ env.GRAPHCHECK_ARTIFACTS_DIR }}/runs/latest/report.html",
            ],
        )

    def test_all_external_actions_are_pinned_to_full_commit_shas(self):
        uses = re.findall(r"^\s*-?\s*uses:\s*([^\s#]+)", ACTION_TEXT + WORKFLOW_TEXT, re.MULTILINE)
        self.assertTrue(uses)
        self.assertTrue(
            all(value == "./" or re.fullmatch(r"[^@]+@[0-9a-f]{40}", value) for value in uses),
            uses,
        )

    def test_platform_install_proves_the_pinned_cli_is_on_path(self):
        steps = WORKFLOW["jobs"]["platform-install"]["steps"]
        names = [step.get("name") for step in steps]
        self.assertLess(names.index("Install pinned CLI and invoke it"), names.index("Verify pinned CLI installation"))
        self.assertLess(names.index("Verify pinned CLI installation"), names.index("Verify platform path reaches the CLI"))
        version_step = steps[names.index("Verify pinned CLI installation")]
        self.assertEqual(version_step["run"], 'test "$(graphcheck --version)" = "graphcheck 0.2.0"')


if __name__ == "__main__":
    unittest.main()
