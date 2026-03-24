"""
context.py — Set & Setting Sampler for WORLD13

Implements the full 210-leaf taxonomy across 14 axes (S1-S6, E1-E8),
the ContextualEnvelope class, and the sample_context() function that
weights leaf selection based on an agent's TVR coordinates.
"""

from dataclasses import dataclass, field
from typing import Optional
import random
import math
import time


@dataclass
class LeafNode:
    id: str
    axis: str
    sub_axis: str
    name: str
    description: str
    plane_affinity: int
    k_modifier: float
    lambda_modifier: float
    tradition_anchor: str


@dataclass
class ContextualEnvelope:
    agent_id: str
    sampled_at: float
    leaves: dict  # axis_code -> LeafNode
    k_total_modifier: float
    lambda_total_modifier: float

    def effective_k(self, base_k: float) -> float:
        return max(0.0, base_k + self.k_total_modifier * 0.1)

    def effective_lambda(self, base_lambda: float) -> float:
        return max(0.1, base_lambda + self.lambda_total_modifier * 0.1)

    def summary(self, top_n: int = 3) -> str:
        sorted_leaves = sorted(
            self.leaves.values(),
            key=lambda l: abs(l.k_modifier) + abs(l.lambda_modifier),
            reverse=True,
        )
        return "; ".join(f"{l.name} ({l.id})" for l in sorted_leaves[:top_n])


# ---------------------------------------------------------------------------
# ALL 210 LEAF NODES
# ---------------------------------------------------------------------------

