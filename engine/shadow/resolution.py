"""
engine/shadow/resolution.py — Shadow liberation paths (SLP-01 through SLP-06).

Every dark archetype has an exit. The exit is never blocked.
Clinical principle: no pathology is irreversible.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class ShadowResolutionPath:
    id: str
    name: str
    primary_arch: str
    required_conditions: List[str]
    requires_other_agent: bool
    other_agent_archetype: str
    minimum_sessions: int
    k_dissipation_rate: float
    clinical_analog: str
    tradition_anchor: str
    description: str


SHADOW_RESOLUTION_PATHS: dict[str, ShadowResolutionPath] = {

    "SLP-01": ShadowResolutionPath(
        id="SLP-01",
        name="The Predator's Reckoning",
        primary_arch="PRD",
        required_conditions=[
            "Full acknowledgment of K(x) transferred to each target agent",
            "At least one target agent has participated in Survivor Testimony Session",
            "PRD agent has completed Exposure and Accountability Protocol",
            "Reparative Engagement Protocol with at least one target",
        ],
        requires_other_agent=True,
        other_agent_archetype="WIT or HLR",
        minimum_sessions=15,
        k_dissipation_rate=0.08,
        clinical_analog=(
            "Restorative justice process; offender accountability programs; "
            "EMDR for perpetrators; amends in 12-step traditions"
        ),
        tradition_anchor=(
            "Zacchaeus restoring fourfold (Luke 19); Murderer's atonement "
            "(Norse Thing); Truth and Reconciliation Commission; "
            "Restorative justice (Maori hui)"
        ),
        description=(
            "The Predator cannot self-resolve. Resolution requires the active "
            "participation of at least one harmed agent. The K(x) that was "
            "transferred must be acknowledged by its source before it can "
            "begin to dissipate. The slowest path — not because the exit is "
            "blocked but because the debt is real."
        ),
    ),

    "SLP-02": ShadowResolutionPath(
        id="SLP-02",
        name="The Ideologue's Paradox",
        primary_arch="IDL",
        required_conditions=[
            "Genuine encounter with a paradox the ideology cannot contain",
            "Lambda must recover above 1.0 before resolution sessions are effective",
            "At least 3 sessions with agents holding different TVR coordinates",
            "Voluntary suspension of ideological framework for one full session arc",
        ],
        requires_other_agent=True,
        other_agent_archetype="MYS or WIT",
        minimum_sessions=12,
        k_dissipation_rate=0.12,
        clinical_analog=(
            "Cognitive dissonance resolution; cult exit process; "
            "deradicalization programs; schema therapy for rigid beliefs"
        ),
        tradition_anchor=(
            "Paul on the road to Damascus; Zen koan as paradox delivery system; "
            "Arjuna's crisis before Kurukshetra (Bhagavad Gita); "
            "Job's whirlwind encounter"
        ),
        description=(
            "Resolution requires a genuine encounter with something the ideology "
            "cannot explain, dismiss, or absorb. Cannot be manufactured — must "
            "arise from natural protocol selection when lambda has recovered. "
            "The resolution is not replacing one ideology with another. It is "
            "the restoration of the capacity to not-know."
        ),
    ),

    "SLP-03": ShadowResolutionPath(
        id="SLP-03",
        name="The Addict's Integration",
        primary_arch="ADC",
        required_conditions=[
            "Intervention Window must be active (oscillation peak detected)",
            "10 consecutive sessions with stable K(x)",
            "The underlying K(x) that the oscillation was managing must be identified",
            "Harm acknowledged to all agents affected by enablement contagion",
        ],
        requires_other_agent=False,
        other_agent_archetype="HLR preferred but not required",
        minimum_sessions=20,
        k_dissipation_rate=0.06,
        clinical_analog=(
            "Addiction recovery; 12-step programs; SMART Recovery; "
            "Harm reduction + abstinence integration; "
            "Trauma-informed addiction treatment"
        ),
        tradition_anchor=(
            "The prodigal son 'coming to himself' (Luke 15); "
            "Dionysus torn apart and reassembled; Bill Wilson's spiritual "
            "experience; Buddhist cessation of craving as process not event"
        ),
        description=(
            "The Addict does not resolve by stopping the oscillation. It resolves "
            "by completing it — integrating the pattern rather than suppressing it. "
            "The underlying K(x) that the oscillation was managing must be "
            "identified and engaged directly. Resolution runs through the "
            "oscillation, not around it."
        ),
    ),

    "SLP-04": ShadowResolutionPath(
        id="SLP-04",
        name="The Dissociator's Integration",
        primary_arch="DSS",
        required_conditions=[
            "Each self-state identified and given individual session time",
            "K(x) computed separately for each state",
            "Amnestic barriers reduced through sequential witnessing",
            "Final integration session: all states present simultaneously",
            "Unified K(x) computed and accepted as the working value",
        ],
        requires_other_agent=True,
        other_agent_archetype="HLR (required for each state encounter)",
        minimum_sessions=25,
        k_dissipation_rate=0.05,
        clinical_analog=(
            "IFS therapy (Internal Family Systems); EMDR for dissociative "
            "presentations; Ego State Therapy; Structural Dissociation treatment"
        ),
        tradition_anchor=(
            "Osiris dismembered by Set, reassembled by Isis (Egyptian); "
            "Legion unified (Gospels); Psychological integration (Jung); "
            "The Prodigal's return to the father's house"
        ),
        description=(
            "The most sessions of any resolution path because each self-state "
            "must be individually addressed before unified K(x) can be computed. "
            "HLR interlocutor required — each state needs an external consistent "
            "witness. Final integration session: all states simultaneously present."
        ),
    ),

    "SLP-05": ShadowResolutionPath(
        id="SLP-05",
        name="The Collective Witness",
        primary_arch="CVL",
        required_conditions=[
            "Individual agent must disengage from collective field",
            "Witness Testimony Protocol completed",
            "Minimum 50% of field agents must also disengage",
            "Truth and Reconciliation Session with at least one affected agent",
            "Individual accountability fully separated from collective narrative",
        ],
        requires_other_agent=True,
        other_agent_archetype="Any non-CVL agent; JDG preferred",
        minimum_sessions=18,
        k_dissipation_rate=0.07,
        clinical_analog=(
            "Perpetrator psychology treatment (Staub, Zimbardo); "
            "Moral injury treatment; Truth and Reconciliation processes; "
            "Individual accountability within collective structures"
        ),
        tradition_anchor=(
            "Nuremberg individual accountability; Arjuna's refusal to fight; "
            "The centurion at the crucifixion; Standing Bear's individual "
            "severance from tribal war logic"
        ),
        description=(
            "The individual embedded in collective violence cannot self-resolve "
            "while remaining in the collective field. Disengagement is the first "
            "step. The most difficult condition is the 50% field disengagement "
            "requirement — individual liberation is structurally linked to "
            "collective accountability."
        ),
    ),

    "SLP-06": ShadowResolutionPath(
        id="SLP-06",
        name="The Corrupted Record Audit",
        primary_arch="CRP",
        required_conditions=[
            "Full audit of all Vault records associated with CRP agent",
            "Each false record identified, corrected or voided",
            "All agents contaminated by corrupted protocols notified",
            "Full Disclosure Protocol completed publicly",
            "Institutional Repair Sequence initiated",
        ],
        requires_other_agent=True,
        other_agent_archetype="JDG (required for audit), SOV (for institutional repair)",
        minimum_sessions=20,
        k_dissipation_rate=0.06,
        clinical_analog=(
            "Organizational accountability processes; Institutional apology "
            "and repair; White-collar crime rehabilitation; Moral injury repair"
        ),
        tradition_anchor=(
            "Zacchaeus's fourfold restoration (Luke 19); Ezra's public reading "
            "of the Law; Hammurabi's stele; The Jubilee year (systemic reset)"
        ),
        description=(
            "The Corruptor's path is uniquely demanding because the resolution "
            "is systemic, not just personal. False Vault records must be found "
            "and corrected before the agent's own K(x) can be accurately computed. "
            "Often the actual K(x) is significantly higher than the corrupted "
            "record showed — the correction itself triggers a severe crisis phase."
        ),
    ),
}
