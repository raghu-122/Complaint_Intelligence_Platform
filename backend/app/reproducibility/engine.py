"""
Reproducibility verification engine.

Verifies deterministic data generation by re-running generator with identical seed
and verifying bitwise match of SHA-256 file checksums against stored manifest.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import get_settings
from app.generator.orchestrator import DataGenerator
from app.exports.exporter import BaselineExporter, sha256_file


class ReproducibilityEngine:
    """Evaluates generator determinism against stored baseline manifests."""

    def __init__(self, manifest_path: Optional[Path] = None):
        settings = get_settings()
        self.manifest_path = manifest_path or (settings.data_dir / "baseline" / "manifest.json")

    def run_check(
        self,
        seed: Optional[int] = None,
        scale: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Re-generate dataset and compare checksums with stored manifest.
        Returns detailed report containing JSON metrics and formatted Markdown.
        """
        if not self.manifest_path.exists():
            return {
                "status": "ERROR",
                "message": f"Baseline manifest not found at {self.manifest_path}. Run generate first.",
                "reproducible": False,
                "report_markdown": "# Reproducibility Check Failed\n\nBaseline manifest not found.",
            }

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        target_seed = seed if seed is not None else manifest.get("seed", 20261022)
        target_scale = scale if scale is not None else manifest.get("scale", "starter")

        # Create temporary working directory for reproducible run
        temp_dir = Path(tempfile.mkdtemp(prefix="yottaflex_repro_"))
        try:
            generator = DataGenerator(seed=target_seed, scale=target_scale)
            data = generator.generate_all()

            exporter = BaselineExporter(base_dir=temp_dir)
            new_manifest = exporter.export_and_create_manifest(
                data=data,
                seed=target_seed,
                scale=target_scale,
            )

            file_comparisons: List[Dict[str, Any]] = []
            mismatches: List[str] = []

            original_files = manifest.get("files", {})
            new_files = new_manifest.get("files", {})

            for filename, orig_meta in original_files.items():
                new_meta = new_files.get(filename)
                if not new_meta:
                    file_comparisons.append({
                        "file": filename,
                        "status": "MISSING_IN_NEW",
                        "original_sha256": orig_meta["sha256"][:12] + "...",
                        "new_sha256": "N/A",
                    })
                    mismatches.append(filename)
                elif orig_meta["sha256"] == new_meta["sha256"]:
                    file_comparisons.append({
                        "file": filename,
                        "status": "MATCH",
                        "original_sha256": orig_meta["sha256"][:12] + "...",
                        "new_sha256": new_meta["sha256"][:12] + "...",
                    })
                else:
                    file_comparisons.append({
                        "file": filename,
                        "status": "MISMATCH",
                        "original_sha256": orig_meta["sha256"][:12] + "...",
                        "new_sha256": new_meta["sha256"][:12] + "...",
                    })
                    mismatches.append(filename)

            is_reproducible = len(mismatches) == 0
            total_checked = len(file_comparisons)
            matched_count = total_checked - len(mismatches)

            # Generate Markdown summary table
            md_lines = [
                "# Data Generation Reproducibility Audit",
                f"- **Evaluation Time**: {datetime.now(timezone.utc).isoformat()}",
                f"- **Seed Evaluated**: `{target_seed}`",
                f"- **Dataset Scale**: `{target_scale}`",
                f"- **Overall Result**: **{'PASS (100% Bitwise Match)' if is_reproducible else 'FAIL (Hash Mismatch)'}**",
                f"- **Files Matched**: {matched_count} / {total_checked}",
                "",
                "| File | Status | Expected SHA-256 | Reproduced SHA-256 |",
                "|---|---|---|---|",
            ]
            for fc in file_comparisons:
                status_icon = "PASS" if fc["status"] == "MATCH" else "FAIL"
                md_lines.append(
                    f"| `{fc['file']}` | {status_icon} | `{fc['original_sha256']}` | `{fc['new_sha256']}` |"
                )

            report_md = "\n".join(md_lines)

            # Save markdown report to data baseline
            report_path = self.manifest_path.parent / "reproducibility_report.md"
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_md)

            return {
                "status": "SUCCESS" if is_reproducible else "FAILED",
                "reproducible": is_reproducible,
                "seed": target_seed,
                "scale": target_scale,
                "total_files": total_checked,
                "matched_files": matched_count,
                "mismatches": mismatches,
                "comparisons": file_comparisons,
                "report_markdown": report_md,
            }

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
