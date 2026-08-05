from __future__ import annotations

import http.server
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
FIXTURES = SKILL_ROOT / "evals" / "fixtures"
RISKY_REPO = FIXTURES / "vite-risky"
VALID_REPORT = FIXTURES / "reports" / "valid-report.json"
INCREMENTAL_POLICY = FIXTURES / "reports" / "incremental-gate-policy.json"
RUNTIME_SITE = FIXTURES / "runtime-site"


def run_python(script: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        cwd=str(cwd or SKILL_ROOT),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class ToolingEval(unittest.TestCase):
    def load_valid(self) -> dict:
        return json.loads(VALID_REPORT.read_text(encoding="utf-8"))

    def test_01_inventory_detects_project_and_observations(self) -> None:
        result = run_python("inventory_repo.py", str(RISKY_REPO))
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertIn("React", output["project"]["frameworks"])
        self.assertIn("Vite", output["project"]["tools"])
        observation_ids = {item["id"] for item in output["observations"]}
        self.assertIn("lockfile_missing", observation_ids)
        self.assertIn("floating_dependencies", observation_ids)
        self.assertIn("typescript_strict_not_enabled", observation_ids)
        self.assertIn("multiple_http_libraries", observation_ids)
        signal_ids = {item["signal"] for item in output["signals"]}
        self.assertIn("dangerously_set_inner_html", signal_ids)
        self.assertIn("raw_inner_html", signal_ids)

    def test_02_inventory_output_file_is_utf8_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "inventory.json"
            result = run_python("inventory_repo.py", str(RISKY_REPO), "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["schema_version"], "inventory-1.0")

    def test_03_strict_verifier_accepts_matching_source_quote(self) -> None:
        result = run_python("verify_findings.py", str(VALID_REPORT), "--repo", str(RISKY_REPO), "--strict")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(json.loads(result.stdout)["valid"])

    def test_04_verifier_rejects_out_of_range_line(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = self.load_valid()
            report["findings"][0]["evidence"][0]["line"] = 999
            path = Path(temporary) / "bad-line.json"
            write_json(path, report)
            result = run_python("verify_findings.py", str(path), "--repo", str(RISKY_REPO), "--strict")
            self.assertEqual(result.returncode, 1)
            self.assertIn("exceed", result.stdout)

    def test_05_verifier_rejects_unconfirmed_p0(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = self.load_valid()
            finding = report["findings"][0]
            finding["severity"] = "P0"
            finding["confidence"] = "medium"
            finding["status"] = "likely"
            path = Path(temporary) / "bad-p0.json"
            write_json(path, report)
            result = run_python("verify_findings.py", str(path), "--repo", str(RISKY_REPO))
            self.assertEqual(result.returncode, 1)
            self.assertIn("P0 requires", result.stdout)

    def test_06_verifier_rejects_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = self.load_valid()
            report["findings"][0]["evidence"][0]["file"] = "../outside.ts"
            path = Path(temporary) / "path-escape.json"
            write_json(path, report)
            result = run_python("verify_findings.py", str(path), "--repo", str(RISKY_REPO))
            self.assertEqual(result.returncode, 1)
            self.assertIn("escapes repository root", result.stdout)

    def test_07_verifier_rejects_missing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = self.load_valid()
            report["findings"][0]["evidence"] = []
            path = Path(temporary) / "missing-evidence.json"
            write_json(path, report)
            result = run_python("verify_findings.py", str(path), "--repo", str(RISKY_REPO))
            self.assertEqual(result.returncode, 1)
            self.assertIn("at least one evidence", result.stdout)

    def test_08_scoring_handles_na_and_evidence_coverage(self) -> None:
        result = run_python("score_report.py", str(VALID_REPORT))
        self.assertEqual(result.returncode, 0, result.stdout)
        output = json.loads(result.stdout)
        self.assertEqual(output["total"], 60.0)
        self.assertEqual(output["grade"], "C")
        self.assertEqual(output["evidence_coverage"], 50.0)
        self.assertEqual(output["status"], "provisional")

    def test_09_scoring_rejects_unknown_dimension(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = self.load_valid()
            report["scoring"]["dimensions"]["made_up"] = {
                "score": 5,
                "evidence_sufficient": True,
                "note": "invalid",
            }
            path = Path(temporary) / "bad-score.json"
            write_json(path, report)
            result = run_python("score_report.py", str(path))
            self.assertEqual(result.returncode, 1)
            self.assertIn("unknown scoring dimensions", result.stdout)

    def test_10_renderer_produces_stable_markdown(self) -> None:
        result = run_python("render_report.py", str(VALID_REPORT))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[P1][高置信度] F-001", result.stdout)
        self.assertIn("`src/evidence.ts:3`", result.stdout)
        self.assertIn("未验证风险", result.stdout)

    def test_11_runtime_dry_run_validates_manifest(self) -> None:
        node = os.environ.get("FRONTEND_REVIEW_NODE", "node")
        command = [
            node,
            str(SCRIPTS / "runtime_audit.cjs"),
            "--base-url",
            "http://127.0.0.1:9999",
            "--manifest",
            str(RUNTIME_SITE / "routes.json"),
            "--output",
            str(RUNTIME_SITE / "unused-output"),
            "--dry-run",
        ]
        result = subprocess.run(command, text=True, encoding="utf-8", capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)["plan"]), 2)

    def test_12_runtime_browser_collects_artifacts_when_enabled(self) -> None:
        node_modules = os.environ.get("FRONTEND_REVIEW_NODE_MODULES")
        if not node_modules:
            self.skipTest("FRONTEND_REVIEW_NODE_MODULES is not set")
        node = os.environ.get("FRONTEND_REVIEW_NODE", "node")

        handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(
            *args, directory=str(RUNTIME_SITE), **kwargs
        )
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                command = [
                    node,
                    str(SCRIPTS / "runtime_audit.cjs"),
                    "--base-url",
                    f"http://127.0.0.1:{server.server_port}",
                    "--manifest",
                    str(RUNTIME_SITE / "routes.json"),
                    "--output",
                    temporary,
                    "--node-modules",
                    node_modules,
                    "--runs",
                    "2",
                    "--fail-on-navigation-error",
                ]
                result = subprocess.run(command, text=True, encoding="utf-8", capture_output=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                audit = json.loads((Path(temporary) / "runtime-audit.json").read_text(encoding="utf-8"))
                self.assertEqual(audit["schemaVersion"], "runtime-audit-1.2")
                self.assertEqual(len(audit["results"]), 4)
                self.assertEqual(len(audit["aggregates"]), 2)
                self.assertTrue(all(item["runs"] == 2 for item in audit["aggregates"]))
                mobile = next(item for item in audit["results"] if item["viewport"]["name"] == "mobile")
                self.assertTrue(mobile["dom"]["layout"]["horizontalOverflow"])
                self.assertEqual(mobile["dom"]["controls"]["missingLabelCount"], 1)
                self.assertEqual(mobile["dom"]["controls"]["formControlTotal"], 1)
                self.assertGreaterEqual(mobile["dom"]["controls"]["interactiveElementTotal"], 2)
                self.assertEqual(mobile["dom"]["images"]["missingAltCount"], 1)
                self.assertEqual(mobile["dom"]["contrast"]["schemaVersion"], "contrast-evidence-1.0")
                self.assertIn("relative luminance", mobile["dom"]["contrast"]["method"])
                self.assertGreaterEqual(mobile["dom"]["contrast"]["violationCount"], 1)
                self.assertIsNotNone(mobile["dom"]["performanceSnapshot"]["labSignals"])
                self.assertIn("cls", mobile["dom"]["performanceSnapshot"]["labSignals"])
                self.assertTrue((Path(temporary) / mobile["artifacts"]["screenshot"]).is_file())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_13_strict_runtime_evidence_requires_artifact_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = self.load_valid()
            report["findings"][0]["evidence"] = [
                {
                    "kind": "runtime",
                    "summary": "The page overflowed at mobile width.",
                    "url": "http://127.0.0.1/example",
                    "viewport": "mobile"
                }
            ]
            path = Path(temporary) / "runtime-without-artifact.json"
            write_json(path, report)
            result = run_python("verify_findings.py", str(path), "--repo", str(RISKY_REPO), "--strict")
            self.assertEqual(result.returncode, 1)
            self.assertIn("requires a runtime artifact", result.stdout)
            self.assertIn("requires --artifact-root", result.stdout)

    def test_14_strict_tool_evidence_requires_artifact_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = self.load_valid()
            report["findings"][0]["evidence"] = [
                {
                    "kind": "tool",
                    "summary": "The build command exited with status 1."
                }
            ]
            path = Path(temporary) / "tool-without-artifact.json"
            write_json(path, report)
            result = run_python("verify_findings.py", str(path), "--repo", str(RISKY_REPO), "--strict")
            self.assertEqual(result.returncode, 1)
            self.assertIn("requires a tool-output artifact", result.stdout)
            self.assertIn("requires --artifact-root", result.stdout)

    def test_15_strict_tool_evidence_accepts_existing_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifact_root = Path(temporary) / "artifacts"
            artifact_root.mkdir()
            (artifact_root / "build-command.txt").write_text(
                "command: npm run build\nexit_code: 1\nstderr: compilation failed\n",
                encoding="utf-8",
            )
            report = self.load_valid()
            report["findings"][0]["evidence"] = [
                {
                    "kind": "tool",
                    "summary": "The build command exited with status 1.",
                    "artifact": "build-command.txt",
                }
            ]
            path = Path(temporary) / "tool-with-artifact.json"
            write_json(path, report)
            result = run_python(
                "verify_findings.py",
                str(path),
                "--repo",
                str(RISKY_REPO),
                "--artifact-root",
                str(artifact_root),
                "--strict",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_16_verifier_rejects_invalid_explicit_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = self.load_valid()
            report["findings"][0]["fingerprint"] = "bad fingerprint"
            path = Path(temporary) / "bad-fingerprint.json"
            write_json(path, report)
            result = run_python("verify_findings.py", str(path), "--repo", str(RISKY_REPO), "--strict")
            self.assertEqual(result.returncode, 1)
            self.assertIn("fingerprint", result.stdout)

    def test_17_compare_matches_line_shifts_and_detects_regression(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            baseline = self.load_valid()
            current = self.load_valid()
            baseline["findings"][0]["fingerprint"] = "fixture-risk-001"
            current["findings"][0]["fingerprint"] = "fixture-risk-001"
            baseline["findings"][0]["severity"] = "P2"
            current["findings"][0]["severity"] = "P1"
            current["findings"][0]["evidence"][0]["line"] = 30
            baseline_path = Path(temporary) / "baseline.json"
            current_path = Path(temporary) / "current.json"
            output = Path(temporary) / "diff.json"
            write_json(baseline_path, baseline)
            write_json(current_path, current)
            result = run_python("compare_reports.py", str(baseline_path), str(current_path), "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            diff = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(diff["summary"]["new"], 0)
            self.assertEqual(diff["summary"]["regressions"], 1)
            self.assertEqual(diff["changed"][0]["changed_fields"], ["severity"])

    def test_18_incremental_gate_blocks_only_new_or_regressed_p1(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            baseline = self.load_valid()
            baseline["findings"][0]["fingerprint"] = "fixture-risk-001"
            current = json.loads(json.dumps(baseline))
            baseline_path = Path(temporary) / "baseline.json"
            current_path = Path(temporary) / "current.json"
            write_json(baseline_path, baseline)
            write_json(current_path, current)
            passing = run_python(
                "gate_report.py",
                str(current_path),
                "--baseline",
                str(baseline_path),
                "--policy",
                str(INCREMENTAL_POLICY),
            )
            self.assertEqual(passing.returncode, 0, passing.stdout + passing.stderr)

            new_finding = json.loads(json.dumps(current["findings"][0]))
            new_finding.update({"id": "F-002", "fingerprint": "fixture-risk-002", "title": "New confirmed regression"})
            current["findings"].append(new_finding)
            write_json(current_path, current)
            failing = run_python(
                "gate_report.py",
                str(current_path),
                "--baseline",
                str(baseline_path),
                "--policy",
                str(INCREMENTAL_POLICY),
            )
            self.assertEqual(failing.returncode, 1)
            payload = json.loads(failing.stdout)
            self.assertFalse(payload["passed"])
            self.assertEqual(payload["evaluated_findings"], 1)
            self.assertEqual(payload["reasons"][0]["finding_id"], "F-002")

    def test_19_sarif_export_is_stable_and_source_located(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first.sarif"
            second = Path(temporary) / "second.sarif"
            for output in (first, second):
                result = run_python("export_sarif.py", str(VALID_REPORT), "--output", str(output))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            sarif = json.loads(first.read_text(encoding="utf-8"))
            self.assertEqual(sarif["version"], "2.1.0")
            result = sarif["runs"][0]["results"][0]
            self.assertEqual(result["ruleId"], "FSR.security_privacy_supply_chain")
            self.assertIn("primaryLocationLineHash", result["partialFingerprints"])
            self.assertEqual(result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"], "src/evidence.ts")

    def test_20_change_scope_parses_hunks_and_risk_categories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            diff = Path(temporary) / "change.diff"
            diff.write_text(
                "diff --git a/src/auth/session.ts b/src/auth/session.ts\n"
                "--- a/src/auth/session.ts\n"
                "+++ b/src/auth/session.ts\n"
                "@@ -2 +2,2 @@\n"
                "-oldValue\n"
                "+newValue\n"
                "+auditValue\n",
                encoding="utf-8",
            )
            output = Path(temporary) / "scope.json"
            result = run_python(
                "collect_change_scope.py",
                str(RISKY_REPO),
                "--diff-file",
                str(diff),
                "--output",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            scope = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(scope["summary"]["files"], 1)
            self.assertEqual(scope["files"][0]["changed_lines"], [{"start": 2, "end": 3}])
            self.assertIn("auth_security", scope["files"][0]["categories"])
            self.assertEqual(scope["files"][0]["review_priority"], "high")

    def test_21_bundle_builds_verified_hashed_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "bundle"
            output.mkdir()
            result = run_python(
                "build_review_bundle.py",
                str(VALID_REPORT),
                "--repo",
                str(RISKY_REPO),
                "--output",
                str(output),
                "--artifact-root",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            expected = {"review.json", "review.md", "review.sarif", "verification.json", "gate-result.json", "manifest.json"}
            self.assertTrue(expected <= {item.name for item in output.iterdir()})
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["summary"]["gate_passed"])
            self.assertEqual(manifest["tool"]["version"], "2.0.0")
            self.assertEqual(
                manifest["tool"]["engine_sha256"]["gate_report.py"],
                hashlib.sha256((SCRIPTS / "gate_report.py").read_bytes()).hexdigest(),
            )
            for item in manifest["files"]:
                digest = hashlib.sha256((output / item["path"]).read_bytes()).hexdigest()
                self.assertEqual(digest, item["sha256"])

    def test_22_runtime_dry_run_expands_runs_and_budgets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "routes.json"
            write_json(
                manifest,
                {
                    "budgets": {"lcpMs": 2500, "cls": 0.1},
                    "routes": [{"id": "home", "path": "/", "viewports": [{"name": "mobile", "width": 375, "height": 812}]}],
                },
            )
            node = os.environ.get("FRONTEND_REVIEW_NODE", "node")
            result = subprocess.run(
                [
                    node,
                    str(SCRIPTS / "runtime_audit.cjs"),
                    "--base-url",
                    "http://127.0.0.1:9999",
                    "--manifest",
                    str(manifest),
                    "--output",
                    str(Path(temporary) / "unused"),
                    "--runs",
                    "3",
                    "--dry-run",
                ],
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)["plan"]
            self.assertEqual(len(plan), 3)
            self.assertEqual([item["run"] for item in plan], [1, 2, 3])
            self.assertEqual(plan[0]["budgets"]["lcpMs"], 2500)

    def test_23_runtime_budget_can_fail_the_tool_step(self) -> None:
        node_modules = os.environ.get("FRONTEND_REVIEW_NODE_MODULES")
        if not node_modules:
            self.skipTest("FRONTEND_REVIEW_NODE_MODULES is not set")
        node = os.environ.get("FRONTEND_REVIEW_NODE", "node")
        handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(
            *args, directory=str(RUNTIME_SITE), **kwargs
        )
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                manifest = Path(temporary) / "routes.json"
                write_json(
                    manifest,
                    {
                        "budgets": {"resourceCount": 0},
                        "routes": [{"id": "home", "path": "/", "viewports": [{"name": "desktop", "width": 1000, "height": 700}]}],
                    },
                )
                output = Path(temporary) / "runtime"
                result = subprocess.run(
                    [
                        node,
                        str(SCRIPTS / "runtime_audit.cjs"),
                        "--base-url",
                        f"http://127.0.0.1:{server.server_port}",
                        "--manifest",
                        str(manifest),
                        "--output",
                        str(output),
                        "--node-modules",
                        node_modules,
                        "--fail-on-budget",
                    ],
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                audit = json.loads((output / "runtime-audit.json").read_text(encoding="utf-8"))
                self.assertEqual(audit["results"][0]["budgets"]["status"], "exceeded")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_24_verifier_rejects_duplicate_logical_fingerprints(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = self.load_valid()
            duplicate = json.loads(json.dumps(report["findings"][0]))
            duplicate["id"] = "F-002"
            report["findings"].append(duplicate)
            path = Path(temporary) / "duplicate-fingerprint.json"
            write_json(path, report)
            result = run_python("verify_findings.py", str(path), "--repo", str(RISKY_REPO), "--strict")
            self.assertEqual(result.returncode, 1)
            self.assertIn("duplicate logical fingerprint", result.stdout)

    def test_25_confirmed_p0_requires_block_conclusion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = self.load_valid()
            report["findings"][0]["severity"] = "P0"
            path = Path(temporary) / "p0.json"
            write_json(path, report)
            rejected = run_python("verify_findings.py", str(path), "--repo", str(RISKY_REPO), "--strict")
            self.assertEqual(rejected.returncode, 1)
            self.assertIn("confirmed P0 requires block", rejected.stdout)
            report["review"]["conclusion"] = "block"
            write_json(path, report)
            accepted = run_python("verify_findings.py", str(path), "--repo", str(RISKY_REPO), "--strict")
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)

    def test_26_change_scope_includes_untracked_text_and_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            initialized = subprocess.run(["git", "init", "--quiet", str(repo)], capture_output=True, text=True, check=False)
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            source = repo / "src" / "auth"
            source.mkdir(parents=True)
            (source / "new.ts").write_text("one\ntwo\nthree", encoding="utf-8")
            (repo / "asset.bin").write_bytes(b"\x00\x01\x02")
            output = Path(temporary) / "scope.json"
            result = run_python("collect_change_scope.py", str(repo), "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            files = {item["path"]: item for item in json.loads(output.read_text(encoding="utf-8"))["files"]}
            self.assertEqual(files["src/auth/new.ts"]["additions"], 3)
            self.assertIn("auth_security", files["src/auth/new.ts"]["categories"])
            self.assertTrue(files["asset.bin"]["binary"])

    def test_27_verifier_rejects_stale_scoring_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = self.load_valid()
            report["scoring"]["result"] = {
                "total": 100,
                "grade": "A",
                "evidence_coverage": 100,
                "status": "final",
                "applicable_weight": 100,
                "details": {},
            }
            path = Path(temporary) / "stale-score.json"
            write_json(path, report)
            result = run_python("verify_findings.py", str(path), "--repo", str(RISKY_REPO), "--strict")
            self.assertEqual(result.returncode, 1)
            self.assertIn("does not match deterministic recalculation", result.stdout)

    def test_28_bundle_verifier_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "bundle"
            output.mkdir()
            built = run_python(
                "build_review_bundle.py",
                str(VALID_REPORT),
                "--repo",
                str(RISKY_REPO),
                "--output",
                str(output),
                "--artifact-root",
                str(output),
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            valid = run_python(
                "verify_review_bundle.py",
                str(output),
                "--repo",
                str(RISKY_REPO),
                "--artifact-root",
                str(output),
                "--require-gate-pass",
            )
            self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)
            with (output / "review.md").open("a", encoding="utf-8") as handle:
                handle.write("tampered\n")
            invalid = run_python("verify_review_bundle.py", str(output))
            self.assertEqual(invalid.returncode, 1)
            self.assertIn("SHA-256 mismatch", invalid.stdout)

    def test_29_default_gate_matches_release_conclusion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = self.load_valid()
            report["review"]["conclusion"] = "ready_after_fixes"
            path = Path(temporary) / "fix-first.json"
            write_json(path, report)
            result = run_python("gate_report.py", str(path))
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["reasons"][0]["code"], "blocked_conclusion")

    def test_30_strict_verifier_warns_on_cross_file_source_only_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = self.load_valid()
            report["findings"][0]["evidence"].append(
                {
                    "kind": "source",
                    "summary": "A second file contains a related DOM sink.",
                    "file": "src/App.tsx",
                    "line": 9,
                    "quote": "<div dangerouslySetInnerHTML={{ __html: html }} />",
                }
            )
            path = Path(temporary) / "cross-file.json"
            write_json(path, report)
            result = run_python("verify_findings.py", str(path), "--repo", str(RISKY_REPO), "--strict")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("semantic reachability", result.stdout)

    def test_31_command_capture_preserves_exit_and_redacts_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "evidence"
            command = [
                "--cwd",
                str(RISKY_REPO),
                "--output",
                str(output),
                "--label",
                "failing-check",
                "--",
                sys.executable,
                "-c",
                "import sys; print('token=supersecret'); print('problem', file=sys.stderr); sys.exit(3)",
            ]
            captured = run_python("capture_command.py", *command)
            self.assertEqual(captured.returncode, 0, captured.stdout + captured.stderr)
            metadata = json.loads((output / "failing-check.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["exit_code"], 3)
            self.assertTrue(metadata["capture"]["complete"])
            self.assertGreater(metadata["capture"]["redactions_applied"], 0)
            self.assertNotIn("supersecret", (output / "failing-check.stdout.log").read_text(encoding="utf-8"))
            self.assertIn("problem", (output / "failing-check.stderr.log").read_text(encoding="utf-8"))
            blocked = run_python("capture_command.py", "--fail-on-command-error", *command)
            self.assertEqual(blocked.returncode, 1)

    def test_32_strict_verifier_checks_nested_command_artifact_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            commands = root / "commands"
            captured = run_python(
                "capture_command.py",
                "--cwd",
                str(RISKY_REPO),
                "--output",
                str(commands),
                "--label",
                "check",
                "--",
                sys.executable,
                "-c",
                "print('complete')",
            )
            self.assertEqual(captured.returncode, 0, captured.stdout + captured.stderr)
            report = self.load_valid()
            report["findings"][0]["evidence"] = [
                {
                    "kind": "tool",
                    "summary": "The captured check completed.",
                    "artifact": "commands/check.json",
                }
            ]
            report_path = root / "review.json"
            write_json(report_path, report)
            valid = run_python(
                "verify_findings.py",
                str(report_path),
                "--repo",
                str(RISKY_REPO),
                "--artifact-root",
                str(root),
                "--strict",
            )
            self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)
            self.assertNotIn("not command-evidence-1.0", valid.stdout)
            with (commands / "check.stdout.log").open("a", encoding="utf-8") as handle:
                handle.write("tampered\n")
            invalid = run_python(
                "verify_findings.py",
                str(report_path),
                "--repo",
                str(RISKY_REPO),
                "--artifact-root",
                str(root),
                "--strict",
            )
            self.assertEqual(invalid.returncode, 1)
            self.assertIn("SHA-256 mismatch", invalid.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
