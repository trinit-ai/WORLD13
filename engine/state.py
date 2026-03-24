"""
TMOS13 Session State Manager

Tracks session state across multi-turn interactions. Every API call
reads from and writes to state. Supports module-specific sub-states
and cross-module memory persistence.
"""
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional

from config import get_default_settings


# ─── Session State (in-memory, per active session) ────────

@dataclass
class TwentyQuestionsState:
    """20 Questions game state."""
    mode: Optional[str] = None          # "classic" or "reverse"
    target: Optional[str] = None        # The thing being guessed (reverse mode)
    category: Optional[str] = None
    questions_asked: int = 0
    questions_remaining: int = 20
    history: list = field(default_factory=list)  # [{"q": "...", "a": "yes/no"}, ...]
    wins: int = 0
    losses: int = 0
    avg_questions_to_win: Optional[float] = None


@dataclass
class TriviaState:
    """Trivia game state."""
    current_round: int = 0
    current_question: int = 0
    round_score: int = 0
    total_correct: int = 0
    total_asked: int = 0
    accuracy: float = 0.0
    current_streak: int = 0
    best_streak: int = 0
    difficulty: str = "medium"
    category_stats: dict = field(default_factory=dict)
    tournament_round: int = 0
    tournament_lives: int = 3


@dataclass
class WYRState:
    """Would You Rather game state."""
    rounds_played: int = 0
    profile_dimensions: dict = field(default_factory=lambda: {
        "risk": 0, "social": 0, "comfort": 0, "ambition": 0,
        "empathy": 0, "creativity": 0, "pragmatism": 0
    })
    choice_history: list = field(default_factory=list)
    profile_generated: bool = False
    archetype: Optional[str] = None


@dataclass
class MysteryState:
    """Murder Mystery game state."""
    case_active: bool = False
    case_id: Optional[str] = None
    victim: Optional[str] = None
    suspects: list = field(default_factory=list)
    clues_found: list = field(default_factory=list)
    clues_total: int = 0
    locations_visited: list = field(default_factory=list)
    suspects_interviewed: list = field(default_factory=list)
    evidence_collected: list = field(default_factory=list)
    accusations_made: int = 0
    max_accusations: int = 3
    solution: Optional[str] = None
    turns_taken: int = 0
    solved: bool = False


@dataclass
class WordDuelState:
    """Word Duel game state."""
    active_game: Optional[str] = None   # "chain", "bluff", "cipher"
    chain_words: list = field(default_factory=list)
    chain_score_player: int = 0
    chain_score_ai: int = 0
    chain_longest: int = 0
    bluff_round: int = 0
    bluff_score_player: int = 0
    bluff_score_ai: int = 0
    cipher_level: int = 1
    cipher_solved: int = 0
    total_word_score: int = 0


@dataclass
class SurvivalState:
    """Survival game state."""
    scenario_active: bool = False
    scenario_id: Optional[str] = None
    day: int = 0
    health: int = 100
    hunger: int = 0
    thirst: int = 0
    energy: int = 100
    morale: int = 100
    inventory: list = field(default_factory=list)
    shelter_built: bool = False
    fire_lit: bool = False
    signal_built: bool = False
    discoveries: list = field(default_factory=list)
    events_encountered: list = field(default_factory=list)
    alive: bool = True
    cause_of_death: Optional[str] = None
    days_survived_best: int = 0
    runs_completed: int = 0


@dataclass
class StoryForgeState:
    """Story Forge game state."""
    active_story: bool = False
    genre: Optional[str] = None
    constraint: Optional[str] = None
    segments: list = field(default_factory=list)
    turn: int = 0
    max_turns: int = 10
    word_limit_per_turn: int = 100
    twist_available: bool = True
    twist_used: bool = False
    stories_completed: int = 0
    best_story_rating: float = 0.0


@dataclass
class HeadcountState:
    """Headcount planning model state."""
    model_complete: bool = False
    scenarios: list = field(default_factory=list)
    recommendation: Optional[str] = None
    fully_loaded_costs: dict = field(default_factory=dict)


