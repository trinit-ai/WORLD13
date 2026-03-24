#!/usr/bin/env python3
"""
13TMOS Watcher — Event-Driven Vault Routing

The Watcher knows nothing in advance. It watches what the Vault produces
and evaluates conditions in real time. The path emerges from the
deliverables, not from a graph.

This is navigation, not pipeline. The Vault is the event bus.
The foam self-organizes.

Usage:
    python engine/watcher.py start
    python engine/watcher.py start --verbose
    python engine/watcher.py test --session <session_id>
    python engine/watcher.py rules
    python engine/watcher.py simulate --pack legal_intake --fields urgency=high,matter_type=personal_injury
"""
import argparse
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
ENGINE_DIR = ROOT_DIR / "engine"
CONFIG_DIR = ROOT_DIR / "config"
OUTPUT_DIR = ROOT_DIR / "output"

sys.path.insert(0, str(ENGINE_DIR))

from local_vault import LocalVault

logger = logging.getLogger("13tmos.watcher")

LINE = "─" * 53


# ═══════════════════════════════════════════════════════════
# Condition Evaluator
# ═══════════════════════════════════════════════════════════

def _resolve_field(record: dict, path: str):
    """Resolve a dotted field path against a vault record.

    Examples:
        "pack" -> record["pack"]
        "fields.urgency" -> record["fields"]["urgency"]
        "session_count" -> special: total vault records for this user
    """
    if path == "session_count":
        return record.get("_session_count", 0)

    parts = path.split(".")
    obj = record
    for part in parts:
        if isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return None
    return obj


def _parse_value(raw: str):
    """Parse a literal value from a condition string."""
    raw = raw.strip()
    # Quoted string
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    # List
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1]
        items = [_parse_value(x.strip()) for x in inner.split(",")]
        return items
    # Boolean
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    # Numeric
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def _eval_simple(record: dict, expr: str) -> bool:
    """Evaluate a single comparison expression.

    Supported operators: ==, !=, >=, <=, >, <, in, not in
    Also supports modulo: session_count % 10 == 0
    """
    expr = expr.strip()

    # Handle modulo expressions: field % N op value
    mod_match = re.match(r'(\S+)\s*%\s*(\d+)\s*(==|!=|>=|<=|>|<)\s*(.+)', expr)
    if mod_match:
        field_path, mod_val, op, rhs_raw = mod_match.groups()
        lhs = _resolve_field(record, field_path)
        if lhs is None:
            return False
        try:
            lhs = int(lhs) % int(mod_val)
        except (TypeError, ValueError):
            return False
        rhs = _parse_value(rhs_raw)
        return _compare(lhs, op, rhs)

    # "not in" must be checked before "in"
    not_in_match = re.match(r'(\S+)\s+not\s+in\s+(.+)', expr)
    if not_in_match:
        field_path, rhs_raw = not_in_match.groups()
        lhs = _resolve_field(record, field_path)
        rhs = _parse_value(rhs_raw)
        if isinstance(rhs, list):
            return str(lhs) not in [str(x) for x in rhs]
        return str(lhs) != str(rhs)

    # "in" operator
    in_match = re.match(r'(\S+)\s+in\s+(.+)', expr)
    if in_match:
        field_path, rhs_raw = in_match.groups()
        lhs = _resolve_field(record, field_path)
        rhs = _parse_value(rhs_raw)
        if isinstance(rhs, list):
            return str(lhs) in [str(x) for x in rhs]
        return str(lhs) == str(rhs)

    # Standard comparison operators
    for op in ("==", "!=", ">=", "<=", ">", "<"):
        if op in expr:
            parts = expr.split(op, 1)
            if len(parts) == 2:
                field_path = parts[0].strip()
                rhs_raw = parts[1].strip()
                lhs = _resolve_field(record, field_path)
                rhs = _parse_value(rhs_raw)
                return _compare(lhs, op, rhs)

    return False