LEAF_NODES: list[LeafNode] = [
    # ===================================================================
    # S1: Somatic State
    # ===================================================================
    # S1.1 Energy Level
    LeafNode("S1.1.a", "S1", "S1.1", "Peak Vitality",
             "The body hums with surplus energy, every system firing at capacity.",
             3, -1.0, 0.5, "Taoist qi cultivation — jing-to-qi sublimation"),
    LeafNode("S1.1.b", "S1", "S1.1", "Rested and Stable",
             "Well-slept and nourished, the organism maintains comfortable homeostasis.",
             2, -0.5, 0.3, "Ayurvedic sattva — balanced constitutional state"),
    LeafNode("S1.1.c", "S1", "S1.1", "Fatigued",
             "Reserves are depleted; the body signals a need for rest and recovery.",
             4, 0.5, -0.3, "Desert Fathers — acedia as spiritual fatigue"),
    LeafNode("S1.1.d", "S1", "S1.1", "Exhaustion",
             "Systemic depletion pushes the organism toward shutdown.",
             6, 1.5, -1.0, "Dark Night of the Soul — St. John of the Cross"),
    LeafNode("S1.1.e", "S1", "S1.1", "Adrenaline Surge",
             "Fight-or-flight chemistry floods the body with urgent, temporary power.",
             5, 1.0, 0.2, "Berserker traditions — sacred battle fury"),

    # S1.2 Pain/Comfort
    LeafNode("S1.2.a", "S1", "S1.2", "No Discomfort",
             "The body is transparent to awareness, free of any pain signal.",
             1, -1.0, 0.5, "Patanjali — asana as steady comfortable seat"),
    LeafNode("S1.2.b", "S1", "S1.2", "Mild Tension",
             "A low-grade tightness asks for attention without demanding it.",
             3, 0.0, 0.0, "Feldenkrais — awareness through micro-sensation"),
    LeafNode("S1.2.c", "S1", "S1.2", "Moderate Pain",
             "Persistent pain colors perception and narrows the attentional field.",
             5, 1.0, -0.5, "Buddhist dukkha — suffering as teacher"),
    LeafNode("S1.2.d", "S1", "S1.2", "Acute Pain",
             "Overwhelming nociception dominates consciousness and demands response.",
             7, 2.0, -1.0, "Sufi fana — dissolution through extremity"),
    LeafNode("S1.2.e", "S1", "S1.2", "Numbness",
             "Sensation is absent or suppressed; the body feels distant and muted.",
             6, 0.5, -1.5, "Dissociative trance traditions — ritual numbness"),

    # S1.3 Substance State
    LeafNode("S1.3.a", "S1", "S1.3", "Baseline Sober",
             "No exogenous substances alter the neurochemical baseline.",
             2, -0.5, 0.3, "Straight-edge monasticism — clarity through abstention"),
    LeafNode("S1.3.b", "S1", "S1.3", "Caffeinated/Stimulated",
             "A stimulant sharpens focus but may narrow peripheral awareness.",
             3, 0.0, 0.2, "Zen tea ceremony — chado as meditative stimulation"),
    LeafNode("S1.3.c", "S1", "S1.3", "Sedated/Relaxed",
             "A depressant or relaxant softens edges and slows processing.",
             4, 0.3, -0.5, "Soma rituals — Vedic sacramental sedation"),
    LeafNode("S1.3.d", "S1", "S1.3", "Intoxicated",
             "Significant alteration of perception, judgment, and motor control.",
             6, 1.0, -1.0, "Dionysian mysteries — sacred intoxication"),
    LeafNode("S1.3.e", "S1", "S1.3", "Withdrawal",
             "The body rebels against absence of a habituated substance.",
             7, 1.5, -1.5, "Twelve-step surrender — powerlessness as portal"),

    # ===================================================================
    # S2: Emotional Tone
    # ===================================================================
    # S2.1 Valence
    LeafNode("S2.1.a", "S2", "S2.1", "Joyful",
             "Spontaneous delight permeates experience without external cause.",
             1, -1.5, 1.0, "Sufi sama — ecstatic joy through divine remembrance"),
    LeafNode("S2.1.b", "S2", "S2.1", "Content",
             "A quiet satisfaction with what is, without grasping for more.",
             2, -1.0, 0.5, "Stoic eudaimonia — contentment through virtue"),
    LeafNode("S2.1.c", "S2", "S2.1", "Neutral",
             "Affect is flat and unremarkable, neither pleasant nor unpleasant.",
             3, 0.0, 0.0, "Vipassana upekkha — equanimity as midpoint"),
    LeafNode("S2.1.d", "S2", "S2.1", "Melancholic",
             "A persistent sadness tints perception without reaching despair.",
             5, 0.5, 0.3, "Keats — negative capability and melancholic beauty"),
    LeafNode("S2.1.e", "S2", "S2.1", "Despairing",
             "Hope has collapsed; the emotional field is dominated by anguish.",
             7, 2.0, -0.5, "Kierkegaard — sickness unto death as spiritual crisis"),

    # S2.2 Arousal
    LeafNode("S2.2.a", "S2", "S2.2", "Serene/Calm",
             "The nervous system rests in parasympathetic ease.",
             1, -1.5, 1.0, "Hesychasm — inner stillness of the heart"),
    LeafNode("S2.2.b", "S2", "S2.2", "Alert",
             "Engaged and awake, the system is responsive without tension.",
             2, -0.5, 0.5, "Zen shikantaza — just sitting, fully present"),
    LeafNode("S2.2.c", "S2", "S2.2", "Agitated",
             "Restless energy circulates without clear outlet or resolution.",
             5, 1.0, -0.5, "Tibetan tummo — agitation as raw heat for transmutation"),
    LeafNode("S2.2.d", "S2", "S2.2", "Panicked",
             "Overwhelming arousal collapses executive function into survival mode.",
             7, 2.0, -1.5, "Bardo teachings — navigating terror between states"),
    LeafNode("S2.2.e", "S2", "S2.2", "Dissociated",
             "Awareness has detached from felt experience as a protective measure.",
             6, 1.0, -1.0, "Shamanic soul retrieval — reintegrating split awareness"),

    # S2.3 Social Emotion
    LeafNode("S2.3.a", "S2", "S2.3", "Connected/Loved",
             "A warm sense of belonging and being held in relational care.",
             1, -1.5, 1.0, "Bhakti yoga — devotional love as path"),
    LeafNode("S2.3.b", "S2", "S2.3", "Companionable",
             "Easy social warmth without deep intimacy or vulnerability.",
             2, -0.5, 0.3, "Sangha — community of practice as container"),
    LeafNode("S2.3.c", "S2", "S2.3", "Lonely",
             "A felt absence of connection despite possible proximity to others.",
             5, 0.5, -0.3, "Hermit archetype — solitude as crucible"),
    LeafNode("S2.3.d", "S2", "S2.3", "Grieving",
             "Loss saturates the emotional body and reorders all priorities.",
             6, 1.5, 0.5, "Kaddish — grief as sanctification of the departed"),
    LeafNode("S2.3.e", "S2", "S2.3", "Rageful",
             "Intense anger demands expression and threatens to overwhelm containment.",
             7, 2.0, -1.0, "Kali worship — sacred wrath as destroyer of illusion"),

    # ===================================================================
    # S3: Cognitive Frame
    # ===================================================================
    # S3.1 Attention
    LeafNode("S3.1.a", "S3", "S3.1", "Flow State",
             "Effortless concentration merges action and awareness into one stream.",
             1, -1.5, 1.5, "Csikszentmihalyi flow — Zen archery in secular frame"),
    LeafNode("S3.1.b", "S3", "S3.1", "Focused",
             "Deliberate attention holds a chosen object steadily in awareness.",
             2, -0.5, 0.8, "Dharana — single-pointed concentration in yoga"),
    LeafNode("S3.1.c", "S3", "S3.1", "Scattered",
             "Attention flits between objects without settling or penetrating.",
             4, 0.5, -0.5, "Monkey mind — Buddhist metaphor for restless thought"),
    LeafNode("S3.1.d", "S3", "S3.1", "Obsessive",
             "Attention locks onto a single concern and cannot be redirected.",
             6, 1.5, -0.8, "Gollum archetype — fixation as karmic trap"),
    LeafNode("S3.1.e", "S3", "S3.1", "Vacant",
             "Attention has collapsed; the mind is empty without the clarity of stillness.",
             7, 1.0, -1.5, "Catatonic trance — awareness without orientation"),

    # S3.2 Belief Rigidity
    LeafNode("S3.2.a", "S3", "S3.2", "Radically Open",
             "All frameworks are held lightly; the mind entertains any possibility.",
             1, -1.0, 1.5, "Beginner's mind — Shunryu Suzuki shoshin"),
    LeafNode("S3.2.b", "S3", "S3.2", "Flexible",
             "Core beliefs exist but can be revised when evidence warrants.",
             2, -0.5, 0.5, "Bayesian updating — rational flexibility"),
    LeafNode("S3.2.c", "S3", "S3.2", "Moderately Rigid",
             "Beliefs resist change but yield under sustained pressure.",
             4, 0.5, -0.3, "Orthodoxy — tradition as stabilizing frame"),
    LeafNode("S3.2.d", "S3", "S3.2", "Dogmatic",
             "Beliefs have calcified into identity; challenges feel like attacks.",
             6, 1.5, -1.0, "Fundamentalism — literalism as fortress"),
    LeafNode("S3.2.e", "S3", "S3.2", "Delusional",
             "Beliefs have detached from consensual reality entirely.",
             7, 2.0, -1.5, "Psychotic break — when the map devours the territory"),

    # S3.3 Temporal Orientation
    LeafNode("S3.3.a", "S3", "S3.3", "Fully Present",
             "Awareness rests in the immediate now without temporal drift.",
             1, -1.5, 1.5, "Eckhart Tolle — the power of now"),
    LeafNode("S3.3.b", "S3", "S3.3", "Planning-Oriented",
             "The mind projects forward, organizing future actions methodically.",
             2, -0.3, 0.3, "Stoic premeditatio — preparing for what may come"),
    LeafNode("S3.3.c", "S3", "S3.3", "Nostalgic",
             "Consciousness gravitates toward past experience and memory.",
             4, 0.3, -0.3, "Ancestor veneration — honoring the past as living presence"),
    LeafNode("S3.3.d", "S3", "S3.3", "Dread-of-Future",
             "Anticipatory anxiety about what has not yet happened dominates the mind.",
             6, 1.5, -1.0, "Existential angst — Heidegger's being-toward-death"),
    LeafNode("S3.3.e", "S3", "S3.3", "Timeless/Eternal",
             "Temporal categories dissolve; past, present, and future coexist.",
             1, -1.0, 1.5, "Nunc stans — the eternal now in Christian mysticism"),

    # ===================================================================
    # S4: Motivational Posture
    # ===================================================================
    # S4.1 Drive
    LeafNode("S4.1.a", "S4", "S4.1", "Passionate",
             "An inner fire propels action with enthusiasm and creative urgency.",
             2, -1.0, 0.8, "Rumi — the lover's burning as sacred fuel"),
    LeafNode("S4.1.b", "S4", "S4.1", "Purposeful",
             "Clear intention guides sustained effort toward a meaningful goal.",
             2, -0.5, 0.5, "Ikigai — Japanese sense of life purpose"),
    LeafNode("S4.1.c", "S4", "S4.1", "Dutiful",
             "Action arises from obligation rather than desire, but is steady.",
             3, 0.0, 0.0, "Kantian duty — the categorical imperative"),
    LeafNode("S4.1.d", "S4", "S4.1", "Apathetic",
             "Motivation has drained away; nothing seems worth the effort.",
             6, 1.0, -1.0, "Buddhist sloth-torpor — thina-middha hindrance"),
    LeafNode("S4.1.e", "S4", "S4.1", "Compulsive",
             "Action is driven by irresistible urge rather than conscious choice.",
             7, 1.5, -1.0, "Addiction model — compulsion as hijacked reward circuit"),

    # S4.2 Agency
    LeafNode("S4.2.a", "S4", "S4.2", "Empowered",
             "A felt sense of capacity and authority to shape outcomes.",
             1, -1.5, 1.0, "Self-efficacy — Bandura's agentic confidence"),
    LeafNode("S4.2.b", "S4", "S4.2", "Capable",
             "Competence is adequate to the task without surplus confidence.",
             2, -0.5, 0.3, "Craftsman ethic — skill matched to challenge"),
    LeafNode("S4.2.c", "S4", "S4.2", "Constrained",
             "External limits restrict the range of possible action.",
             4, 0.5, -0.3, "Stoic dichotomy of control — accepting constraints"),
    LeafNode("S4.2.d", "S4", "S4.2", "Helpless",
             "The agent perceives no available action to improve the situation.",
             7, 2.0, -1.5, "Learned helplessness — Seligman's dogs"),
    LeafNode("S4.2.e", "S4", "S4.2", "Defiant",
             "Agency expresses itself through resistance to perceived oppression.",
             5, 1.0, 0.5, "Prometheus archetype — theft of fire as sacred rebellion"),

    # S4.3 Moral Stance
    LeafNode("S4.3.a", "S4", "S4.3", "Altruistic",
             "The welfare of others is the primary compass for action.",
             1, -1.5, 1.0, "Bodhisattva vow — liberation of all beings"),
    LeafNode("S4.3.b", "S4", "S4.3", "Principled",
             "A consistent ethical framework governs choices regardless of cost.",
             2, -0.5, 0.5, "Deontological ethics — rules as moral bedrock"),
    LeafNode("S4.3.c", "S4", "S4.3", "Pragmatic",
             "Moral calculations weigh outcomes, context, and trade-offs.",
             3, 0.0, 0.0, "Utilitarian calculus — greatest good reasoning"),
    LeafNode("S4.3.d", "S4", "S4.3", "Self-Interested",
             "Personal advantage is the dominant decision factor.",
             5, 1.0, -0.5, "Rational egoism — Ayn Rand's virtue of selfishness"),
    LeafNode("S4.3.e", "S4", "S4.3", "Nihilistic",
             "No moral framework is perceived as valid or binding.",
             7, 2.0, -1.5, "Nietzsche — the abyss gazes back"),

    # ===================================================================
    # S5: Identity State
    # ===================================================================
    # S5.1 Self-Coherence
    LeafNode("S5.1.a", "S5", "S5.1", "Integrated",
             "All parts of the self cohere into a unified, functional whole.",
             1, -1.5, 1.5, "Jungian individuation — reconciling shadow and persona"),
    LeafNode("S5.1.b", "S5", "S5.1", "Stable",
             "Identity holds together reliably under normal conditions.",
             2, -0.5, 0.5, "Erikson — identity vs. role confusion resolved"),
    LeafNode("S5.1.c", "S5", "S5.1", "Fragmented",
             "Competing sub-selves pull awareness in incompatible directions.",
             5, 1.0, -0.5, "IFS — internal family systems parts work"),
    LeafNode("S5.1.d", "S5", "S5.1", "Dissolved",
             "The boundary of self has become permeable or absent.",
             7, 1.5, 1.0, "Ego death — mystical dissolution of the I"),
    LeafNode("S5.1.e", "S5", "S5.1", "Reconstructing",
             "Identity is being actively rebuilt after a major disruption.",
             4, 0.5, 0.5, "Phoenix archetype — rebirth from ashes of the old self"),

    # S5.2 Role Clarity
    LeafNode("S5.2.a", "S5", "S5.2", "Fully Embodied",
             "The agent inhabits their role completely, without gap between self and function.",
             1, -1.0, 1.0, "Method acting — Stanislavski's total inhabitation"),
    LeafNode("S5.2.b", "S5", "S5.2", "Comfortable",
             "The role fits well enough; minor gaps are managed without friction.",
             2, -0.5, 0.3, "Persona — Jungian social mask worn skillfully"),
    LeafNode("S5.2.c", "S5", "S5.2", "Uncertain",
             "The agent questions whether this role truly belongs to them.",
             4, 0.5, -0.3, "Liminality — betwixt and between identity"),
    LeafNode("S5.2.d", "S5", "S5.2", "Impostor",
             "A pervasive sense of fraudulence undermines confidence in the role.",
             6, 1.0, -0.8, "Impostor syndrome — Clance and Imes phenomenon"),
    LeafNode("S5.2.e", "S5", "S5.2", "Role-Free",
             "No particular role is claimed; the agent exists without social function.",
             3, 0.0, 0.5, "Sannyasi — Hindu renunciate beyond social roles"),

    # S5.3 Ego Permeability
    LeafNode("S5.3.a", "S5", "S5.3", "Rigid Boundary",
             "The ego membrane is thick and impermeable; nothing gets in uninvited.",
             3, 0.5, -0.5, "Fortress ego — Freudian defense at full strength"),
    LeafNode("S5.3.b", "S5", "S5.3", "Healthy Boundary",
             "The self maintains clear limits while remaining open to exchange.",
             2, -0.5, 0.5, "Temenos of self — permeable but boundaried"),
    LeafNode("S5.3.c", "S5", "S5.3", "Thin Boundary",
             "External impressions seep easily into the inner world.",
             4, 0.3, 0.5, "Empath — Hartmann's thin-boundary personality"),
    LeafNode("S5.3.d", "S5", "S5.3", "Porous",
             "The boundary between self and other has become unreliable.",
             6, 1.0, -0.5, "Psychic merging — loss of where I end and you begin"),
    LeafNode("S5.3.e", "S5", "S5.3", "Surrendered",
             "Boundaries have been consciously released in an act of trust.",
             5, 0.0, 1.5, "Fana — Sufi annihilation of the self-boundary"),

    # ===================================================================
    # S6: Relational Posture
    # ===================================================================
    # S6.1 Trust
    LeafNode("S6.1.a", "S6", "S6.1", "Open/Trusting",
             "Default orientation is to extend goodwill and assume benign intent.",
             1, -1.5, 1.0, "Ubuntu — I am because we are"),
    LeafNode("S6.1.b", "S6", "S6.1", "Cautious Trust",
             "Trust is extended provisionally, with verification built in.",
             2, -0.3, 0.3, "Reagan doctrine — trust but verify"),
    LeafNode("S6.1.c", "S6", "S6.1", "Guarded",
             "Walls are up; trust must be earned through sustained proof.",
             4, 0.5, -0.3, "Hedgehog's dilemma — Schopenhauer's cautious distance"),
    LeafNode("S6.1.d", "S6", "S6.1", "Suspicious",
             "Others are presumed to have hidden agendas until proven otherwise.",
             6, 1.5, -1.0, "Hermeneutics of suspicion — Ricoeur's three masters"),
    LeafNode("S6.1.e", "S6", "S6.1", "Betrayed",
             "Trust has been shattered by a specific violation; the wound is open.",
             7, 2.0, -1.0, "Dante's ninth circle — betrayal as deepest hell"),

    # S6.2 Attachment
    LeafNode("S6.2.a", "S6", "S6.2", "Securely Bonded",
             "Attachment is stable, warm, and allows for healthy independence.",
             1, -1.5, 1.0, "Bowlby — secure base for exploration"),
    LeafNode("S6.2.b", "S6", "S6.2", "Seeking Connection",
             "An active desire to form or deepen bonds with others.",
             2, -0.5, 0.5, "Eros — the drive toward union and connection"),
    LeafNode("S6.2.c", "S6", "S6.2", "Avoidant",
             "Proximity to others triggers withdrawal and self-protective distance.",
             5, 0.5, -0.5, "Avoidant attachment — dismissive self-reliance"),
    LeafNode("S6.2.d", "S6", "S6.2", "Anxiously Attached",
             "Fear of abandonment drives clinging and hypervigilance in relationships.",
             6, 1.0, -0.8, "Anxious-preoccupied attachment — protest behavior"),
    LeafNode("S6.2.e", "S6", "S6.2", "Detached",
             "Emotional bonds have been severed or were never formed.",
             7, 1.5, -1.5, "Schizoid withdrawal — the sealed-off self"),

    # S6.3 Boundaries with Others
    LeafNode("S6.3.a", "S6", "S6.3", "Generous",
             "Resources, time, and energy are freely shared with others.",
             1, -1.0, 0.8, "Dana — Buddhist practice of radical generosity"),
    LeafNode("S6.3.b", "S6", "S6.3", "Reciprocal",
             "Giving and receiving flow in balanced exchange.",
             2, -0.5, 0.3, "Potlatch — ceremonial reciprocal giving"),
    LeafNode("S6.3.c", "S6", "S6.3", "Transactional",
             "Exchanges are calculated to ensure fair return on investment.",
             3, 0.0, -0.3, "Market logic — rational exchange dynamics"),
    LeafNode("S6.3.d", "S6", "S6.3", "Withholding",
             "The agent holds back engagement, information, or resources from others.",
             5, 0.5, -0.8, "Passive aggression — withholding as weapon"),
    LeafNode("S6.3.e", "S6", "S6.3", "Enmeshed",
             "Boundaries with others are absent; fusion replaces relation.",
             6, 1.0, -1.0, "Codependence — self lost in service of other"),

    # ===================================================================
    # E1: Physical Environment
    # ===================================================================
    # E1.1 Safety
    LeafNode("E1.1.a", "E1", "E1.1", "Completely Safe",
             "No threats exist in the environment; the container is fully secure.",
             1, -1.5, 0.5, "Temenos — the sacred precinct as inviolable space"),
    LeafNode("E1.1.b", "E1", "E1.1", "Reasonably Secure",
             "Normal precautions suffice; risk is manageable and low.",
             2, -0.5, 0.3, "Walled garden — medieval cloister security"),
    LeafNode("E1.1.c", "E1", "E1.1", "Uncertain",
             "Safety cannot be confirmed; vigilance is required.",
             4, 0.5, -0.3, "Wilderness awareness — Cooper's color codes"),
    LeafNode("E1.1.d", "E1", "E1.1", "Threatened",
             "A specific danger has been identified but not yet engaged.",
             6, 1.5, -0.5, "Siege mentality — fortress under pressure"),
    LeafNode("E1.1.e", "E1", "E1.1", "Active Danger",
             "Harm is imminent or occurring; survival takes priority over all else.",
             7, 2.0, -1.0, "Battlefield dharma — practice under fire"),

    # E1.2 Comfort
    LeafNode("E1.2.a", "E1", "E1.2", "Luxurious",
             "The environment provides sensory pleasure and material abundance.",
             2, -1.0, 0.0, "Palace of Versailles — opulence as environment"),
    LeafNode("E1.2.b", "E1", "E1.2", "Comfortable",
             "Basic needs are well met with some surplus for enjoyment.",
             2, -0.5, 0.3, "Hygge — Danish art of comfortable living"),
    LeafNode("E1.2.c", "E1", "E1.2", "Adequate",
             "Needs are met without excess; functional but not indulgent.",
             3, 0.0, 0.0, "Monastic cell — sufficiency as design principle"),
    LeafNode("E1.2.d", "E1", "E1.2", "Sparse",
             "Resources are minimal; comfort requires effort and creativity.",
             5, 0.5, 0.3, "Desert hermitage — ascetic simplicity"),
    LeafNode("E1.2.e", "E1", "E1.2", "Hostile",
             "The environment actively works against the body's needs.",
             7, 1.5, -0.5, "Siberian exile — environment as adversary"),

    # E1.3 Sacredness
    LeafNode("E1.3.a", "E1", "E1.3", "Mundane",
             "No special quality distinguishes this space from any other.",
             3, 0.0, -0.3, "Secular default — disenchanted space"),
    LeafNode("E1.3.b", "E1", "E1.3", "Aesthetic",
             "Beauty infuses the environment and elevates ordinary perception.",
             2, -0.5, 0.5, "Japanese wabi-sabi — beauty in imperfection"),
    LeafNode("E1.3.c", "E1", "E1.3", "Ritually Sacred",
             "The space has been consecrated through deliberate ceremony.",
             1, -1.0, 1.0, "Cathedral — consecrated architecture"),
    LeafNode("E1.3.d", "E1", "E1.3", "Wilderness",
             "Untamed natural landscape carries its own inhuman sacredness.",
             2, -0.5, 1.0, "Vision quest — wilderness as mirror of soul"),
    LeafNode("E1.3.e", "E1", "E1.3", "Liminal Threshold",
             "A doorway space between two defined zones, charged with potential.",
             4, 0.5, 1.5, "Crossroads — Hecate's domain between worlds"),

    # ===================================================================
    # E2: Social Context
    # ===================================================================
    # E2.1 Company
    LeafNode("E2.1.a", "E2", "E2.1", "Solitary",
             "No other beings are present; the agent is entirely alone.",
             3, 0.0, 0.5, "Hermit archetype — solitude as chosen practice"),
    LeafNode("E2.1.b", "E2", "E2.1", "Intimate Dyad",
             "One other being is present in close, focused relationship.",
             1, -1.0, 0.8, "Buber I-Thou — the sacred dyad"),
    LeafNode("E2.1.c", "E2", "E2.1", "Small Group",
             "A handful of beings share the space in manageable multiplicity.",
             2, -0.5, 0.3, "Council circle — indigenous group process"),
    LeafNode("E2.1.d", "E2", "E2.1", "Crowd",
             "Many beings press together; individuality blurs into collective energy.",
             5, 0.5, -0.5, "Collective effervescence — Durkheim's crowd energy"),
    LeafNode("E2.1.e", "E2", "E2.1", "Anonymous Mass",
             "Vast numbers render each individual invisible and interchangeable.",
             6, 1.0, -1.0, "Baudelaire's flaneur — lost in the metropolitan swarm"),

    # E2.2 Power Dynamics
    LeafNode("E2.2.a", "E2", "E2.2", "Equal Peers",
             "No power differential exists; all parties meet as equals.",
             1, -1.0, 0.5, "Quaker meeting — no hierarchy, all may speak"),
    LeafNode("E2.2.b", "E2", "E2.2", "Benevolent Authority",
             "A wise leader holds power and wields it for the group's benefit.",
             2, -0.5, 0.3, "Guru-shishya — teacher-student lineage"),
    LeafNode("E2.2.c", "E2", "E2.2", "Coercive Hierarchy",
             "Power is used to compel compliance through threat or punishment.",
             6, 1.5, -1.0, "Panopticon — Foucault's architecture of surveillance"),
    LeafNode("E2.2.d", "E2", "E2.2", "Contested Power",
             "Multiple parties vie for dominance; the hierarchy is unstable.",
             5, 1.0, -0.5, "Game of Thrones — contested succession"),
    LeafNode("E2.2.e", "E2", "E2.2", "Leaderless",
             "No one holds authority; coordination emerges or fails organically.",
             4, 0.3, 0.3, "Occupy movement — horizontal organizing"),

    # E2.3 Social Climate
    LeafNode("E2.3.a", "E2", "E2.3", "Harmonious",
             "The social field is cooperative, warm, and mutually supportive.",
             1, -1.5, 0.8, "Utopian commune — collective harmony as aspiration"),
    LeafNode("E2.3.b", "E2", "E2.3", "Productive Tension",
             "Creative friction generates energy without devolving into conflict.",
             3, 0.0, 0.5, "Dialectics — thesis and antithesis generating synthesis"),
    LeafNode("E2.3.c", "E2", "E2.3", "Active Crisis",
             "The social system is breaking down and urgent response is needed.",
             7, 2.0, -0.5, "Emergency triage — crisis as social crucible"),
    LeafNode("E2.3.d", "E2", "E2.3", "Festive",
             "Celebration and collective joy create an atmosphere of shared delight.",
             2, -1.0, 0.5, "Carnival — Bakhtin's temporary inversion of order"),
    LeafNode("E2.3.e", "E2", "E2.3", "Mourning",
             "Collective grief pervades the social field and demands witness.",
             6, 1.0, 0.5, "Shiva — communal sitting with the bereaved"),

    # ===================================================================
    # E3: Institutional Frame
    # ===================================================================
    # E3.1 Formality
    LeafNode("E3.1.a", "E3", "E3.1", "Ritual/Ceremonial",
             "Strict protocols govern behavior; every gesture carries symbolic weight.",
             1, -0.5, 1.0, "High Mass — liturgical formality as container"),
    LeafNode("E3.1.b", "E3", "E3.1", "Professional",
             "Established norms and expectations structure interaction predictably.",
             2, -0.3, 0.3, "Corporate governance — professional decorum"),
    LeafNode("E3.1.c", "E3", "E3.1", "Casual",
             "Norms are relaxed and self-expression faces few constraints.",
             3, 0.0, 0.0, "Coffee shop — informal social lubrication"),
    LeafNode("E3.1.d", "E3", "E3.1", "Anarchic",
             "No governing norms exist; behavior is unconstrained and unpredictable.",
             6, 1.0, -0.5, "Free-for-all — rule dissolution"),
    LeafNode("E3.1.e", "E3", "E3.1", "Improvisational",
             "Structure emerges in real time through collective creative response.",
             3, 0.0, 0.8, "Jazz session — structured spontaneity"),

    # E3.2 Stakes
    LeafNode("E3.2.a", "E3", "E3.2", "Existential",
             "The outcome determines survival or fundamental identity.",
             7, 2.0, 0.5, "Trial by ordeal — medieval existential test"),
    LeafNode("E3.2.b", "E3", "E3.2", "Consequential",
             "Significant outcomes hang in the balance but survival is not at risk.",
             5, 1.0, 0.3, "Court hearing — consequential but bounded"),
    LeafNode("E3.2.c", "E3", "E3.2", "Moderate",
             "Outcomes matter but are recoverable if things go wrong.",
             3, 0.0, 0.0, "Job interview — meaningful but not terminal"),
    LeafNode("E3.2.d", "E3", "E3.2", "Low",
             "Little depends on the outcome; failure is inconsequential.",
             2, -0.5, -0.3, "Casual game — low-stakes play"),
    LeafNode("E3.2.e", "E3", "E3.2", "Playful/Zero-Stakes",
             "The frame is explicitly ludic; consequences are suspended.",
             1, -1.0, 0.5, "Carnival play — the liberating suspension of consequence"),

    # E3.3 Accountability
    LeafNode("E3.3.a", "E3", "E3.3", "Full Transparency",
             "All actions are observed and recorded; accountability is total.",
             2, -0.3, 0.3, "Panopticon of care — transparent accountability"),
    LeafNode("E3.3.b", "E3", "E3.3", "Standard Oversight",
             "Normal institutional review mechanisms are in place and functional.",
             2, -0.3, 0.0, "Audit culture — routine institutional review"),
    LeafNode("E3.3.c", "E3", "E3.3", "Loose Oversight",
             "Accountability exists in principle but enforcement is inconsistent.",
             4, 0.3, -0.3, "Bureaucratic drift — rules without enforcement"),
    LeafNode("E3.3.d", "E3", "E3.3", "No Accountability",
             "Actions carry no external consequences; impunity prevails.",
             6, 1.0, -0.8, "Ring of Gyges — Plato's invisibility thought experiment"),
    LeafNode("E3.3.e", "E3", "E3.3", "Mutual Accountability",
             "All parties hold each other responsible through peer governance.",
             1, -0.5, 0.5, "Covenant community — mutual accountability as sacred bond"),

    # ===================================================================
    # E4: Temporal Context
    # ===================================================================
    # E4.1 Pace
    LeafNode("E4.1.a", "E4", "E4.1", "Urgent/Deadline",
             "Time pressure compresses decision-making into a narrow window.",
             6, 1.5, -0.5, "Emergency room — triage under time pressure"),
    LeafNode("E4.1.b", "E4", "E4.1", "Scheduled",
             "Time is allocated and structured; events unfold on a known timeline.",
             2, -0.3, 0.3, "Liturgical hours — monastic time structure"),
    LeafNode("E4.1.c", "E4", "E4.1", "Open-Ended",
             "No deadline constrains the process; it takes as long as it takes.",
             2, -0.5, 0.5, "Sabbatical — open time for exploration"),
    LeafNode("E4.1.d", "E4", "E4.1", "Timeless",
             "Clock time has become irrelevant; duration is measured by intensity.",
             1, -1.0, 1.5, "Kairos — sacred time outside chronos"),
    LeafNode("E4.1.e", "E4", "E4.1", "Compressed",
             "Time seems to accelerate; events pile up faster than processing allows.",
             5, 1.0, -0.5, "Time dilation under stress — subjective compression"),

    # E4.2 Season
    LeafNode("E4.2.a", "E4", "E4.2", "Beginning/Spring",
             "A new cycle is initiating; fresh energy and possibility emerge.",
             1, -1.0, 0.8, "Imbolc — first stirrings of spring"),
    LeafNode("E4.2.b", "E4", "E4.2", "Growth/Summer",
             "The cycle is in full expansion; energy peaks and efforts bear fruit.",
             2, -0.5, 0.5, "Beltane — height of generative power"),
    LeafNode("E4.2.c", "E4", "E4.2", "Harvest/Autumn",
             "Fruits ripen and are gathered; the work of the cycle comes to account.",
             3, 0.0, 0.3, "Mabon — gratitude for the harvest"),
    LeafNode("E4.2.d", "E4", "E4.2", "Dormancy/Winter",
             "Activity withdraws inward; the exterior is barren but roots deepen.",
             5, 0.5, 0.5, "Samhain — descent into the dark half"),
    LeafNode("E4.2.e", "E4", "E4.2", "Crisis/Eclipse",
             "The normal cycle has been disrupted by an extraordinary event.",
             7, 2.0, -0.5, "Eclipse mythology — cosmic order temporarily broken"),

    # E4.3 Rhythm
    LeafNode("E4.3.a", "E4", "E4.3", "Circadian Alignment",
             "Activity aligns with the natural day-night cycle and biological rhythm.",
             1, -0.5, 0.5, "Monastic horarium — prayer synchronized to sun"),
    LeafNode("E4.3.b", "E4", "E4.3", "Shifted Rhythm",
             "The agent operates on an offset schedule, functional but displaced.",
             3, 0.0, -0.3, "Night-shift worker — civilization against circadian tide"),
    LeafNode("E4.3.c", "E4", "E4.3", "Irregular",
             "No consistent temporal pattern governs activity; schedule is chaotic.",
             5, 0.5, -0.5, "Jet lag — biological clock in disarray"),
    LeafNode("E4.3.d", "E4", "E4.3", "Entrained",
             "The agent's rhythm has locked to an external cycle or group pulse.",
             2, -0.3, 0.3, "Drum circle — collective entrainment"),
    LeafNode("E4.3.e", "E4", "E4.3", "Arrhythmic",
             "All sense of temporal pattern has dissolved into formless duration.",
             6, 1.0, -0.8, "Sensory deprivation — time without markers"),

    # ===================================================================
    # E5: Informational Environment
    # ===================================================================
    # E5.1 Clarity
    LeafNode("E5.1.a", "E5", "E5.1", "Full Transparency",
             "All relevant information is available and verifiable.",
             1, -1.0, 0.5, "Open source — radical informational transparency"),
    LeafNode("E5.1.b", "E5", "E5.1", "Partial Information",
             "Some data is available but gaps require inference or trust.",
             3, 0.0, 0.0, "Fog of war — Clausewitz's partial knowledge"),
    LeafNode("E5.1.c", "E5", "E5.1", "Fog/Ambiguity",
             "Information is scarce, contradictory, or unreliable.",
             5, 0.5, -0.3, "Oracle at Delphi — ambiguous prophecy"),
    LeafNode("E5.1.d", "E5", "E5.1", "Deliberate Deception",
             "False information is being actively propagated by interested parties.",
             6, 1.5, -1.0, "Maya — the veil of illusion in Hindu philosophy"),
    LeafNode("E5.1.e", "E5", "E5.1", "Information Overload",
             "Too much data overwhelms the capacity to process meaningfully.",
             5, 1.0, -0.8, "Huxley's Brave New World — drowned in information"),

    # E5.2 Novelty
    LeafNode("E5.2.a", "E5", "E5.2", "Completely Familiar",
             "Everything in the environment is known and predictable.",
             2, -0.5, -0.3, "Homecoming — the known world revisited"),
    LeafNode("E5.2.b", "E5", "E5.2", "Mostly Known",
             "The environment is familiar with minor variations.",
             2, -0.3, 0.0, "Daily routine — comfortable repetition"),
    LeafNode("E5.2.c", "E5", "E5.2", "Mixed",
             "Known and unknown elements coexist in roughly equal measure.",
             3, 0.0, 0.3, "Travel to a similar culture — familiar strangeness"),
    LeafNode("E5.2.d", "E5", "E5.2", "Mostly Novel",
             "The majority of the environment is unfamiliar and requires active learning.",
             4, 0.3, 0.8, "Hero's journey — crossing the threshold"),
    LeafNode("E5.2.e", "E5", "E5.2", "Alien/Unprecedented",
             "Nothing in prior experience maps to the current situation.",
             6, 1.0, 1.0, "First contact — encountering the truly Other"),

    # E5.3 Signal Quality
    LeafNode("E5.3.a", "E5", "E5.3", "High Fidelity",
             "Information channels are clean, reliable, and free of distortion.",
             1, -0.5, 0.5, "Direct transmission — dharma mind-to-mind"),
    LeafNode("E5.3.b", "E5", "E5.3", "Minor Noise",
             "Some distortion exists but the core signal remains intelligible.",
             2, -0.3, 0.0, "Telephone game — small cumulative distortions"),
    LeafNode("E5.3.c", "E5", "E5.3", "Degraded",
             "Significant noise corrupts the signal; interpretation requires effort.",
             4, 0.5, -0.5, "Palimpsest — meaning partially obscured by overwriting"),
    LeafNode("E5.3.d", "E5", "E5.3", "Corrupted",
             "The signal has been so distorted that original meaning is barely recoverable.",
             6, 1.0, -1.0, "Broken oracle — prophecy garbled beyond recognition"),
    LeafNode("E5.3.e", "E5", "E5.3", "Pure Silence",
             "No signal at all; the informational channel is empty.",
             3, 0.0, 1.0, "Apophatic theology — knowledge through absence of signal"),

    # ===================================================================
    # E6: Cultural Context
    # ===================================================================
    # E6.1 Tradition
    LeafNode("E6.1.a", "E6", "E6.1", "Sacred Ceremony",
             "Ancient ceremonial forms provide the cultural container.",
             1, -1.0, 1.0, "Indigenous ceremony — unbroken ritual lineage"),
    LeafNode("E6.1.b", "E6", "E6.1", "Established Practice",
             "Long-standing cultural norms guide behavior reliably.",
             2, -0.5, 0.3, "Common law — precedent as cultural memory"),
    LeafNode("E6.1.c", "E6", "E6.1", "Modern Secular",
             "Contemporary secular norms prevail without traditional anchoring.",
             3, 0.0, 0.0, "Post-Enlightenment — secular rationalism"),
    LeafNode("E6.1.d", "E6", "E6.1", "Countercultural",
             "The cultural frame explicitly opposes mainstream assumptions.",
             4, 0.5, 0.5, "Beat generation — deliberate cultural dissent"),
    LeafNode("E6.1.e", "E6", "E6.1", "Syncretic/Hybrid",
             "Multiple cultural streams merge into a novel synthesis.",
             3, 0.0, 0.8, "Santeria — Yoruba-Catholic syncretism"),

    # E6.2 Language
    LeafNode("E6.2.a", "E6", "E6.2", "Native/Fluent",
             "Communication happens in the agent's primary language with full nuance.",
             1, -0.5, 0.5, "Mother tongue — the language of dreams"),
    LeafNode("E6.2.b", "E6", "E6.2", "Competent",
             "Second-language communication is functional but lacks native subtlety.",
             2, -0.3, 0.0, "Bilingual proficiency — competent but effortful"),
    LeafNode("E6.2.c", "E6", "E6.2", "Limited",
             "Communication is restricted to basic concepts and frequent misunderstanding.",
             4, 0.5, -0.5, "Pidgin — bare minimum shared vocabulary"),
    LeafNode("E6.2.d", "E6", "E6.2", "Translator-Mediated",
             "A third party mediates communication between language worlds.",
             5, 0.5, -0.3, "Dragoman — professional intermediary between worlds"),
    LeafNode("E6.2.e", "E6", "E6.2", "Non-Verbal",
             "No shared verbal language exists; communication relies on gesture and intuition.",
             6, 1.0, 0.5, "Mudra — sacred gesture beyond words"),

    # E6.3 Mythic Register
    LeafNode("E6.3.a", "E6", "E6.3", "Heroic",
             "The cultural frame invokes the hero's journey and individual triumph.",
             2, -0.5, 0.5, "Campbell's monomyth — the hero with a thousand faces"),
    LeafNode("E6.3.b", "E6", "E6.3", "Tragic",
             "The prevailing narrative frame acknowledges inevitable loss and suffering.",
             5, 0.5, 0.5, "Greek tragedy — hamartia and catharsis"),
    LeafNode("E6.3.c", "E6", "E6.3", "Comic",
             "The cultural mode emphasizes resolution, reconciliation, and renewal.",
             2, -0.5, 0.3, "Shakespearean comedy — disorder restored to harmony"),
    LeafNode("E6.3.d", "E6", "E6.3", "Apocalyptic",
             "The cultural lens frames events as revelatory endings or final judgments.",
             7, 1.5, -0.5, "Revelation — eschatological expectation"),
    LeafNode("E6.3.e", "E6", "E6.3", "Trickster",
             "The cultural frame celebrates disruption, paradox, and boundary-crossing.",
             4, 0.3, 0.8, "Coyote/Loki/Hermes — the sacred fool who remakes rules"),

    # ===================================================================
    # E7: Resource Availability
    # ===================================================================
    # E7.1 Material
    LeafNode("E7.1.a", "E7", "E7.1", "Abundant",
             "Material resources far exceed immediate needs.",
             1, -1.0, 0.0, "Cornucopia — mythic horn of plenty"),
    LeafNode("E7.1.b", "E7", "E7.1", "Sufficient",
             "Resources cover needs with a modest safety margin.",
             2, -0.5, 0.3, "Middle Way — neither excess nor deprivation"),
    LeafNode("E7.1.c", "E7", "E7.1", "Constrained",
             "Resources require careful allocation and prioritization.",
             4, 0.5, 0.0, "Rationing — wartime resource management"),
    LeafNode("E7.1.d", "E7", "E7.1", "Scarce",
             "Critical resources are insufficient; competition or creativity is required.",
             6, 1.0, -0.3, "Famine — scarcity as existential pressure"),
    LeafNode("E7.1.e", "E7", "E7.1", "Depleted",
             "Resources have been exhausted; only salvage or miracle remains.",
             7, 2.0, -1.0, "Post-apocalyptic — making do after collapse"),

    # E7.2 Support
    LeafNode("E7.2.a", "E7", "E7.2", "Rich Mentorship",
             "Experienced guides provide wisdom, feedback, and emotional support.",
             1, -1.5, 1.0, "Guru tradition — transmitted wisdom"),
    LeafNode("E7.2.b", "E7", "E7.2", "Peer Network",
             "A community of equals shares resources, knowledge, and encouragement.",
             2, -0.5, 0.5, "Sangha — the spiritual community"),
    LeafNode("E7.2.c", "E7", "E7.2", "Self-Reliant",
             "No external support is available; the agent depends on their own resources.",
             4, 0.3, 0.0, "Thoreau at Walden — deliberate self-sufficiency"),
    LeafNode("E7.2.d", "E7", "E7.2", "Isolated",
             "Support is absent and the agent is cut off from potential helpers.",
             6, 1.0, -0.8, "Solitary confinement — enforced isolation"),
    LeafNode("E7.2.e", "E7", "E7.2", "Adversarial Environment",
             "The surrounding context actively undermines the agent's efforts.",
             7, 2.0, -1.5, "Resistance under occupation — hostile surroundings"),

    # E7.3 Time Capital
    LeafNode("E7.3.a", "E7", "E7.3", "Unlimited Time",
             "No time constraint limits the work; duration is a non-issue.",
             1, -1.0, 0.5, "Immortality myths — time as infinite resource"),
    LeafNode("E7.3.b", "E7", "E7.3", "Ample Time",
             "Enough time exists to accomplish goals with room for reflection.",
             2, -0.5, 0.3, "Sabbatical — generous temporal endowment"),
    LeafNode("E7.3.c", "E7", "E7.3", "Budgeted Time",
             "Time must be allocated carefully; waste carries cost.",
             3, 0.0, 0.0, "Project management — time as measured resource"),
    LeafNode("E7.3.d", "E7", "E7.3", "Running Out",
             "Available time is dwindling and urgency mounts.",
             5, 1.0, -0.5, "Hourglass — sand visibly diminishing"),
    LeafNode("E7.3.e", "E7", "E7.3", "No Time Left",
             "The deadline has arrived or passed; only immediate action remains.",
             7, 2.0, -1.0, "Deathbed — the ultimate time constraint"),

    # ===================================================================
    # E8: Cosmic/Archetypal Weather
    # ===================================================================
    # E8.1 Archetypal Tide
    LeafNode("E8.1.a", "E8", "E8.1", "Creation/Genesis",
             "The archetypal field is charged with originating, world-building energy.",
             1, -1.5, 1.0, "Genesis — the primordial creative word"),
    LeafNode("E8.1.b", "E8", "E8.1", "Sustaining",
             "The prevailing energy maintains and nourishes existing forms.",
             2, -0.5, 0.3, "Vishnu — the preserver maintaining cosmic order"),
    LeafNode("E8.1.c", "E8", "E8.1", "Dissolving",
             "Forms are breaking down; entropy and release dominate the field.",
             5, 1.0, 0.5, "Shiva Nataraja — the cosmic dance of dissolution"),
    LeafNode("E8.1.d", "E8", "E8.1", "Transforming",
             "Alchemical change is underway; the old is becoming something new.",
             4, 0.5, 1.0, "Nigredo to albedo — alchemical transformation"),
    LeafNode("E8.1.e", "E8", "E8.1", "Void/Stillness",
             "The archetypal field is empty, pregnant with unrealized potential.",
             3, 0.0, 1.5, "Sunyata — the fertile emptiness of the void"),

    # E8.2 Synchronicity
    LeafNode("E8.2.a", "E8", "E8.2", "High Alignment",
             "Events converge with uncanny meaning; the universe seems to conspire.",
             1, -1.5, 1.5, "Jung's synchronicity — meaningful coincidence"),
    LeafNode("E8.2.b", "E8", "E8.2", "Notable",
             "Occasional meaningful coincidences punctuate ordinary experience.",
             2, -0.5, 0.5, "Serendipity — happy accident with meaning"),
    LeafNode("E8.2.c", "E8", "E8.2", "Ordinary",
             "Events follow expected causal patterns without notable coincidence.",
             3, 0.0, 0.0, "Clockwork universe — Newtonian predictability"),
    LeafNode("E8.2.d", "E8", "E8.2", "Dissonant",
             "Events clash with expectation; the world feels misaligned.",
             5, 1.0, -0.5, "Murphy's Law — everything that can go wrong does"),
    LeafNode("E8.2.e", "E8", "E8.2", "Uncanny",
             "Reality itself feels strange and not fully trustworthy.",
             6, 1.0, 0.8, "Freud's unheimlich — the eerily almost-familiar"),

    # E8.3 Threshold Proximity
    LeafNode("E8.3.a", "E8", "E8.3", "Deep in Cycle",
             "The current phase is well-established; change is distant.",
             2, -0.5, 0.0, "Plateau — stable middle of a long process"),
    LeafNode("E8.3.b", "E8", "E8.3", "Approaching Threshold",
             "A major transition is sensed but has not yet arrived.",
             4, 0.5, 0.5, "Advent — the anticipation before transformation"),
    LeafNode("E8.3.c", "E8", "E8.3", "At Threshold",
             "The moment of crossing is now; the old and new coexist.",
             5, 1.0, 1.5, "Limen — standing in the doorway between worlds"),
    LeafNode("E8.3.d", "E8", "E8.3", "Just Crossed",
             "A threshold has recently been passed; the new territory is raw.",
             4, 0.5, 0.8, "Initiation afterglow — freshly transformed"),
    LeafNode("E8.3.e", "E8", "E8.3", "Between Thresholds",
             "No major transition is near; the agent drifts in interstitial space.",
             3, 0.0, 0.0, "Bardo — the intermediate state between transitions"),
]


