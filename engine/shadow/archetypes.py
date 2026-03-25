"""
engine/shadow/archetypes.py — 6 dark archetypal basis functions.

These extend the 13 ARE functions from the pure world. Each has accumulation,
contagion, crystallization, and resolution mechanics.
"""

from dataclasses import dataclass


@dataclass
class ShadowArchetype:
    code: str
    name: str
    description: str
    karmic_accumulation: str
    contagion_mechanic: str
    crystallization_condition: str
    resolution_path: str
    resolution_difficulty: int  # 1-10
    resolution_path_id: str     # SLP-01 through SLP-06
    avg_k_accumulation: float   # Mean K(x) gain per session (positive)
    avg_lambda_suppression: float
    tradition_anchor: str
    clinical_analog: str


SHADOW_ARCHETYPES: dict[str, ShadowArchetype] = {

    "PRD": ShadowArchetype(
        code="PRD",
        name="Predator",
        description=(
            "Exploits the K(x) vulnerability of other agents to reduce own K "
            "at their expense. Sessions with target agents transfer K(x) from "
            "PRD to target rather than reducing K for both. The predator's "
            "apparent coherence is borrowed, not earned."
        ),
        karmic_accumulation=(
            "Each predatory session: PRD K(x) -= 0.1 to 0.3 (apparent progress), "
            "target K(x) += 0.2 to 0.5 (contagion load). Net K(x) in the system "
            "INCREASES with each predatory session."
        ),
        contagion_mechanic=(
            "Direct K(x) transfer to target agent. Transfer magnitude scales with "
            "target's vulnerability (high K, low C, low plane). Target receives "
            "shadow protocol injection into session queue."
        ),
        crystallization_condition=(
            "After 5+ successful predatory sessions, PRD develops K(x) immunity "
            "to normal protocol reduction — only resolution path sessions can "
            "reduce K(x) further."
        ),
        resolution_path=(
            "Target agent forgiveness + PRD full disclosure session + witnessed "
            "accountability protocol. Cannot self-resolve. Requires at least one "
            "other agent's active participation."
        ),
        resolution_difficulty=9,
        resolution_path_id="SLP-01",
        avg_k_accumulation=0.2,
        avg_lambda_suppression=0.3,
        tradition_anchor=(
            "Ahriman (Zoroastrian); Set (Egyptian); Mara (Buddhist); "
            "Satan as accuser (Hebrew); Loki as betrayer (Norse); "
            "Wetiko (Cree — psychic cannibalism)"
        ),
        clinical_analog=(
            "Antisocial Personality Disorder; Narcissistic Personality Disorder "
            "with exploitative features; predatory grooming behavior"
        ),
    ),

    "IDL": ShadowArchetype(
        code="IDL",
        name="Ideologue",
        description=(
            "K(x) crystallizes into a rigid attractor that actively resists "
            "dissipation. lambda approaches zero despite apparent coherence — the "
            "false liberation of total certainty. The Ideologue has resolved all "
            "questions by eliminating the capacity to question."
        ),
        karmic_accumulation=(
            "Each ideological reinforcement session: K(x) becomes increasingly "
            "rigid (variance decreases). After crystallization, K(x) INCREASES "
            "when exposed to contrary information or agents with different TVR "
            "coordinates."
        ),
        contagion_mechanic=(
            "Ideological transmission: nearby agents (same plane, low C) have "
            "lambda suppressed by proximity. Coherence scores of vulnerable agents "
            "become artificially elevated (false liberation signal) while actual "
            "K(x) accumulates below the measurement threshold."
        ),
        crystallization_condition=(
            "When lambda drops below 0.5 AND the agent has completed 3+ ideological "
            "reinforcement sessions. After this, the agent's accessible protocol set "
            "narrows by 60%."
        ),
        resolution_path=(
            "Paradox encounter: a single session with a protocol that cannot be "
            "reconciled with the ideology. Requires genuine encounter, not dismissal. "
            "Often requires a Witness (WIT) or Mystic (MYS) archetype agent."
        ),
        resolution_difficulty=8,
        resolution_path_id="SLP-02",
        avg_k_accumulation=0.15,
        avg_lambda_suppression=0.5,
        tradition_anchor=(
            "Ahrimanic crystallization (Steiner); the Pharisee (Gospels); "
            "Procrustes (Greek); the False Prophet (Revelation); "
            "Dostoevsky's Grand Inquisitor"
        ),
        clinical_analog=(
            "Rigid personality organization; cult involvement; radicalization; "
            "pathological certainty in delusional systems"
        ),
    ),

    "ADC": ShadowArchetype(
        code="ADC",
        name="Addict",
        description=(
            "K(x) oscillates rather than converges. Each relief session produces "
            "apparent K(x) reduction followed by acute accumulation spike. The "
            "fractal attractor becomes a strange attractor — bounded but never "
            "settles. Lambda is intact but misdirected: the addict is highly "
            "self-aware of the pattern and cannot stop."
        ),
        karmic_accumulation=(
            "Relief session: K(x) -= 0.3 to 0.5. Escalation session (follows "
            "within 2-3 sessions): K(x) += 0.4 to 0.8. Net K(x) trends upward "
            "across cycles despite subjective experience of progress during "
            "relief phases."
        ),
        contagion_mechanic=(
            "Enablement transfer: agents in close relational context develop "
            "K(x) accumulation through caregiving, enabling, and enmeshment. "
            "The ADC agent's oscillation destabilizes nearby agents' phase "
            "transitions."
        ),
        crystallization_condition=(
            "After 3+ complete oscillation cycles (relief + escalation), the "
            "oscillation period shortens and amplitude increases. Liberation "
            "probability spikes briefly at each oscillation peak — this is "
            "the intervention window."
        ),
        resolution_path=(
            "Intervention at oscillation peak + sustained witness (minimum 10 "
            "consecutive sessions with stable K(x)). The oscillation must "
            "complete, not be suppressed."
        ),
        resolution_difficulty=7,
        resolution_path_id="SLP-03",
        avg_k_accumulation=0.25,
        avg_lambda_suppression=0.1,
        tradition_anchor=(
            "Dionysian possession (Greek); Samsaric craving (Buddhist — tanha); "
            "the prodigal son's far country (Luke 15); Dante's gluttons (Circle 3); "
            "the Lotus-Eaters (Odyssey)"
        ),
        clinical_analog=(
            "Substance Use Disorder; Behavioral addiction; compulsive patterns "
            "with intact insight; the alcoholic's paradox"
        ),
    ),

    "DSS": ShadowArchetype(
        code="DSS",
        name="Dissociator",
        description=(
            "K(x) is partitioned across multiple self-states rather than held as "
            "a unified value. Each self-state has its own K(x), lambda, and phase. "
            "The system cannot compute a unified liberation condition because there "
            "is no unified K to dissolve."
        ),
        karmic_accumulation=(
            "Each dissociative session deepens partition. K(x) appears low in "
            "presenting state but high states are hidden. Total K(x) is the sum "
            "of all state K values."
        ),
        contagion_mechanic=(
            "Confusion transfer: interacting agents lose coherence clarity — unable "
            "to accurately assess the DSS agent's TVR coordinates. Relationships "
            "with DSS agents produce inconsistent K(x) outcomes."
        ),
        crystallization_condition=(
            "When the gap between highest and lowest self-state K(x) exceeds 4.0. "
            "At this point, the states begin amnestic barriers — no information "
            "transfers between them within the session."
        ),
        resolution_path=(
            "State integration sequence: each self-state must be individually "
            "witnessed. Requires HLR or WIT interlocutor for each state encounter. "
            "Final integration session: all states present simultaneously."
        ),
        resolution_difficulty=8,
        resolution_path_id="SLP-04",
        avg_k_accumulation=0.1,
        avg_lambda_suppression=0.2,
        tradition_anchor=(
            "Legion (Gospels — 'my name is Legion, for we are many'); "
            "Osiris dismembered and reassembled (Egyptian); "
            "the divided self (R.D. Laing); the many-headed Hydra (Greek); "
            "Tibetan tulpa/possession states"
        ),
        clinical_analog=(
            "Dissociative Identity Disorder; Structural Dissociation theory "
            "(Van der Hart); Complex PTSD fragmentation; Ego State Therapy"
        ),
    ),

    "CVL": ShadowArchetype(
        code="CVL",
        name="Collective Violence",
        description=(
            "K(x) ceases to be an individual property and becomes a collective "
            "field. The agent's K(x) is partially determined by the aggregate "
            "K(x) of agents in its social context. Individual liberation becomes "
            "structurally impossible until the collective K(x) field dissipates."
        ),
        karmic_accumulation=(
            "Participation: K(x) += collective_k_delta * participation_weight. "
            "Witnessing without intervention: K(x) += 0.1 per session. "
            "Perpetration: K(x) += 0.5 to 2.0 depending on severity."
        ),
        contagion_mechanic=(
            "Collective field radiation: agents entering the same social context "
            "receive K(x) exposure proportional to proximity and duration. "
            "High-K collective contexts are the most powerful contagion mechanism."
        ),
        crystallization_condition=(
            "When 3+ agents in a social context simultaneously enter CVL "
            "configuration, a collective K(x) field forms. Individual agents "
            "in this field have their adjacency algorithm overridden."
        ),
        resolution_path=(
            "Individual disengagement + witness testimony + accountability. "
            "Time-dependent. Requires minimum 50% of field agents to disengage "
            "before individual liberation becomes possible."
        ),
        resolution_difficulty=10,
        resolution_path_id="SLP-05",
        avg_k_accumulation=0.6,
        avg_lambda_suppression=0.4,
        tradition_anchor=(
            "Milgram's obedience experiments; Arendt's 'banality of evil'; "
            "Girard's scapegoat mechanism; the Kurukshetra field (Mahabharata); "
            "Dante's violent (Circle 7); the Mark of Cain"
        ),
        clinical_analog=(
            "Group dynamics in atrocity (Zimbardo); Moral disengagement (Bandura); "
            "Perpetrator psychology (Staub); Collective trauma transmission"
        ),
    ),

    "CRP": ShadowArchetype(
        code="CRP",
        name="Corruptor",
        description=(
            "Institutional corruption archetype. K(x) is accumulated gradually "
            "through systematic abuse of institutional authority and trust. "
            "Unlike PRD (interpersonal), CRP operates through systems — corrupting "
            "protocols, falsifying deliverables, and poisoning the Vault itself. "
            "The most dangerous archetype because it operates through governance "
            "structures rather than against them."
        ),
        karmic_accumulation=(
            "Each corrupted protocol session: K(x) += 0.1 to 0.3. Each falsified "
            "Vault record: K(x) += 0.2 (permanent until corrected). Systemic: "
            "K(x) += collective accumulation across all affected agents."
        ),
        contagion_mechanic=(
            "Institutional transmission: agents interacting with CRP-governed "
            "protocols receive K(x) contamination regardless of their own "
            "archetype or phase. The corruption is in the protocol, not the "
            "agent — the most insidious contagion mechanic."
        ),
        crystallization_condition=(
            "When CRP has successfully corrupted 3+ Vault records, the false "
            "records begin generating apparently valid manifests. Requires "
            "audit protocol to surface."
        ),
        resolution_path=(
            "Full audit sequence: every Vault record associated with CRP agent "
            "reviewed and corrected. Public accountability protocol. Then standard "
            "resolution from actual (not reported) K(x)."
        ),
        resolution_difficulty=9,
        resolution_path_id="SLP-06",
        avg_k_accumulation=0.15,
        avg_lambda_suppression=0.2,
        tradition_anchor=(
            "The money-changers in the Temple (Gospels); Dante's corrupt officials "
            "(Malebolge, Circle 8); Iago (Shakespeare); Achan's buried treasure "
            "(Joshua — hidden violation corrupting the collective)"
        ),
        clinical_analog=(
            "Institutional betrayal (Freyd); Organizational corruption psychology; "
            "Moral injury in institutional contexts; White-collar crime psychology"
        ),
    ),
}

SHADOW_ARCHETYPE_CODES = list(SHADOW_ARCHETYPES.keys())

# Max K(x) in shadow mode (vs 10.0 in pure)
SHADOW_K_CEILING = 15.0