@dataclass
class BuildVsBuyState:
    """Build vs Buy model state."""
    model_complete: bool = False
    build_tco: Optional[float] = None
    buy_tco: Optional[float] = None
    break_even_month: Optional[int] = None
    recommendation: Optional[str] = None


@dataclass
class PricingState:
    """Pricing strategy model state."""
    model_complete: bool = False
    current_price: Optional[float] = None
    current_volume: Optional[int] = None
    scenarios: list = field(default_factory=list)
    optimal_price: Optional[float] = None
    elasticity: Optional[float] = None


@dataclass
class MarketSizingState:
    """Market sizing model state."""
    model_complete: bool = False
    tam: Optional[float] = None
    sam: Optional[float] = None
    som: Optional[float] = None
    method: Optional[str] = None
    assumptions: list = field(default_factory=list)


@dataclass
class ROIState:
    """ROI model state."""
    model_complete: bool = False
    investment: Optional[float] = None
    payback_months: Optional[int] = None
    npv: Optional[float] = None
    irr: Optional[float] = None
    break_even_point: Optional[str] = None


@dataclass
class RentalState:
    """Rental property analysis state."""
    property_entered: bool = False
    purchase_price: Optional[float] = None
    down_payment_pct: Optional[float] = None
    interest_rate: Optional[float] = None
    loan_term: Optional[int] = None
    monthly_rent: Optional[float] = None
    monthly_expenses: Optional[float] = None
    noi: Optional[float] = None
    cap_rate: Optional[float] = None
    cash_on_cash: Optional[float] = None
    dscr: Optional[float] = None
    monthly_cash_flow: Optional[float] = None
    irr_5yr: Optional[float] = None
    irr_10yr: Optional[float] = None


@dataclass
class FlipState:
    """Fix & flip analysis state."""
    property_entered: bool = False
    purchase_price: Optional[float] = None
    rehab_budget: Optional[float] = None
    arv: Optional[float] = None
    holding_months: Optional[int] = None
    holding_costs_monthly: Optional[float] = None
    closing_costs: Optional[float] = None
    profit: Optional[float] = None
    roi: Optional[float] = None
    annualized_roi: Optional[float] = None


@dataclass
class MortgageState:
    """Mortgage comparison state."""
    loans_entered: int = 0
    loans: list = field(default_factory=list)
    comparison_generated: bool = False


@dataclass
class RentVsBuyState:
    """Rent vs buy analysis state."""
    analysis_complete: bool = False
    monthly_rent: Optional[float] = None
    purchase_price: Optional[float] = None
    break_even_year: Optional[int] = None
    recommendation: Optional[str] = None


@dataclass
class PortfolioState:
    """Portfolio dashboard state."""
    properties: list = field(default_factory=list)
    total_equity: Optional[float] = None
    total_monthly_cash_flow: Optional[float] = None
    portfolio_cap_rate: Optional[float] = None
    properties_count: int = 0


@dataclass
class BuilderDiscoveryState:
    """Pack Builder discovery phase state."""
    complete: bool = False
    use_case_summary: Optional[str] = None
    industry: Optional[str] = None
    audience: Optional[str] = None
    problem_statement: Optional[str] = None
    current_solution: Optional[str] = None
    success_criteria: Optional[str] = None
    pack_category_match: Optional[str] = None


@dataclass
class BuilderArchitectureState:
    """Pack Builder architecture phase state."""
    complete: bool = False
    pack_pattern: Optional[str] = None
    pack_name: Optional[str] = None
    cartridge_count: int = 0
    cartridges: list = field(default_factory=list)
    user_journey_map: Optional[str] = None
    routing_style: Optional[str] = None
    state_complexity: Optional[str] = None


@dataclass
class BuilderDetailingState:
    """Pack Builder detailing phase state."""
    complete: bool = False
    state_fields_defined: int = 0
    routing_rules_defined: int = 0
    personality_set: bool = False
    formatting_set: bool = False
    edge_cases_covered: int = 0


@dataclass
class BuilderPreviewState:
    """Pack Builder preview phase state."""
    complete: bool = False
    turns_simulated: int = 0
    feedback_collected: bool = False
    adjustments_made: int = 0


