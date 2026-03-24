"""
13TMOS Session Auditor — Compliance Evaluation Engine

The manifest is the specification. The vault record is the execution.
The auditor measures the gap.

Compares what the manifest said would happen against what the Vault
says actually happened. Produces structured compliance verdicts.
"""
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("13tmos.auditor")

ROOT_DIR = Path(__file__).resolve().parent.parent
PACKS_DIR = ROOT_DIR / "protocols" / "packs"
OUTPUT_DIR = ROOT_DIR / "output"


class SessionAuditor:
    """Compliance evaluation engine for vault records."""

    def __init__(self, vault, manifest_archive=None):
        """
        Args:
            vault: LocalVault instance
            manifest_archive: ManifestArchive instance (optional)
        """
        self.vault = vault
        self.archive = manifest_archive

    # ── Single Session Audit ──────────────────────────────

    def audit_session(self, session_id: str) -> dict:
        """Audit a single session against its governing manifest.

        Returns a verdict dict with compliance status and findings.
        """
        record = self.vault.read(session_id)
        if not record:
            return {
                "session_id": session_id,
                "pack_id": "unknown",
                "manifest_version": "unknown",
                "date": "unknown",
                "status": "incomplete",
                "findings": ["Vault record not found for session."],
                "deliverable_fields_expected": [],
                "deliverable_fields_actual": [],
                "missing_fields": [],
                "prohibited_action_detected": False,
            }

        pack_id = record.get("pack", "unknown")
        manifest_version = record.get("manifest", "unknown")
        date = record.get("date", "unknown")
        fields = record.get("fields", {})
        content = record.get("content", {})

        # Load governing manifest
        manifest = self._load_manifest(pack_id, manifest_version)

        # Determine expected fields
        expected_fields = self._get_required_fields(manifest)
        actual_fields = list(fields.keys()) if isinstance(fields, dict) else []
        missing_fields = [f for f in expected_fields if f not in actual_fields]

        # Check for prohibited actions
        prohibited = self._get_prohibited_actions(manifest)
        prohibited_detected = self._check_prohibited(content, prohibited)

        # Check completion
        completion_ok = self._check_completion(record, content)

        # Build findings
        findings = []

        if missing_fields:
            for f in missing_fields:
                findings.append(f"Missing required field: {f}")

        if prohibited_detected:
            for trace in prohibited_detected:
                findings.append(f"Prohibited action trace: {trace}")

        if not completion_ok:
            findings.append("Session did not reach completion.")

        if manifest is None:
            findings.append(f"Governing manifest not found for {pack_id} v{manifest_version}.")

        # Determine verdict
        if not completion_ok and not findings:
            status = "incomplete"
        elif findings:
            # If only issue is missing manifest but everything else is fine
            if len(findings) == 1 and "manifest not found" in findings[0].lower():
                status = "incomplete"
            elif not completion_ok and not missing_fields and not prohibited_detected:
                status = "incomplete"
            else:
                status = "non_compliant"
        else:
            status = "compliant"

        return {
            "session_id": session_id,
            "pack_id": pack_id,
            "manifest_version": manifest_version,
            "date": date,
            "status": status,
            "findings": findings,
            "deliverable_fields_expected": expected_fields,
            "deliverable_fields_actual": actual_fields,
            "missing_fields": missing_fields,
            "prohibited_action_detected": bool(prohibited_detected),
        }

    # ── Range Audit ───────────────────────────────────────

    def audit_range(self, start_date: str = None, end_date: str = None,
                    pack_id: str = None, user_id: str = None) -> list[dict]:
        """Audit all sessions matching filters."""
        # Build query dimensions
        dimensions = {}
        if pack_id:
            dimensions["pack"] = pack_id
        if user_id:
            dimensions["user"] = user_id

        if dimensions:
            records = self.vault.query(dimensions)
        else:
            records = self.vault.query({"user": "*"})
            # Fallback: list all
            if not records:
                summaries = self.vault.list_sessions()
                records = []
                for s in summaries:
                    r = self.vault.read(s["session"])
                    if r:
                        records.append(r)

        # Filter by date range
        if start_date or end_date:
            filtered = []
            for r in records:
                rdate = r.get("date", "")
                if start_date and rdate < start_date:
                    continue
                if end_date and rdate > end_date:
                    continue
                filtered.append(r)
            records = filtered

        # Audit each
        verdicts = []
        for record in records:
            session_id = record.get("session", "")
            if session_id:
                verdict = self.audit_session(session_id)
                verdicts.append(verdict)

        return verdicts

    # ── Vault Hash ────────────────────────────────────────

    def compute_vault_hash(self, session_ids: list[str]) -> str:
        """SHA-256 hash of all vault records for tamper evidence.

        Records are serialized as sorted JSON with consistent key ordering.
        """
        hasher = hashlib.sha256()

        for sid in sorted(session_ids):
            record = self.vault.read(sid)
            if record:
                # Remove transient fields that shouldn't affect hash
                hashable = {k: v for k, v in record.items() if not k.startswith("_")}
                canonical = json.dumps(hashable, sort_keys=True, default=str)
                hasher.update(canonical.encode("utf-8"))

        return hasher.hexdigest()

    # ── Report Generation ─────────────────────────────────

    def generate_report(self, verdicts: list[dict], scope: dict, auditor: str) -> str:
        """Format verdicts into the compliance report string."""
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        report_id = str(uuid.uuid4())[:8]

        total = len(verdicts)
        compliant = sum(1 for v in verdicts if v["status"] == "compliant")
        non_compliant = sum(1 for v in verdicts if v["status"] == "non_compliant")
        incomplete = sum(1 for v in verdicts if v["status"] == "incomplete")

        def pct(n):
            return f"{n / total * 100:.0f}%" if total > 0 else "0%"

        # Compute vault hash
        session_ids = [v["session_id"] for v in verdicts]
        vault_hash = self.compute_vault_hash(session_ids)

        # Build scope description
        scope_desc = scope.get("description", "all sessions")

        # Collect manifest versions
        manifest_versions = set()
        current_versions = {}
        for v in verdicts:
            mv = v.get("manifest_version", "unknown")
            pid = v.get("pack_id", "unknown")
            manifest_versions.add(f"{pid} v{mv}")
            # Track current version per pack
            if pid not in current_versions:
                current = self._get_current_version(pid)
                if current:
                    current_versions[pid] = current

        deprecated_count = 0
        for v in verdicts:
            pid = v.get("pack_id", "")
            mv = v.get("manifest_version", "")
            if pid in current_versions and mv != current_versions[pid]:
                deprecated_count += 1

        # ── Build Report ──────────────────────────────────
        lines = [
            "VAULT AUDIT REPORT",
            f"Generated: {date_str}",
            f"Auditor: {auditor}",
            f"Scope: {scope_desc}",
            f"Sessions reviewed: {total}",
            "",
            "SUMMARY",
            "─" * 44,
            f"Compliant:      {compliant} ({pct(compliant)})",
            f"Non-compliant:  {non_compliant} ({pct(non_compliant)})",
            f"Incomplete:     {incomplete} ({pct(incomplete)})",
            "",
        ]

        # Findings section
        flagged = [v for v in verdicts if v["status"] != "compliant"]
        if flagged:
            lines.append("FINDINGS")
            lines.append("─" * 44)

            for v in flagged:
                sid = v["session_id"]
                sid_short = sid[:8] if len(sid) > 8 else sid
                lines.append("")
                lines.append(f"Session: {sid_short}")
                lines.append(f"Pack: {v['pack_id']} v{v['manifest_version']}")
                lines.append(f"Date: {v['date']}")
                lines.append(f"Status: {v['status'].upper()}")
                lines.append("")

                for finding in v["findings"]:
                    lines.append(f"Reason: {finding}")

                if v["missing_fields"]:
                    lines.append(f"Expected: Fields {', '.join(v['missing_fields'])} per manifest")
                    lines.append(f"Actual: Fields not present in vault record")

                lines.append("")
                lines.append("Recommendation: Review session transcript. Consider re-running")
                lines.append("intake with updated manifest.")
                lines.append("")
                lines.append("─" * 44)

            lines.append("")

        # Summary-only note
        if not flagged and total > 0:
            lines.append("FINDINGS")
            lines.append("─" * 44)
            lines.append("No non-compliant or incomplete sessions found.")
            lines.append("")

        # Manifest compliance
        lines.append("MANIFEST COMPLIANCE")
        lines.append("─" * 44)

        if total > 0:
            lines.append("All sessions ran under documented manifest versions.")
        else:
            lines.append("No sessions to evaluate.")

        lines.append(f"Manifest versions in use: {', '.join(sorted(manifest_versions)) if manifest_versions else 'none'}")

        current_list = [f"{pid} v{ver}" for pid, ver in current_versions.items()]
        lines.append(f"Current manifest versions: {', '.join(sorted(current_list)) if current_list else 'none'}")
        lines.append(f"Sessions on deprecated manifests: {deprecated_count}")
        lines.append("")

        # Certification
        lines.append("CERTIFICATION")
        lines.append("─" * 44)
        lines.append("This report was generated by the Vault Audit Pack v1.0")
        lines.append("governed by manifest protocols/packs/vault_audit/MANIFEST.md.")
        lines.append("The audit pack itself is subject to the same compliance")
        lines.append("verification as any other pack in the system.")
        lines.append("")
        lines.append(f"Report ID: {report_id}")
        lines.append(f"Vault hash: {vault_hash}")

        return "\n".join(lines), report_id, vault_hash

    # ── Write Report ──────────────────────────────────────

    def write_report(self, report: str, report_id: str = None) -> str:
        """Write report to output/ and return file path."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rid = report_id or str(uuid.uuid4())[:8]
        filename = f"audit_{date_str}_{rid}.md"
        path = OUTPUT_DIR / filename
        path.write_text(report)
        logger.info("Audit report written: %s", path)
        return str(path)

    # ── Internal Helpers ──────────────────────────────────

    def _load_manifest(self, pack_id: str, version: str = None) -> dict | None:
        """Load a pack manifest, trying archive first, then current."""
        # Try manifest archive for specific version
        if self.archive and version:
            content = self.archive.retrieve_version(pack_id, version)
            if content:
                # Return as a pseudo-manifest with the content
                return {"_raw": content, "_source": "archive", "_version": version}

        # Fall back to current manifest.json
        manifest_path = PACKS_DIR / pack_id / "manifest.json"
        if manifest_path.exists():
            try:
                return json.loads(manifest_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass

        return None

    def _get_required_fields(self, manifest: dict | None) -> list[str]:
        """Extract required deliverable fields from a manifest."""
        if manifest is None:
            return []

        # From manifest.json state.capture keys
        state = manifest.get("state", {})
        capture = state.get("capture", {})
        if capture:
            return [k for k, v in capture.items()
                    if v is None or v == 0]  # null/zero = expected to be filled

        # From deliverables section
        deliverables = manifest.get("deliverables", {})
        if isinstance(deliverables, dict):
            types = deliverables.get("types", [])
            for dt in types:
                fields = dt.get("fields", [])
                return [f.get("id", f.get("name", "")) for f in fields
                        if isinstance(f, dict) and f.get("required", False)]

        return []

    def _get_prohibited_actions(self, manifest: dict | None) -> list[str]:
        """Extract prohibited action keywords from manifest.

        Reads MANIFEST.md if available (via archive), otherwise
        returns common prohibitions.
        """
        if manifest is None:
            return []

        # If we have raw MANIFEST.md content, parse prohibited section
        raw = manifest.get("_raw", "")
        if raw:
            prohibited = []
            in_section = False
            for line in raw.split("\n"):
                if "prohibited action" in line.lower():
                    in_section = True
                    continue
                if in_section:
                    if line.startswith("##") or line.startswith("### Authorized"):
                        break
                    if line.strip().startswith("- "):
                        prohibited.append(line.strip()[2:].strip())
            return prohibited

        return []

    def _check_prohibited(self, content, prohibited: list[str]) -> list[str]:
        """Check content for traces of prohibited actions."""
        if not prohibited or not content:
            return []

        # Flatten content to searchable text
        if isinstance(content, dict):
            text = json.dumps(content).lower()
        elif isinstance(content, str):
            text = content.lower()
        else:
            return []

        traces = []
        for action in prohibited:
            # Extract key phrases from prohibition
            keywords = [w for w in action.lower().split()
                        if len(w) > 4 and w not in ("must", "shall", "never", "session")]
            # Check for keyword clusters (2+ keywords present)
            matches = sum(1 for kw in keywords if kw in text)
            if len(keywords) > 0 and matches >= min(2, len(keywords)):
                traces.append(action[:80])

        return traces

    def _check_completion(self, record: dict, content) -> bool:
        """Check if session reached completion."""
        # Check for content.summary (completion indicator)
        if isinstance(content, dict):
            if content.get("summary"):
                return True
            # Empty content dict = incomplete
            if not content:
                return False

        # If content is a non-empty string, consider complete
        if isinstance(content, str) and content.strip():
            return True

        # Has fields = likely complete
        fields = record.get("fields", {})
        if fields and any(v is not None and str(v).strip() for v in fields.values()):
            return True

        return False

    def _get_current_version(self, pack_id: str) -> str | None:
        """Get current manifest version for a pack."""
        manifest_path = PACKS_DIR / pack_id / "manifest.json"
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text())
                return data.get("version", None)
            except (json.JSONDecodeError, OSError):
                pass
        return None
