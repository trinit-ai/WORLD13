# WORLD13 — Simulation Theatres

A **theatre** is a named, self-contained simulation fork. Each theatre specifies:
- Which protocol pack(s) agents run
- The agent population (names, archetypes, K₀, λ, cycle phase, backstory)
- The context envelope (which of the 14 Set/Setting axes are fixed vs. sampled)
- The Ω coefficient and tick parameters
- What output/analysis is generated

The WORLD13 engine is invariant across all theatres. Only the parameters change.

---

## Directory Structure

```
theatres/
├── _template/              — Copy this to start a new theatre
│   ├── manifest.yaml       — All simulation parameters
│   └── README.md
│
├── enlightened_duck/       — Duck oracle: 10 agents, 3 questions, life path divergence
├── org_mirror/             — Organizational dynamics simulation
├── policy_lab/             — Policy scenario modeling fork
└── ...                     — Add more as needed
```

---

## How to Add a Theatre

1. Copy `_template/` to `theatres/{your_name}/`
2. Fill in `manifest.yaml`
3. Run: `python3 theatres/run_theatre.py --theatre {your_name}`
4. Results written to `data/theatres/{your_name}/` in the Vault

---

## The Invariant Layer

All theatres share: TVR Equations 1–8, the adjacency algorithm, the Set & Setting
context sampler (14 axes, 210 leaf nodes), the SQLite Vault, and the session runner.
None of these change between theatres. The governance is the constant.
The world is the variable.