def _compare(lhs, op: str, rhs) -> bool:
    """Compare two values with an operator."""
    if lhs is None:
        return op == "!="

    # Coerce types for comparison
    try:
        if isinstance(rhs, (int, float)) and not isinstance(lhs, (int, float)):
            lhs = float(lhs)
        elif isinstance(lhs, (int, float)) and not isinstance(rhs, (int, float)):
            rhs = float(rhs)
    except (TypeError, ValueError):
        pass

    if op == "==":
        return str(lhs) == str(rhs)
    elif op == "!=":
        return str(lhs) != str(rhs)
    elif op == ">=":
        return float(lhs) >= float(rhs)
    elif op == "<=":
        return float(lhs) <= float(rhs)
    elif op == ">":
        return float(lhs) > float(rhs)
    elif op == "<":
        return float(lhs) < float(rhs)
    return False


def evaluate_condition(record: dict, condition: str) -> bool:
    """Evaluate a compound condition string against a vault record.

    Supports: and, or, not, parentheses (basic)
    """
    condition = condition.strip()

    # Split on " or " first (lower precedence)
    or_parts = _split_boolean(condition, " or ")
    if len(or_parts) > 1:
        return any(evaluate_condition(record, part) for part in or_parts)

    # Split on " and " (higher precedence)
    and_parts = _split_boolean(condition, " and ")
    if len(and_parts) > 1:
        return all(evaluate_condition(record, part) for part in and_parts)

    # Handle "not" prefix
    if condition.startswith("not "):
        return not evaluate_condition(record, condition[4:])

    # Single expression
    return _eval_simple(record, condition)


def _split_boolean(condition: str, operator: str) -> list[str]:
    """Split condition on boolean operator, respecting quoted strings."""
    parts = []
    current = ""
    in_quote = False
    quote_char = ""
    i = 0
    while i < len(condition):
        c = condition[i]
        if c in ('"', "'") and not in_quote:
            in_quote = True
            quote_char = c
            current += c
        elif c == quote_char and in_quote:
            in_quote = False
            current += c
        elif not in_quote and condition[i:i + len(operator)].lower() == operator:
            parts.append(current.strip())
            current = ""
            i += len(operator)
            continue
        else:
            current += c
        i += 1
    if current.strip():
        parts.append(current.strip())
    return parts


# ═══════════════════════════════════════════════════════════
# Format Helpers
# ═══════════════════════════════════════════════════════════

def _format_message(template: str, record: dict) -> str:
    """Format a message template with record values.

    Supports: {pack}, {date}, {session_id}, {fields.key}, {session_count}
    """
    result = template
    # Simple top-level replacements
    for key in ("pack", "date", "type", "session", "user", "manifest"):
        result = result.replace(f"{{{key}}}", str(record.get(key, "?")))
    result = result.replace("{session_id}", str(record.get("session", "?")))
    result = result.replace("{session_count}", str(record.get("_session_count", 0)))

    # Fields replacements: {fields.key}
    fields = record.get("fields", {})
    for match in re.finditer(r'\{fields\.(\w+)\}', template):
        field_name = match.group(1)
        result = result.replace(match.group(0), str(fields.get(field_name, "?")))

    return result


# ═══════════════════════════════════════════════════════════
# VaultWatcher
# ═══════════════════════════════════════════════════════════

