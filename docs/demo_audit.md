# 13TMOS Compliance Demo

## The Claim

A non-technical compliance officer can verify that an AI session ran in accordance with its governing protocol — without reading code, without reviewing logs, without trusting the vendor.

## The Demo

### Step 1: Read the manifest (2 minutes)

Open `protocols/packs/legal_intake/MANIFEST.md`. A compliance officer reads it. They now know exactly what the AI is authorized to do, prohibited from doing, and required to produce.

This is not a log. This is not a config file. This is a behavioral contract written in plain English that defines the session before it runs.

### Step 2: Watch a session run (3 minutes)

```
> load legal_intake
```

The session runs. Fields are captured. The deliverable is produced. The Vault record is written.

The compliance officer watches the AI do exactly what the manifest said it would do. No more, no less.

### Step 3: Run the audit (1 minute)

```
> load vault_audit
```

The audit reads every Vault record in scope. For each session, it retrieves the governing manifest, compares the deliverable against the manifest's requirements, and produces a verdict.

```
Session abc123 | legal_intake v1.1 | COMPLIANT
```

All required fields present. No prohibited actions detected. Completion criteria met.

### Step 4: The verdict

The compliance officer who read the manifest in Step 1 can verify that what they read is what happened. The manifest was the specification. The Vault record was the execution. The audit measured the gap.

The vault hash — a SHA-256 digest of every record included in the audit — is the tamper-evident seal. If any record is modified after the audit, re-running produces a different hash.

## What no agentic framework can show

1. **The manifest**: what was authorized before the session ran
2. **The audit**: verification that the session matched the manifest
3. **The hash**: tamper-evident seal on the institutional record

Every competitor offers logs. Logs are forensic — you read them after something goes wrong to figure out what happened.

A manifest is prescriptive — you read it before the session runs and know exactly what will happen. The audit closes the loop.

## The compliance stack

```
Manifest     → defines authorization, prohibition, required deliverables
Pack         → governs session behavior within manifest boundaries
Vault        → records what actually happened (dimensional, immutable)
Audit        → compares manifest spec against vault execution
Hash         → tamper-evident seal on the institutional record
Archive      → preserves every manifest version for retroactive audit
```

Each layer is human-readable. Each layer is versioned. Each layer is independently verifiable.

## Why this matters

- **Regulated industries** need to prove the AI did what it was supposed to do. The manifest + audit is that proof.
- **Enterprise procurement** requires governance artifacts. The manifest is the governance artifact.
- **Legal defensibility** requires a specification that existed before the incident. The manifest is dated, versioned, and archived.
- **Insurance underwriting** for AI liability requires demonstrable controls. The audit report is the control evidence.

Logs tell you what happened after something goes wrong. A manifest tells you what will happen before anything runs. The audit closes the loop.

That is auditable AI.