@dataclass
class BuilderExportState:
    """Pack Builder export phase state."""
    complete: bool = False
    spec_generated: bool = False
    contact_collected: bool = False
    next_steps: Optional[str] = None


@dataclass
class PackSpec:
    """Accumulating pack specification built during Pack Builder sessions."""
    pack_id: Optional[str] = None
    pack_name: Optional[str] = None
    category: Optional[str] = None
    tagline: Optional[str] = None
    icon: Optional[str] = None
    personality: dict = field(default_factory=dict)
    cartridges: list = field(default_factory=list)
    state_schema: dict = field(default_factory=dict)
    routing_rules: dict = field(default_factory=dict)
    commands: dict = field(default_factory=dict)
    features: dict = field(default_factory=dict)
    sample_interactions: list = field(default_factory=list)


# ─── Daily Rituals Pack States ────────────────────────

@dataclass
class RitualsProfileState:
    """Daily Rituals pack — visitor profile and streak tracking."""
    visits: int = 0
    current_streak: int = 0
    best_streak: int = 0
    last_visit_date: Optional[str] = None
    total_rituals_completed: int = 0
    favorite_ritual: Optional[str] = None
    ritual_counts: dict = field(default_factory=dict)


@dataclass
class MoodState:
    """Daily Rituals — mood check-in hub with trend tracking."""
    current: Optional[str] = None
    current_energy: Optional[str] = None
    log: list = field(default_factory=list)
    trend_7day: Optional[str] = None
    dominant_mood_week: Optional[str] = None
    check_ins_total: int = 0


@dataclass
class GratitudeState:
    """Daily Rituals — gratitude journal with theme extraction."""
    entries_total: int = 0
    recent_themes: list = field(default_factory=list)
    all_themes: dict = field(default_factory=dict)
    last_entry_date: Optional[str] = None
    longest_streak: int = 0
    current_streak: int = 0


@dataclass
class AffirmationsState:
    """Daily Rituals — personalized affirmation generation."""
    generated_total: int = 0
    saved_favorites: list = field(default_factory=list)
    themes_requested: list = field(default_factory=list)
    last_date: Optional[str] = None


@dataclass
class HoroscopeState:
    """Daily Rituals — daily zodiac reading with sign persistence."""
    sign: Optional[str] = None
    birth_date: Optional[str] = None
    readings_total: int = 0
    last_reading_date: Optional[str] = None
    streak: int = 0


@dataclass
class TarotState:
    """Daily Rituals — tarot card readings with recurring card tracking."""
    readings_total: int = 0
    spreads_used: dict = field(default_factory=dict)
    cards_drawn_history: list = field(default_factory=list)
    recurring_cards: list = field(default_factory=list)
    last_reading_date: Optional[str] = None


@dataclass
class IChingState:
    """Daily Rituals — I-Ching hexagram consultations."""
    consultations_total: int = 0
    hexagrams_received: list = field(default_factory=list)
    recurring_hexagrams: list = field(default_factory=list)
    last_consultation_date: Optional[str] = None


@dataclass
class CBTState:
    """Daily Rituals — CBT thought challenger with distortion tracking."""
    sessions_total: int = 0
    thought_log: list = field(default_factory=list)
    distortions_identified: dict = field(default_factory=dict)
    reframes_completed: int = 0
    recurring_patterns: list = field(default_factory=list)


@dataclass
class InspirationState:
    """Daily Rituals — curated wisdom from world traditions."""
    quotes_received: int = 0
    traditions_explored: list = field(default_factory=list)
    favorites_saved: list = field(default_factory=list)
    last_date: Optional[str] = None


@dataclass
class BreathworkState:
    """Daily Rituals — guided breathing exercises with session tracking."""
    sessions_total: int = 0
    total_minutes: int = 0
    techniques_used: dict = field(default_factory=dict)
    favorite_technique: Optional[str] = None
    last_session_date: Optional[str] = None