class VaultWatcher:
    """Event-driven vault routing. The foam self-organizes."""

    def __init__(self, vault_dir: str = None, rules_path: str = None, identity_path: str = None):
        self.vault_dir = Path(vault_dir) if vault_dir else ROOT_DIR / "vault"
        self.rules_path = Path(rules_path) if rules_path else CONFIG_DIR / "watchers.yaml"
        self.identity_path = Path(identity_path) if identity_path else CONFIG_DIR / "identity.json"

        self.vault = LocalVault(self.vault_dir)
        self.rules: list[dict] = []
        self.identity: dict = {}
        self._observer = None
        self._running = False
        self._verbose = False

        # Track files we've already processed (avoid re-triggering on modify)
        self._seen_files: set[str] = set()

        self._load_rules()
        self._load_identity()

    def _load_rules(self):
        """Load watcher rules from YAML config."""
        if not self.rules_path.exists():
            logger.warning("Watcher rules not found: %s", self.rules_path)
            return

        try:
            import yaml
            data = yaml.safe_load(self.rules_path.read_text())
            self.rules = data.get("watchers", []) if data else []
            logger.info("Loaded %d watcher rules from %s", len(self.rules), self.rules_path)
        except ImportError:
            logger.error("PyYAML required for watcher rules — pip install pyyaml")
        except Exception as e:
            logger.error("Failed to load watcher rules: %s", e)

    def _load_identity(self):
        """Load local identity."""
        if self.identity_path.exists():
            self.identity = json.loads(self.identity_path.read_text())
        else:
            self.identity = {"user_id": "local", "name": "Local User"}

    # ── Core Event Handler ──────────────────────────────────

    def on_vault_write(self, record: dict) -> list[dict]:
        """Called when a new vault record is detected. Evaluates and fires rules."""
        # Enrich record with session_count
        user_id = record.get("user", "local")
        all_sessions = self.vault.list_sessions(user_id=user_id)
        record["_session_count"] = len(all_sessions)

        matched = self.evaluate_rules(record)

        for rule in matched:
            self.fire_rule(rule, record)

        return matched

    def evaluate_rules(self, record: dict) -> list[dict]:
        """Return list of rules that match the record."""
        matched = []
        for rule in self.rules:
            condition = rule.get("condition", "")
            if not condition:
                continue

            try:
                if evaluate_condition(record, condition):
                    matched.append(rule)
                    # First match wins unless continue: true
                    if not rule.get("continue", False):
                        break
            except Exception as e:
                logger.warning("Rule '%s' evaluation error: %s", rule.get("name", "?"), e)

        return matched

    def fire_rule(self, rule: dict, record: dict):
        """Execute a rule's action against the matching record."""
        action = rule.get("action", "")
        name = rule.get("name", "unknown")
        now = datetime.now().strftime("%H:%M:%S")

        # Print notification if present
        notify = rule.get("notify")
        if notify:
            msg = _format_message(notify, record)
            print(f"\n[{now}] ⚡ WATCHER: {name}")
            print(f"  {msg}")

        if action == "load_pack":
            self._action_load_pack(rule, record)
        elif action == "notify":
            message = rule.get("message", "")
            if message:
                msg = _format_message(message, record)
                if not notify:  # Don't double-print
                    print(f"\n[{now}] WATCHER: {name}")
                    print(f"  {msg}")
        elif action == "write_summary":
            self._action_write_summary(rule, record)
        elif action == "send_email":
            self._action_send_email(rule, record)
        elif action == "send_channel":
            self._action_send_channel(rule, record)
        elif action == "start_session":
            self._action_start_session(rule, record)
        elif action == "chain_web":
            self._action_chain_web(rule, record)
        else:
            logger.warning("Unknown watcher action: %s", action)

    def _action_load_pack(self, rule: dict, record: dict):
        """Spawn a console session for the target pack."""
        target_pack = rule.get("pack", "")
        if not target_pack:
            logger.error("load_pack rule '%s' missing pack field", rule.get("name"))
            return

        session_id = record.get("session", "")
        inherit_flag = rule.get("inherit", False)

        cmd = [sys.executable, str(ENGINE_DIR / "console.py"), "--pack", target_pack]
        if inherit_flag and session_id:
            cmd.extend(["--session", session_id])

        logger.info("Firing load_pack: %s (inherit=%s, source=%s)",
                     target_pack, inherit_flag, session_id[:8] if session_id else "none")

        # Non-blocking subprocess — the watcher continues monitoring
        subprocess.Popen(
            cmd,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

    def _action_write_summary(self, rule: dict, record: dict):
        """Run vault query and write summary to output/."""
        user_id = record.get("user", "local")
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_file = OUTPUT_DIR / f"summary_{user_id}_{date_str}.md"

        # Query all records for this user
        sessions = self.vault.list_sessions(user_id=user_id)

        lines = [
            f"# Vault Summary — {user_id}",
            f"Generated: {date_str}",
            f"Total sessions: {len(sessions)}",
            "",
            "## Sessions",
            "",
        ]

        for s in sessions:
            sid = s.get("session", "?")[:8]
            lines.append(f"- [{s.get('date', '?')}] {s.get('pack', '?')} ({sid}) — {s.get('type', '?')}")

        output_file.write_text("\n".join(lines))
        logger.info("Summary written: %s", output_file)
        print(f"  Summary written: {output_file}")

    def _action_send_email(self, rule: dict, record: dict):
        """Send an email when a rule fires.

        Rule fields:
          to:      recipient email (supports {fields.email} templates)
          subject: email subject (supports templates)
          body:    email body text (supports templates)
        """
        to_raw = rule.get("to", "")
        subject_raw = rule.get("subject", "")
        body_raw = rule.get("body", "")

        if not to_raw or not subject_raw or not body_raw:
            logger.error("send_email rule '%s' missing to/subject/body", rule.get("name"))
            return

        to = _format_message(to_raw, record)
        subject = _format_message(subject_raw, record)
        body = _format_message(body_raw, record)

        try:
            from email_service import send_email
            result = send_email(to=to, subject=subject, html=f"<p>{body}</p>", text=body)
            if result.get("success"):
                logger.info("Watcher email sent: to=%s subject=%s", to, subject)
                print(f"  Email sent to {to}: {subject}")
            else:
                logger.warning("Watcher email failed: %s", result.get("error", "unknown"))
                print(f"  Email failed: {result.get('error', 'unknown')}")
        except ImportError:
            logger.warning("email_service not available — send_email action skipped")
            print("  Email skipped (email_service not configured)")
        except Exception as e:
            logger.error("send_email action failed: %s", e)
            print(f"  Email error: {e}")

    def _action_send_channel(self, rule: dict, record: dict):
        """Send a message to a channel/sender via the session runner.

        Rule fields:
          channel:   target channel (telegram, whatsapp, sms, email, etc.)
          sender_id: recipient identifier (supports templates)
          message:   message text (supports templates)
          pack_id:   pack to use for the session (optional, defaults to current)
        """
        import asyncio

        channel = rule.get("channel", "")
        sender_id_raw = rule.get("sender_id", "")
        message_raw = rule.get("message", "")

        if not channel or not sender_id_raw or not message_raw:
            logger.error("send_channel rule '%s' missing channel/sender_id/message",
                         rule.get("name"))
            return

        sender_id = _format_message(sender_id_raw, record)
        message = _format_message(message_raw, record)
        pack_id = rule.get("pack_id", record.get("pack", "guest"))

        try:
            from session_runner import SessionRunner
            runner = SessionRunner()
            reply = asyncio.run(
                runner.handle_message(channel, sender_id, message, default_pack=pack_id)
            )
            logger.info("Watcher sent to %s/%s: %s", channel, sender_id[:8], message[:50])
            print(f"  Sent to {channel}/{sender_id[:12]}")
        except Exception as e:
            logger.error("send_channel action failed: %s", e)
            print(f"  Channel send error: {e}")

    def _action_start_session(self, rule: dict, record: dict):
        """Seed a new session on a channel for a recipient.

        Rule fields:
          channel:   target channel
          sender_id: recipient identifier (supports templates)
          pack:      pack ID for the new session
          name:      recipient name (supports templates)
          context:   seed context (supports templates, optional)
        """
        channel = rule.get("channel", "")
        sender_id_raw = rule.get("sender_id", "")
        pack_id = rule.get("pack", "")
        name_raw = rule.get("name", "")

        if not channel or not sender_id_raw or not pack_id:
            logger.error("start_session rule '%s' missing channel/sender_id/pack",
                         rule.get("name"))
            return

        sender_id = _format_message(sender_id_raw, record)
        name = _format_message(name_raw, record) if name_raw else sender_id
        context_raw = rule.get("context", "")
        context = _format_message(context_raw, record) if context_raw else ""

        try:
            from session_runner import SessionRunner
            runner = SessionRunner()
            result = runner.seed_session(
                channel=channel,
                sender_id=sender_id,
                pack_id=pack_id,
                name=name,
                context=context,
            )
            if "error" in result:
                logger.warning("start_session failed: %s", result["error"])
                print(f"  Session seed failed: {result['error']}")
            else:
                logger.info("Watcher seeded session: %s/%s pack=%s",
                            channel, sender_id[:8], pack_id)
                print(f"  Session seeded: {channel}/{sender_id[:12]} → {pack_id}")
        except Exception as e:
            logger.error("start_session action failed: %s", e)
            print(f"  Session seed error: {e}")

    def _action_chain_web(self, rule: dict, record: dict):
        """Load a web definition and begin routing."""
        web_name = rule.get("web", "")
        web_path = CONFIG_DIR / "webs" / f"{web_name}.yaml"

        if not web_path.exists():
            logger.error("Web definition not found: %s", web_path)
            return

        logger.info("Chaining web: %s", web_name)
        # Web chaining would load the YAML and process routes
        # For now, notify — full web orchestration is Session 04 territory
        print(f"  Web chain requested: {web_name} (route via orchestrator)")

    # ── File System Watching ────────────────────────────────

    def start(self, verbose: bool = False):
        """Begin watching vault_dir for new .json files."""
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        self._verbose = verbose
        self._running = True

        # Index existing files so we don't trigger on boot
        if self.vault_dir.exists():
            for path in self.vault_dir.rglob("*.json"):
                self._seen_files.add(str(path))

        watcher_self = self

        class VaultHandler(FileSystemEventHandler):
            def on_created(self, event):
                if event.is_directory or not event.src_path.endswith(".json"):
                    return
                watcher_self._handle_new_file(event.src_path)

            def on_modified(self, event):
                if event.is_directory or not event.src_path.endswith(".json"):
                    return
                # Only process if we haven't seen this file before
                # (watchdog sometimes fires modify after create)
                if event.src_path not in watcher_self._seen_files:
                    watcher_self._handle_new_file(event.src_path)

        self._observer = Observer()
        self._observer.schedule(VaultHandler(), str(self.vault_dir), recursive=True)
        self._observer.start()

        print(f"\nWatcher active — monitoring vault/ for new records")
        print(f"Active rules: {len(self.rules)}")
        if verbose:
            for rule in self.rules:
                print(f"  {rule.get('name', '?')}: {rule.get('condition', '?')}")
        print()

    def _handle_new_file(self, path: str):
        """Process a newly detected vault file."""
        self._seen_files.add(path)

        # Small delay to ensure file is fully written
        time.sleep(0.2)

        try:
            record = json.loads(Path(path).read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read new vault file %s: %s", path, e)
            return

        session_id = record.get("session", "?")
        pack = record.get("pack", "?")

        if self._verbose:
            print(f"\n[VAULT] New record: {pack}/{session_id[:8]}")

        self.on_vault_write(record)

    def stop(self):
        """Clean shutdown."""
        self._running = False
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        print("Watcher stopped.")

    def is_running(self) -> bool:
        return self._running

    # ── Background Thread Mode (for console integration) ───

    def start_background(self, verbose: bool = False) -> threading.Thread:
        """Start the watcher in a background thread. Returns the thread."""
        thread = threading.Thread(target=self.start, args=(verbose,), daemon=True)
        thread.start()
        return thread


# ═══════════════════════════════════════════════════════════
# CLI Commands
# ═══════════════════════════════════════════════════════════

def cmd_start(args):
    """Start the watcher (blocking)."""
    watcher = VaultWatcher()
    if not watcher.rules:
        print("No watcher rules found. Create config/watchers.yaml first.")
        return

    watcher.start(verbose=args.verbose)

    try:
        while watcher.is_running():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n")
        watcher.stop()


def cmd_rules(args):
    """List all active rules."""
    watcher = VaultWatcher()

    if not watcher.rules:
        print("\nNo watcher rules loaded.")
        print(f"Expected: {watcher.rules_path}")
        return

    print(f"\nACTIVE RULES — {len(watcher.rules)} loaded")
    print(LINE)
    for rule in watcher.rules:
        name = rule.get("name", "?")
        action = rule.get("action", "?")
        target = ""
        if action == "load_pack":
            target = f" → load {rule.get('pack', '?')}"
        elif action == "send_email":
            target = f" → email {rule.get('to', '?')}"
        elif action == "send_channel":
            target = f" → {rule.get('channel', '?')}/{rule.get('sender_id', '?')[:12]}"
        elif action == "start_session":
            target = f" → seed {rule.get('channel', '?')} → {rule.get('pack', '?')}"
        elif action == "chain_web":
            target = f" → chain {rule.get('web', '?')}"
        elif action == "write_summary":
            target = " → write summary"
        trigger = rule.get("trigger", "vault_write")
        print(f"  {name:<28} {trigger}{target}")
    print()


def cmd_test(args):
    """Test rules against an existing vault record."""
    if not args.session:
        print("Error: --session required")
        return

    watcher = VaultWatcher()
    vault = LocalVault()

    record = vault.read(args.session)
    if not record:
        print(f"No vault record found for session: {args.session}")
        return

    # Enrich with session_count
    user_id = record.get("user", "local")
    all_sessions = vault.list_sessions(user_id=user_id)
    record["_session_count"] = len(all_sessions)

    print(f"\nTesting rules against session: {args.session[:8]}")
    print(f"  pack: {record.get('pack')}, user: {record.get('user')}")
    print(LINE)

    matched = watcher.evaluate_rules(record)

    if not matched:
        print("No rules matched.")
    else:
        for rule in matched:
            name = rule.get("name", "?")
            action = rule.get("action", "?")
            print(f"MATCH: {name}")
            print(f"  Action: {action}", end="")
            if action == "load_pack":
                print(f" → {rule.get('pack', '?')}")
                print(f"  Inherit: {rule.get('inherit', False)}")
            elif action == "notify":
                msg = _format_message(rule.get("message", ""), record)
                print(f"\n  Message: \"{msg}\"")
            else:
                print()
            notify = rule.get("notify")
            if notify:
                print(f"  Notify: \"{_format_message(notify, record)}\"")

    print(f"\n({len(matched)} rule{'s' if len(matched) != 1 else ''} matched, "
          f"{len(watcher.rules) - len(matched)} rules skipped)")
    print()


def cmd_simulate(args):
    """Simulate a vault write with a synthetic record."""
    if not args.pack:
        print("Error: --pack required")
        return

    watcher = VaultWatcher()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Parse fields
    fields = {}
    if args.fields:
        for pair in args.fields.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                fields[k.strip()] = v.strip()

    # Build synthetic record
    record = {
        "pack": args.pack,
        "user": "local",
        "date": date_str,
        "type": "session_record",
        "fields": fields,
        "session": "sim-00000000-0000-0000-0000-000000000000",
        "manifest": "1.0.0",
    }

    # Enrich with session_count
    all_sessions = watcher.vault.list_sessions(user_id="local")
    record["_session_count"] = len(all_sessions)

    fields_display = ", ".join(f"{k}={v}" for k, v in fields.items()) if fields else "(none)"
    print(f"\nSimulating vault write: pack={args.pack}, {fields_display}")
    print(LINE)

    matched = watcher.evaluate_rules(record)

    if not matched:
        print("No rules matched.")
    else:
        for rule in matched:
            name = rule.get("name", "?")
            action = rule.get("action", "?")
            print(f"MATCH: {name}")
            print(f"  Action: {action}", end="")
            if action == "load_pack":
                print(f" → {rule.get('pack', '?')}")
                print(f"  Inherit: {rule.get('inherit', False)}")
            elif action == "notify":
                msg = _format_message(rule.get("message", ""), record)
                print(f"\n  Message: \"{msg}\"")
            else:
                print()
            notify = rule.get("notify")
            if notify:
                print(f"  Notify: \"{_format_message(notify, record)}\"")

    print(f"\n({len(matched)} rule{'s' if len(matched) != 1 else ''} matched, "
          f"{len(watcher.rules) - len(matched)} rules skipped)")
    print()


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="13TMOS Watcher — event-driven vault routing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="The Vault is the event bus. The foam self-organizes.",
    )

    sub = parser.add_subparsers(dest="command")

    p_start = sub.add_parser("start", help="Start the watcher (blocking)")
    p_start.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    sub.add_parser("rules", help="List all active rules")

    p_test = sub.add_parser("test", help="Test rules against a vault record")
    p_test.add_argument("--session", "-s", required=True, help="Session ID to test")

    p_sim = sub.add_parser("simulate", help="Simulate a vault write")
    p_sim.add_argument("--pack", "-p", required=True, help="Pack ID")
    p_sim.add_argument("--fields", "-f", help="Comma-separated key=value fields")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "start":
        cmd_start(args)
    elif args.command == "rules":
        cmd_rules(args)
    elif args.command == "test":
        cmd_test(args)
    elif args.command == "simulate":
        cmd_simulate(args)


if __name__ == "__main__":
    main()
