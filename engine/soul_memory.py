"""
SoulMemory — soul.py integration for the validator.
Reads SOUL.md (judge identity) and updates MEMORY.md (submission patterns).
Uses soul-agent package for persistence.
"""
import os
from pathlib import Path
from datetime import datetime
from collections import Counter


SOUL_DIR = Path(__file__).parent / "soul"


class SoulMemory:
    def __init__(self):
        self.soul_path = SOUL_DIR / "SOUL.md"
        self.memory_path = SOUL_DIR / "MEMORY.md"
        SOUL_DIR.mkdir(exist_ok=True)

    def update(self, report):
        """Append this run's patterns to MEMORY.md."""
        memory = self.memory_path.read_text() if self.memory_path.exists() else _MEMORY_TEMPLATE

        # Build run entry
        entry = f"""
## Run: {report.timestamp[:10]} | {report.submitter} ({report.team})
- Repo: {report.repo_url}
- Agent type: {report.agent_type}
- Verdict: {report.verdict}
- Hard gates: {report.hard_gates}
- Soft gates: {report.soft_score[0]}/{report.soft_score[1]}
- Quality: {report.quality_score}/100
- Failures: {[r['rule'].id for r in report._results if not r['result'].passed]}
- Warnings: {report.warnings[:3]}
"""
        # Append to daily log section
        if "## Run Log" not in memory:
            memory += "\n## Run Log\n"
        memory += entry

        self.memory_path.write_text(memory)

        # Optionally push to GCS
        bucket = os.getenv("MEMORY_BUCKET")
        if bucket:
            self._push_to_gcs(bucket)

    def _push_to_gcs(self, bucket_name: str):
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob("MEMORY.md")
            blob.upload_from_filename(str(self.memory_path))
        except Exception as e:
            print(f"[SoulMemory] GCS push failed: {e}")


_MEMORY_TEMPLATE = """# Agent Validator Memory
*Maintained by soul.py -- auto-updated after each validation run.*

## Most Common Failures
(populated automatically as runs accumulate)

## Team Patterns
(populated automatically as runs accumulate)

## Rule Effectiveness Notes
(add manual notes here about rules that are too strict or too lenient)

"""