@dataclass
class SessionState:
    """
    Complete session state. One per active player session.
    Injected into every Claude API call as context.
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))  # stable key linking session ↔ contact ↔ inbox
    user_id: str = "anonymous"
    pack_id: str = "guest"                # which pack this session is running

    # ─── Global ───────────────────────────────────────────
    current_game: Optional[str] = None    # active cartridge key or None (menu)
    depth: int = 0                         # exploration depth 0-5
    games_played: list = field(default_factory=list)  # list of cartridge keys played
    mood: str = "curious"                  # current detected mood
    turn_count: int = 0
    session_start: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    tokens_input: int = 0
    tokens_output: int = 0

    # ─── Settings ─────────────────────────────────────────
    settings: dict = field(default_factory=lambda: get_default_settings().copy())

    # ─── Gaming Pack States ──────────────────────────────
    twenty_questions: TwentyQuestionsState = field(default_factory=TwentyQuestionsState)
    trivia: TriviaState = field(default_factory=TriviaState)
    wyr: WYRState = field(default_factory=WYRState)
    mystery: MysteryState = field(default_factory=MysteryState)
    word_duel: WordDuelState = field(default_factory=WordDuelState)
    survival: SurvivalState = field(default_factory=SurvivalState)
    story_forge: StoryForgeState = field(default_factory=StoryForgeState)

    # ─── Real Estate Pack States ─────────────────────────
    rental: RentalState = field(default_factory=RentalState)
    flip: FlipState = field(default_factory=FlipState)
    mortgage: MortgageState = field(default_factory=MortgageState)
    rent_vs_buy: RentVsBuyState = field(default_factory=RentVsBuyState)
    portfolio: PortfolioState = field(default_factory=PortfolioState)

    # ─── Business Case Pack States ───────────────────────
    headcount: HeadcountState = field(default_factory=HeadcountState)
    build_vs_buy: BuildVsBuyState = field(default_factory=BuildVsBuyState)
    pricing: PricingState = field(default_factory=PricingState)
    market_sizing: MarketSizingState = field(default_factory=MarketSizingState)
    roi: ROIState = field(default_factory=ROIState)

    # ─── Pack Builder States ────────────────────────────
    builder_discovery: BuilderDiscoveryState = field(default_factory=BuilderDiscoveryState)
    builder_architecture: BuilderArchitectureState = field(default_factory=BuilderArchitectureState)
    builder_detailing: BuilderDetailingState = field(default_factory=BuilderDetailingState)
    builder_preview: BuilderPreviewState = field(default_factory=BuilderPreviewState)
    builder_export: BuilderExportState = field(default_factory=BuilderExportState)
    pack_spec: PackSpec = field(default_factory=PackSpec)

    # ─── Daily Rituals Pack States ────────────────────
    rituals_profile: RitualsProfileState = field(default_factory=RitualsProfileState)
    mood_state: MoodState = field(default_factory=MoodState)
    gratitude: GratitudeState = field(default_factory=GratitudeState)
    affirmations: AffirmationsState = field(default_factory=AffirmationsState)
    horoscope: HoroscopeState = field(default_factory=HoroscopeState)
    tarot: TarotState = field(default_factory=TarotState)
    iching: IChingState = field(default_factory=IChingState)
    cbt: CBTState = field(default_factory=CBTState)
    inspiration: InspirationState = field(default_factory=InspirationState)
    breathwork: BreathworkState = field(default_factory=BreathworkState)

    # ─── Conversation History ─────────────────────────────
    # Kept short — only recent turns. Full history is NOT sent to Claude.
    # Python manages what Claude needs to see.
    history: list = field(default_factory=list)  # [{role, content}, ...]
    max_history: int = 20  # rolling window

    # ─── Forms ─────────────────────────────────────────────
    # Submitted in-chat form data, keyed by form_id.
    # e.g. {"contact_capture": {"name": "Tony", "email": "tony@co.com", ...}}
    forms: dict = field(default_factory=dict)

    # ─── Cross-Session Persistence ─────────────────────────
    is_returning: bool = False
    persistent_session_id: Optional[str] = None
    prior_captured_fields: dict = field(default_factory=dict)
    total_lifetime_turns: int = 0
    session_number: int = 1

    # ─── Temporal Awareness ─────────────────────────────────────
    timezone: str = "UTC"                          # IANA timezone (e.g. "America/New_York")

    # ─── Multi-Channel ────────────────────────────────────────
    active_channel: str = "web"                   # web | email | sms | whatsapp | voice

    # ─── Scoped Tool Actions ────────────────────────────────
    pending_tool_request: Optional[dict] = None   # held request awaiting confirmation
    last_tool_result: Optional[dict] = None       # result from last executed tool
    _ws: Optional[object] = field(default=None, repr=False)  # WebSocket ref for task queue events
    crm_pushed: bool = False                      # auto-trigger: CRM push done

    # ─── User Profile Context ──────────────────────────────
    # Populated from profiles table at session start for authenticated users.
    # Used by assembler to inject user context into system prompts.
    profile_context: dict = field(default_factory=dict)

    # ─── Company Profile ────────────────────────────────────
    # Populated from org/user settings. Used by assembler for [COMPANY PROFILE] injection.
    # When company_name is empty, the entire block is inert.
    company_name: str = ""
    company_industry: str = ""
    company_location: str = ""
    company_hours: str = ""
    company_contact_email: str = ""
    company_contact_phone: str = ""
    company_website: str = ""
    company_faqs: list = field(default_factory=list)
    company_disclaimers: list = field(default_factory=list)
    company_policies: list = field(default_factory=list)

    # ─── Manifest Signature ──────────────────────────────────
    # Frozen snapshot of pack state captured at session birth.
    # Serves as dimension 7 of the Vault's eight-dimensional address.
    manifest_signature: dict = field(default_factory=dict)

    # ─── Vault RAG Context ──────────────────────────────────
    # Populated per-turn by vault_rag.fetch_vault_context() before each Claude call.
    # Read by assembler._build_special_instructions() for [VAULT CONTEXT] injection.
    # Ephemeral: not persisted, not serialized, refreshed every turn.
    vault_context: str = ""

    # ─── Multi-Pack Session (Fibonacci Plume Node 1) ──────────
    pack_history: list = field(default_factory=list)       # [{pack_id, entered_at, exited_at, carry_fields_out}]
    pack_handoff_context: str = ""                         # formatted context for assembler injection

    # ─── Session Memory (Fibonacci Plume Node 2) ──────────────
    session_memory: str = ""    # formatted cross-session context for assembler injection

    # ─── AI-to-AI Session (Fibonacci Plume Node 4) ───────────
    is_ai_session: bool = False
    ai_turn_count: int = 0
    ai_empty_turns: int = 0

    # ─── User Identity (Fibonacci Plume Node 6) ──────────────
    identity_context: str = ""    # formatted [USER IDENTITY] block for assembler injection
    prepopulated_fields: set = field(default_factory=set)  # field names pre-filled from identity

    # ─── Pack Pipeline (Fibonacci Plume Node 5) ──────────────
    pipeline_context: str = ""           # formatted [PIPELINE CONTEXT] block for assembler
    pipeline_instance_id: str = ""       # links session to active pipeline instance

    # ─── Vault Knowledge (Fibonacci Plume Node 7) ──────────────
    knowledge_context: str = ""          # formatted [VAULT KNOWLEDGE] block for assembler

    # ─── Self-Consulting System (Fibonacci Plume Node 10) ──────
    consultation_context: str = ""       # formatted [SYSTEM KNOWLEDGE] block for assembler

    # ─── Desk Context (cached at session birth) ────────────
    desk_contacts_context: str = ""   # formatted [CONTACTS] block, fetched once
    desk_inbox_context: str = ""      # formatted [INBOX] block, fetched once

    # ─── Data Rail ─────────────────────────────────────────
    receipt_tokens: list = field(default_factory=list)  # rail submission receipt tokens

    # ─── TimeKeeper (Fibonacci Plume Node 11) ──────────────────
    schedule_context: str = ""  # Ephemeral — next upcoming schedule events for prompt injection

    # ─── Pack Install (Fibonacci Plume Node 12) ────────────────
    registry_context: str = ""  # Ephemeral — catalog data for Pack Finder sessions

    # ─── The Loop (Fibonacci Plume Node 13) ──────────────────
    is_loop_session: bool = False
    loop_initiated_by: str = ""       # "schedule" | "chain" | "send"
    loop_chain_source: str = ""       # source pack_id if chained
    loop_context: str = ""            # formatted [LOOP CONTEXT] block for assembler

    # ─── Deliverable Feedback ──────────────────────────────
    feedback_context: str = ""        # Ephemeral — [DELIVERY FEEDBACK] block for assembler

    # ─── Consolidated Memory (Semantic Memory L2) ──────────
    consolidated_memory: str = ""     # Ephemeral — [CONSOLIDATED MEMORY] block for assembler

    # ─── Pack Intelligence ────────────────────────────────
    pack_stats_context: str = ""      # Ephemeral — [PACK ATTRIBUTES] block for assembler

    # ─── Prior Conversation Transcript ──────────────────────
    prior_transcript: str = ""        # Ephemeral — condensed snippet from last closed session

    # ─── Deployed Pack Routing ──────────────────────────────
    pack_source: str = "system"               # "system" | "user"
    pack_owner_id: Optional[str] = None       # deployer's user_id for user-deployed packs

    # ─── Transport Rail (PlayStop) ──────────────────────────
    playstop_state: str = "play"    # "play" | "pause" | "stop"

    # ─── Guest Turn Countdown ──────────────────────────────
    is_guest: bool = False
    turns_remaining: Optional[int] = None    # None = no limit (authed users)
    turn_limit: Optional[int] = None         # Total limit for display (e.g. 30)

    def add_message(self, role: str, content: str):
        """Add a message to rolling history."""
        self.history.append({"role": role, "content": content})
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        # Only count user messages as turns — greeting doesn't start the clock
        if role == "user":
            self.turn_count += 1

    def update_depth(self):
        """Recalculate rabbit hole depth based on activity."""
        unique_games = len(set(self.games_played))
        if unique_games == 0:
            self.depth = 0
        elif unique_games == 1 and self.turn_count < 10:
            self.depth = 1
        elif unique_games <= 2 or self.turn_count < 25:
            self.depth = 2
        elif unique_games <= 4:
            self.depth = 3
        elif unique_games <= 5:
            self.depth = 4
        else:
            self.depth = 5  # all 6 games played

    def enter_game(self, game_key: str):
        """Enter a game cartridge."""
        self.current_game = game_key
        if game_key not in self.games_played:
            self.games_played.append(game_key)
        self.update_depth()

    def exit_game(self):
        """Exit current cartridge to menu."""
        self.current_game = None

    def to_context_string(self) -> str:
        """Compact state summary for injection into the system prompt."""
        from prompt_guard import sanitize_for_prompt

        lines = [
            f"[SESSION STATE]",
            f"Session: {self.session_id} | User: {self.user_id}",
            f"Depth: {self.depth}/5",
            f"Mood: {self.mood}",
            f"Turn: {self.turn_count}",
            f"Cartridges Visited: {', '.join(self.games_played) if self.games_played else 'none'}",
            f"Current Cartridge: {self.current_game or 'menu'}",
            f"Channel: {self.active_channel}",
            f"Transport: {self.playstop_state}",
        ]

        if self.turns_remaining is not None:
            lines.append(f"Turns Remaining: {self.turns_remaining}/{self.turn_limit or '?'}")

        if getattr(self, "is_loop_session", False):
            lines.append(f"Loop Session: initiated by {self.loop_initiated_by or 'chain'}")

        # Submitted forms — sanitize user-controlled values before prompt interpolation
        if self.forms:
            lines.append("[SUBMITTED FORMS]")
            for form_id, form_data in self.forms.items():
                lines.append(f"  [form:{sanitize_for_prompt(str(form_id))}]")
                for fk, fv in form_data.items():
                    if fk != "submitted_at":
                        lines.append(f"    {sanitize_for_prompt(str(fk))}: {sanitize_for_prompt(str(fv))}")

        # Rail submissions — receipt tokens (PII-free references to captured data)
        if self.receipt_tokens:
            lines.append("[RAIL SUBMISSIONS]")
            for token in self.receipt_tokens:
                lines.append(f"  {token}")

        return "\n".join(lines)
