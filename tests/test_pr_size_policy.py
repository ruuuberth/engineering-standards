"""Pruebas de la política de tamaño de PR (Balanced).

Se ejecutan con pytest o con `python3 -m unittest` (sin dependencias externas).
Cubren los límites acordados (100/101/150/151), las exclusiones, la excepción
`size-exempt` con y sin justificación, la autoría de la etiqueta, la retirada de
la etiqueta y el caso de diff truncado por GitHub.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import pr_size_policy as policy  # noqa: E402

SCRIPT = ROOT / "scripts" / "pr_size_policy.py"


def f(name: str, additions: int, deletions: int = 0) -> dict:
    return {"filename": name, "additions": additions, "deletions": deletions}


class ThresholdTests(unittest.TestCase):
    """1-100 PASS · 101-150 PASS+WARNING · 151+ FAIL."""

    def verdict(self, total: int) -> str:
        return policy.classify(total, 100, 150)

    def test_zero_lines_passes(self):
        self.assertEqual(self.verdict(0), "pass")

    def test_one_line_passes(self):
        self.assertEqual(self.verdict(1), "pass")

    def test_exactly_100_passes(self):
        self.assertEqual(self.verdict(100), "pass")

    def test_101_warns(self):
        self.assertEqual(self.verdict(101), "warn")

    def test_exactly_150_warns(self):
        self.assertEqual(self.verdict(150), "warn")

    def test_151_fails(self):
        self.assertEqual(self.verdict(151), "fail")

    def test_large_diff_fails(self):
        self.assertEqual(self.verdict(5000), "fail")

    def test_changed_lines_are_additions_plus_deletions(self):
        res = policy.evaluate(files=[f("a.py", 60, 40)])
        self.assertEqual(res["total_changed"], 100)
        self.assertEqual(res["verdict"], "pass")

    def test_mixed_files_sum_correctly(self):
        res = policy.evaluate(files=[f("a.py", 50, 50), f("b.py", 1)])
        self.assertEqual(res["total_changed"], 101)
        self.assertEqual(res["verdict"], "warn")

    def test_warn_still_reports_success_status(self):
        # WARN no debe bloquear el merge: el status queda en success.
        res = policy.evaluate(files=[f("a.py", 120)])
        self.assertEqual(res["verdict"], "warn")
        self.assertEqual(res["status_state"], "success")

    def test_fail_reports_failure_status(self):
        res = policy.evaluate(files=[f("a.py", 200)])
        self.assertEqual(res["status_state"], "failure")

    def test_custom_thresholds(self):
        res = policy.evaluate(files=[f("a.py", 30)], max_pass=10, max_warn=20)
        self.assertEqual(res["verdict"], "fail")


class ExclusionTests(unittest.TestCase):
    def test_default_exclude_list_matches_agreed_policy(self):
        self.assertEqual(
            set(policy.DEFAULT_EXCLUDES),
            {
                "**/*.lock",
                "**/generated/**",
                "**/dist/**",
                "**/build/**",
                "**/*.min.js",
                "**/*.min.css",
            },
        )

    def test_excluded_paths_do_not_count(self):
        res = policy.evaluate(
            files=[
                f("uv.lock", 5000),
                f("Cargo.lock", 3000),
                f("src/generated/schema.py", 4000),
                f("dist/app.js", 900),
                f("build/out.bin", 800),
                f("web/app.min.js", 700),
                f("web/app.min.css", 600),
                f("src/main.py", 10, 5),
            ]
        )
        self.assertEqual(res["total_changed"], 15)
        self.assertEqual(res["verdict"], "pass")
        self.assertEqual(res["files_considered"], 1)
        self.assertEqual(res["files_excluded"], 7)

    def test_lockfile_at_repo_root_is_excluded(self):
        self.assertTrue(policy.PathFilter(policy.DEFAULT_EXCLUDES).matches("uv.lock"))

    def test_nested_lockfile_is_excluded(self):
        pf = policy.PathFilter(policy.DEFAULT_EXCLUDES)
        self.assertTrue(pf.matches("sub/dir/package-lock.lock"))

    def test_generated_directory_at_root_is_excluded(self):
        # '**/generated/**' debe casar también sin prefijo de directorio.
        self.assertTrue(
            policy.PathFilter(policy.DEFAULT_EXCLUDES).matches("generated/model.py")
        )

    def test_minified_assets_are_excluded(self):
        pf = policy.PathFilter(policy.DEFAULT_EXCLUDES)
        self.assertTrue(pf.matches("a/app.min.js"))
        self.assertTrue(pf.matches("a/app.min.css"))

    def test_tests_are_not_excluded(self):
        pf = policy.PathFilter(policy.DEFAULT_EXCLUDES)
        self.assertFalse(pf.matches("tests/test_app.py"))
        self.assertFalse(pf.matches("src/app_test.py"))

    def test_documentation_is_not_excluded(self):
        pf = policy.PathFilter(policy.DEFAULT_EXCLUDES)
        self.assertFalse(pf.matches("docs/guide.md"))
        self.assertFalse(pf.matches("README.md"))

    def test_configuration_is_not_excluded(self):
        pf = policy.PathFilter(policy.DEFAULT_EXCLUDES)
        self.assertFalse(pf.matches("pyproject.toml"))
        self.assertFalse(pf.matches("configs/ruff.toml"))
        self.assertFalse(pf.matches(".github/workflows/ci.yml"))

    def test_similar_directory_names_are_not_excluded(self):
        # 'distribution/' no es 'dist/' y '.build' no es 'build/'.
        pf = policy.PathFilter(policy.DEFAULT_EXCLUDES)
        self.assertFalse(pf.matches("src/distribution/x.py"))
        self.assertFalse(pf.matches("build.md"))
        self.assertFalse(pf.matches("src/build_tools/x.py"))

    def test_custom_excludes_override_defaults(self):
        res = policy.evaluate(files=[f("uv.lock", 500)], excludes=("**/vendor/**",))
        self.assertEqual(res["total_changed"], 500)


class ExemptionTests(unittest.TestCase):
    BODY_OK = (
        "## Qué\nArreglo el parseo.\n\n"
        "<!-- size-exemption -->Regenero el cliente desde el esquema de la API "
        "y el diff es mecánico.<!-- /size-exemption -->\n"
    )

    def evaluate(self, **kw):
        base = dict(
            files=[f("big.py", 900)],
            body=self.BODY_OK,
            labels=["size-exempt"],
            actor="ruuuberth",
            actor_permission="write",
        )
        base.update(kw)
        return policy.evaluate(**base)

    def test_exempt_with_justification_and_maintainer_passes(self):
        res = self.evaluate()
        self.assertTrue(res["exemption"]["granted"])
        self.assertEqual(res["verdict"], "pass")
        self.assertEqual(res["status_state"], "success")

    def test_exempt_without_justification_is_rejected(self):
        res = self.evaluate(body="Solo un PR enorme sin justificar.")
        self.assertFalse(res["exemption"]["granted"])
        self.assertEqual(res["verdict"], "fail")
        self.assertIn("justificación", res["exemption"]["reason"])

    def test_exempt_with_too_short_justification_is_rejected(self):
        res = self.evaluate(body="<!-- size-exemption -->ok<!-- /size-exemption -->")
        self.assertFalse(res["exemption"]["granted"])
        self.assertEqual(res["verdict"], "fail")

    def test_justification_line_form_is_accepted(self):
        res = self.evaluate(body="Size exemption: regeneración mecánica del cliente.")
        self.assertTrue(res["exemption"]["granted"])

    def test_justification_block_form_is_accepted(self):
        res = self.evaluate(
            body="<!-- size exception -->Migración de esquema completa.<!-- /size exception -->"
        )
        self.assertTrue(res["exemption"]["granted"])

    def test_label_applied_by_non_maintainer_is_rejected(self):
        res = self.evaluate(actor_permission="read")
        self.assertFalse(res["exemption"]["granted"])
        self.assertEqual(res["verdict"], "fail")
        self.assertIn("mantenedores", res["exemption"]["reason"])

    def test_label_applied_by_triage_is_rejected(self):
        res = self.evaluate(actor_permission="triage")
        self.assertFalse(res["exemption"]["granted"])

    def test_label_applied_by_maintain_role_is_accepted(self):
        res = self.evaluate(actor_permission="maintain")
        self.assertTrue(res["exemption"]["granted"])

    def test_label_with_unknown_actor_is_denied_by_default(self):
        res = self.evaluate(actor=None, actor_permission=None)
        self.assertFalse(res["exemption"]["granted"])
        self.assertEqual(res["verdict"], "fail")

    def test_unknown_actor_can_be_downgraded_to_warning(self):
        res = self.evaluate(actor=None, actor_permission=None, unattributable="warn")
        self.assertTrue(res["exemption"]["granted"])

    def test_actor_can_be_ignored_if_configured(self):
        res = self.evaluate(
            actor=None, actor_permission=None, require_authorized_actor=False
        )
        self.assertTrue(res["exemption"]["granted"])

    def test_removing_label_reapplies_the_limit(self):
        # Mismo PR grande: con etiqueta pasa, sin etiqueta vuelve a fallar.
        with_label = self.evaluate(labels=["size-exempt"])
        without_label = self.evaluate(labels=["other"])
        self.assertEqual(with_label["verdict"], "pass")
        self.assertEqual(without_label["verdict"], "fail")
        self.assertFalse(without_label["exemption"]["requested"])

    def test_exempt_does_not_excuse_a_truncated_diff(self):
        res = self.evaluate(files=[f("big.py", 1) for _ in range(3000)], max_files=3000)
        self.assertEqual(res["verdict"], "fail")
        self.assertTrue(res["truncated"])


class RobustnessTests(unittest.TestCase):
    def test_empty_pr_passes(self):
        res = policy.evaluate(files=[])
        self.assertEqual(res["total_changed"], 0)
        self.assertEqual(res["verdict"], "pass")

    def test_missing_counts_are_treated_as_zero(self):
        res = policy.evaluate(files=[{"filename": "a.py"}])
        self.assertEqual(res["total_changed"], 0)

    def test_negative_counts_are_clamped(self):
        res = policy.evaluate(files=[f("a.py", -5, -5)])
        self.assertEqual(res["total_changed"], 0)

    def test_truncated_flag_marks_failure(self):
        files = [f(f"f{i}.py", 1) for i in range(3000)]
        res = policy.evaluate(files=files)
        self.assertTrue(res["truncated"])
        self.assertEqual(res["verdict"], "fail")

    def test_largest_files_are_reported(self):
        res = policy.evaluate(files=[f("a.py", 10), f("b.py", 90), f("c.py", 50)])
        self.assertEqual(res["largest_files"][0]["filename"], "b.py")

    def test_glob_double_star_matches_zero_segments(self):
        self.assertEqual(policy.glob_to_regex("**/*.lock"), r"(?:.*/)?[^/]*\.lock")

    def test_question_mark_matches_single_char(self):
        pf = policy.PathFilter(["file?.py"])
        self.assertTrue(pf.matches("file1.py"))
        self.assertFalse(pf.matches("file12.py"))

    def test_star_does_not_cross_directories(self):
        pf = policy.PathFilter(["src/*.py"])
        self.assertTrue(pf.matches("src/a.py"))
        self.assertFalse(pf.matches("src/sub/a.py"))


class CliTests(unittest.TestCase):
    """Prueba de integración real: ejecuta el script como lo hace el workflow."""

    def run_cli(self, *args, files=None, body=None):
        with tempfile.TemporaryDirectory() as tmp:
            files_path = Path(tmp) / "files.jsonl"
            files_path.write_text(
                "\n".join(json.dumps(x) for x in (files or [])) + "\n", encoding="utf-8"
            )
            cmd = [sys.executable, str(SCRIPT), "--files", str(files_path), *args]
            if body is not None:
                body_path = Path(tmp) / "body.md"
                body_path.write_text(body, encoding="utf-8")
                cmd += ["--body", str(body_path)]
            out_path = Path(tmp) / "verdict.json"
            cmd += ["--json-out", str(out_path)]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            data = json.loads(out_path.read_text(encoding="utf-8"))
            return proc, data

    def test_cli_100_passes_with_exit_0(self):
        proc, data = self.run_cli(files=[f("a.py", 100)])
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(data["verdict"], "pass")

    def test_cli_150_warns_with_exit_0(self):
        proc, data = self.run_cli(files=[f("a.py", 80, 70)])
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(data["verdict"], "warn")

    def test_cli_151_fails(self):
        proc, data = self.run_cli(files=[f("a.py", 151)])
        self.assertEqual(data["verdict"], "fail")
        self.assertEqual(data["status_state"], "failure")

    def test_cli_enforce_returns_exit_2_on_failure(self):
        proc, _ = self.run_cli("--enforce", files=[f("a.py", 151)])
        self.assertEqual(proc.returncode, 2)

    def test_cli_enforce_returns_exit_0_on_warning(self):
        proc, _ = self.run_cli("--enforce", files=[f("a.py", 149)])
        self.assertEqual(proc.returncode, 0)

    def test_cli_reads_labels_and_exemption(self):
        proc, data = self.run_cli(
            "--labels",
            "size-exempt,other",
            "--label-actor",
            "ruuuberth",
            "--actor-permission",
            "admin",
            files=[f("a.py", 900)],
            body="<!-- size-exemption -->Regeneración completa del cliente.<!-- /size-exemption -->",
        )
        self.assertEqual(data["verdict"], "pass")
        self.assertTrue(data["exemption"]["granted"])

    def test_cli_ignores_excluded_files(self):
        proc, data = self.run_cli(files=[f("uv.lock", 9000), f("src/a.py", 10)])
        self.assertEqual(data["total_changed"], 10)
        self.assertEqual(data["verdict"], "pass")


if __name__ == "__main__":
    unittest.main(verbosity=2)