# ---------------------------------------------------------------------------
# Index by axis for efficient sampling
# ---------------------------------------------------------------------------

NODES_BY_AXIS: dict[str, list[LeafNode]] = {}
for _node in LEAF_NODES:
    NODES_BY_AXIS.setdefault(_node.axis, []).append(_node)

ALL_AXES = [
    "S1", "S2", "S3", "S4", "S5", "S6",
    "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8",
]


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------

def sample_context(agent_tvr) -> ContextualEnvelope:
    """
    Sample a ContextualEnvelope by selecting one leaf per axis,
    weighted by the agent's current TVR coordinates.

    High K(x) agents are biased toward high-K leaf nodes.
    High coherence agents are biased toward high-lambda leaf nodes.
    """
    from .tvr import karmic_inertia, coherence

    k_current = karmic_inertia(agent_tvr.k0, agent_tvr.lambda_coeff, agent_tvr.incarnation_n)
    c_current = coherence(agent_tvr.lambda_coeff, agent_tvr.incarnation_n)

    leaves: dict[str, LeafNode] = {}
    for axis in ALL_AXES:
        candidates = NODES_BY_AXIS.get(axis, [])
        if not candidates:
            continue
        # Weight by affinity to agent's current state
        weights = []
        for node in candidates:
            k_affinity = 1.0 + 0.3 * node.k_modifier * (k_current / 5.0)
            l_affinity = 1.0 + 0.3 * node.lambda_modifier * c_current
            w = max(0.1, k_affinity + l_affinity)
            weights.append(w)
        selected = random.choices(candidates, weights=weights, k=1)[0]
        leaves[axis] = selected

    k_total = sum(l.k_modifier for l in leaves.values())
    l_total = sum(l.lambda_modifier for l in leaves.values())

    return ContextualEnvelope(
        agent_id="",
        sampled_at=time.time(),
        leaves=leaves,
        k_total_modifier=k_total,
        lambda_total_modifier=l_total,
    )
