from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


ASTROLOGY_CARD_TRACKER_CONFIG_KEY = "combat_astrology_card_tracker"
ASTROLOGY_CARD_COUNT = 5
ASTROLOGY_MIN_CARD_COUNT = 1
ASTROLOGY_COUNTER_CHOICES = (5, 6)
ASTROLOGY_DEFAULT_COUNTER_THRESHOLD = 6
ASTROLOGY_UNSET_LABEL = "请选择"

ASTROLOGY_SUIT_LUCK = "幸运型"
ASTROLOGY_SUIT_INTERFERENCE = "干扰型"
ASTROLOGY_SUIT_SUPPORT = "支援型"
ASTROLOGY_SUIT_ATTACK = "攻击型"
ASTROLOGY_SUIT_OPTIONS = (
    ASTROLOGY_SUIT_LUCK,
    ASTROLOGY_SUIT_INTERFERENCE,
    ASTROLOGY_SUIT_SUPPORT,
    ASTROLOGY_SUIT_ATTACK,
)

ASTROLOGY_CARDS_BY_SUIT: Mapping[str, tuple[str, ...]] = {
    ASTROLOGY_SUIT_LUCK: ("恶魔", "命运之轮", "星星"),
    ASTROLOGY_SUIT_INTERFERENCE: ("倒吊者",),
    ASTROLOGY_SUIT_SUPPORT: ("月亮", "教皇"),
    ASTROLOGY_SUIT_ATTACK: ("力量", "皇帝", "女皇", "正义", "审判"),
}
ASTROLOGY_CARD_OPTIONS = tuple(
    card
    for suit in ASTROLOGY_SUIT_OPTIONS
    for card in ASTROLOGY_CARDS_BY_SUIT[suit]
)
ASTROLOGY_CARD_SUIT = {
    card: suit
    for suit, cards in ASTROLOGY_CARDS_BY_SUIT.items()
    for card in cards
}
WHEEL_OF_FORTUNE_CARD = "命运之轮"

# The insertion order is also the settings-page order requested by the user.
ASTROLOGY_SKILLS: Mapping[str, Mapping[str, Any]] = {
    "starry_field": {"name": "星辉领域", "skill_id": 27202},
    "whirling_assault": {"name": "疾旋突袭", "skill_id": 27203},
    "star_blast": {"name": "星之爆破", "skill_id": 27201},
    "space_slash": {"name": "空间斩", "skill_id": 27200},
    "revolving_impact": {"name": "回旋冲击", "skill_id": 27204},
    "gravity_field": {"name": "重力场", "skill_id": 27206},
    "starlight_bloom": {"name": "星辉绽放", "skill_id": 27205},
    "fatal_fall": {"name": "致命坠击", "skill_id": 27210},
}

ASTROLOGY_CORE_COOLDOWN_DEFAULTS: Mapping[int, float] = {
    int(ASTROLOGY_SKILLS["starry_field"]["skill_id"]): 9.0,
    int(ASTROLOGY_SKILLS["whirling_assault"]["skill_id"]): 12.0,
}
ASTROLOGY_CRITICAL_COOLDOWN_SKILL_IDS = frozenset(
    int(ASTROLOGY_SKILLS[key]["skill_id"])
    for key in ("starry_field", "whirling_assault")
)
ASTROLOGY_CRITICAL_COOLDOWN_REDUCTION_MS = 2_000
ASTROLOGY_CRITICAL_CORRELATION_WINDOW_MS = 1_500
ASTROLOGY_MIN_COOLDOWN_SECONDS = 0.1
ASTROLOGY_MAX_COOLDOWN_SECONDS = 9999.0


def _normalize_cooldown_seconds(value: Any, default: float) -> float:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        seconds = default
    if not ASTROLOGY_MIN_COOLDOWN_SECONDS <= seconds <= ASTROLOGY_MAX_COOLDOWN_SECONDS:
        seconds = default
    return float(seconds)


def default_astrology_card_tracker_config() -> dict[str, Any]:
    return {
        "tracked_skills": {
            str(skill_id): False for skill_id in ASTROLOGY_CORE_COOLDOWN_DEFAULTS
        },
        "counter_threshold": ASTROLOGY_DEFAULT_COUNTER_THRESHOLD,
        "deck": ["" for _ in range(ASTROLOGY_CARD_COUNT)],
        "skill_suits": {
            str(int(item["skill_id"])): "" for item in ASTROLOGY_SKILLS.values()
        },
        "base_cooldown_seconds": {
            str(skill_id): seconds
            for skill_id, seconds in ASTROLOGY_CORE_COOLDOWN_DEFAULTS.items()
        },
    }


def ensure_astrology_card_tracker_config(data: dict[str, Any]) -> dict[str, Any]:
    raw = data.get(ASTROLOGY_CARD_TRACKER_CONFIG_KEY)
    if not isinstance(raw, dict):
        raw = {}
        data[ASTROLOGY_CARD_TRACKER_CONFIG_KEY] = raw

    legacy_enabled = bool(raw.get("enabled", False))
    source_tracked_skills = raw.get("tracked_skills")
    if not isinstance(source_tracked_skills, dict):
        source_tracked_skills = {}
    raw["tracked_skills"] = {
        str(skill_id): bool(
            source_tracked_skills.get(str(skill_id), legacy_enabled)
        )
        for skill_id in ASTROLOGY_CORE_COOLDOWN_DEFAULTS
    }
    raw.pop("enabled", None)
    try:
        threshold = int(raw.get("counter_threshold"))
    except (TypeError, ValueError):
        threshold = ASTROLOGY_DEFAULT_COUNTER_THRESHOLD
    if threshold not in ASTROLOGY_COUNTER_CHOICES:
        threshold = ASTROLOGY_DEFAULT_COUNTER_THRESHOLD
    raw["counter_threshold"] = threshold

    source_deck = raw.get("deck")
    if not isinstance(source_deck, list):
        source_deck = []
    deck: list[str] = []
    for index in range(ASTROLOGY_CARD_COUNT):
        value = str(source_deck[index]).strip() if index < len(source_deck) else ""
        deck.append(value if value in ASTROLOGY_CARD_SUIT else "")
    raw["deck"] = deck

    source_suits = raw.get("skill_suits")
    if not isinstance(source_suits, dict):
        source_suits = {}
    skill_suits: dict[str, str] = {}
    for item in ASTROLOGY_SKILLS.values():
        skill_id = str(int(item["skill_id"]))
        suit = str(source_suits.get(skill_id, "")).strip()
        skill_suits[skill_id] = suit if suit in ASTROLOGY_SUIT_OPTIONS else ""
    raw["skill_suits"] = skill_suits

    source_cooldowns = raw.get("base_cooldown_seconds")
    if not isinstance(source_cooldowns, dict):
        source_cooldowns = {}
    base_cooldown_seconds: dict[str, float | int] = {}
    for skill_id, default in ASTROLOGY_CORE_COOLDOWN_DEFAULTS.items():
        seconds = _normalize_cooldown_seconds(
            source_cooldowns.get(str(skill_id)),
            default,
        )
        base_cooldown_seconds[str(skill_id)] = (
            int(seconds) if seconds.is_integer() else seconds
        )
    raw["base_cooldown_seconds"] = base_cooldown_seconds
    return raw


@dataclass(frozen=True)
class AstrologyCardTrackerSettings:
    tracked_skill_ids: frozenset[int] = field(default_factory=frozenset)
    counter_threshold: int = ASTROLOGY_DEFAULT_COUNTER_THRESHOLD
    deck: tuple[str, ...] = ()
    skill_suits: Mapping[int, str] = field(default_factory=dict)
    base_cooldown_seconds: Mapping[int, float] = field(default_factory=dict)

    @property
    def configured(self) -> bool:
        return (
            bool(self.tracked_skill_ids)
            and ASTROLOGY_MIN_CARD_COUNT <= len(self.deck) <= ASTROLOGY_CARD_COUNT
            and all(card in ASTROLOGY_CARD_SUIT for card in self.deck)
            and all(
                int(item["skill_id"]) in self.skill_suits
                and self.skill_suits[int(item["skill_id"])] in ASTROLOGY_SUIT_OPTIONS
                for item in ASTROLOGY_SKILLS.values()
            )
            and all(
                skill_id in self.base_cooldown_seconds
                and ASTROLOGY_MIN_COOLDOWN_SECONDS
                <= self.base_cooldown_seconds[skill_id]
                <= ASTROLOGY_MAX_COOLDOWN_SECONDS
                for skill_id in ASTROLOGY_CORE_COOLDOWN_DEFAULTS
            )
        )

    def tracks_skill(self, skill_id: int) -> bool:
        return int(skill_id) in self.tracked_skill_ids


def load_astrology_card_tracker_settings(
    data: dict[str, Any],
) -> AstrologyCardTrackerSettings:
    if not isinstance(data.get(ASTROLOGY_CARD_TRACKER_CONFIG_KEY), dict):
        return AstrologyCardTrackerSettings()
    raw = ensure_astrology_card_tracker_config(data)
    active_deck: list[str] = []
    for card in raw["deck"]:
        card = str(card)
        if not card:
            break
        active_deck.append(card)
    return AstrologyCardTrackerSettings(
        tracked_skill_ids=frozenset(
            int(skill_id)
            for skill_id, enabled in raw["tracked_skills"].items()
            if enabled
        ),
        counter_threshold=int(raw["counter_threshold"]),
        deck=tuple(active_deck),
        skill_suits={
            int(skill_id): str(suit)
            for skill_id, suit in raw["skill_suits"].items()
            if str(suit) in ASTROLOGY_SUIT_OPTIONS
        },
        base_cooldown_seconds={
            int(skill_id): float(seconds)
            for skill_id, seconds in raw["base_cooldown_seconds"].items()
        },
    )


@dataclass(frozen=True)
class AstrologyCardUpdate:
    at_ms: int
    action: str
    skill_id: int
    skill_suit: str
    card: str | None
    counter: int
    next_card_number: int
    cooldown_ready_at_ms: int | None = None


class AstrologyCardTracker:
    """Rebuild the combat-astrology counter and held card from successful E12s.

    The configured first card is treated as the next card after a tracker reset.
    Live mode resets when the self entity id is learned or changes, which matches the
    normal workflow of starting the plugin before using combat-astrology skills.
    """

    def __init__(self, settings: AstrologyCardTrackerSettings) -> None:
        self.settings = settings
        self.revision = 0
        self.last_update: AstrologyCardUpdate | None = None
        self.reset()

    @property
    def configured(self) -> bool:
        return self.settings.configured

    @property
    def held_card_suit(self) -> str | None:
        if self.held_card is None:
            return None
        return ASTROLOGY_CARD_SUIT.get(self.held_card)

    @property
    def next_card_number(self) -> int:
        return self.next_card_index + 1

    def reset(self) -> None:
        self.counter = 0
        self.held_card: str | None = None
        self.next_card_index = 0
        self.cooldown_ready_at_ms: dict[int, int] = {}
        self.last_skill_use_at_ms: dict[int, int] = {}
        self.critical_reduced_use_at_ms: dict[int, int] = {}
        self.last_update = None
        self.revision += 1

    def skill_can_consume_current_card(self, skill_id: int) -> bool:
        held_suit = self.held_card_suit
        return bool(
            held_suit is not None
            and self.settings.skill_suits.get(int(skill_id)) == held_suit
        )

    def skill_cooldown_ready_at_ms(self, skill_id: int) -> int | None:
        return self.cooldown_ready_at_ms.get(int(skill_id))

    def skill_cooldown_remaining_seconds(
        self,
        skill_id: int,
        *,
        at_ms: int,
    ) -> float | None:
        ready_at_ms = self.skill_cooldown_ready_at_ms(skill_id)
        if ready_at_ms is None:
            return None
        return max(0.0, (ready_at_ms - int(at_ms)) / 1000.0)

    def skill_is_ready(self, skill_id: int, *, at_ms: int) -> bool | None:
        remaining = self.skill_cooldown_remaining_seconds(skill_id, at_ms=at_ms)
        if remaining is None:
            return None
        return remaining <= 0.0

    def skill_is_available(self, skill_id: int, *, at_ms: int) -> bool:
        """Return whether an enabled core skill can currently be cast.

        Before the first observed use, the normal post-login workflow treats the
        skill as ready.  A held card of the matching suit also makes the skill
        available even while its ordinary cooldown is still running.
        """

        skill_id = int(skill_id)
        if not self.settings.tracks_skill(skill_id):
            return False
        if self.skill_can_consume_current_card(skill_id):
            return True
        ready = self.skill_is_ready(skill_id, at_ms=at_ms)
        return True if ready is None else ready

    def is_relevant_event(self, event: Mapping[str, Any]) -> bool:
        if not self.configured:
            return False
        try:
            event_id = int(event.get("EventId"))
            skill_id = int(event.get("SkillId"))
        except (TypeError, ValueError):
            return False
        if skill_id not in self.settings.skill_suits:
            return False
        return event_id == 12 or (
            event_id == 3 and skill_id in ASTROLOGY_CRITICAL_COOLDOWN_SKILL_IDS
        )

    def process_event(
        self,
        event: Mapping[str, Any],
        *,
        self_entity_id: str | None,
    ) -> AstrologyCardUpdate | None:
        if not self.configured:
            return None
        if self_entity_id is None or str(event.get("Id", "")) != str(self_entity_id):
            return None
        try:
            event_id = int(event.get("EventId"))
            skill_id = int(event.get("SkillId"))
            at_ms = int(event.get("At"))
        except (TypeError, ValueError):
            return None
        if event_id == 3:
            return self._process_critical_damage(event, skill_id=skill_id, at_ms=at_ms)
        if event_id != 12:
            return None
        skill_suit = self.settings.skill_suits.get(skill_id)
        if skill_suit not in ASTROLOGY_SUIT_OPTIONS:
            return None

        cooldown_ready_at_ms: int | None = None
        base_cooldown_seconds = self.settings.base_cooldown_seconds.get(skill_id)
        if base_cooldown_seconds is not None:
            cooldown_ready_at_ms = at_ms + round(base_cooldown_seconds * 1000.0)
            self.cooldown_ready_at_ms[skill_id] = cooldown_ready_at_ms
            self.last_skill_use_at_ms[skill_id] = at_ms
            self.critical_reduced_use_at_ms.pop(skill_id, None)

        action = "counted"
        affected_card: str | None = self.held_card
        if self.held_card is not None:
            if skill_suit != self.held_card_suit:
                action = "held_mismatch"
            else:
                consumed_card = self.held_card
                affected_card = consumed_card
                self.counter = 0
                if consumed_card == WHEEL_OF_FORTUNE_CARD:
                    self.held_card = self._draw_next_card()
                    action = "wheel_pass"
                else:
                    self.held_card = None
                    action = "consumed"
        else:
            self.counter += 1
            if self.counter >= self.settings.counter_threshold:
                self.counter = 0
                self.held_card = self._draw_next_card()
                affected_card = self.held_card
                action = "acquired"

        update = AstrologyCardUpdate(
            at_ms=at_ms,
            action=action,
            skill_id=skill_id,
            skill_suit=skill_suit,
            card=affected_card,
            counter=self.counter,
            next_card_number=self.next_card_number,
            cooldown_ready_at_ms=cooldown_ready_at_ms,
        )
        self.last_update = update
        self.revision += 1
        return update

    def _process_critical_damage(
        self,
        event: Mapping[str, Any],
        *,
        skill_id: int,
        at_ms: int,
    ) -> AstrologyCardUpdate | None:
        if skill_id not in ASTROLOGY_CRITICAL_COOLDOWN_SKILL_IDS:
            return None
        critical = event.get("IsCritical", False)
        if isinstance(critical, str):
            critical = critical.strip().casefold() in {"1", "true", "yes"}
        if not bool(critical):
            return None
        last_use_at_ms = self.last_skill_use_at_ms.get(skill_id)
        ready_at_ms = self.cooldown_ready_at_ms.get(skill_id)
        if last_use_at_ms is None or ready_at_ms is None:
            return None
        elapsed_ms = at_ms - last_use_at_ms
        if not 0 <= elapsed_ms <= ASTROLOGY_CRITICAL_CORRELATION_WINDOW_MS:
            return None
        # Both core skills may emit more than one damage event for one successful
        # cast.  The E12 timestamp identifies that cast, so every cast can shorten
        # its cooldown at most once even when several of its hits are critical.
        if self.critical_reduced_use_at_ms.get(skill_id) == last_use_at_ms:
            return None

        ready_at_ms = max(
            at_ms,
            ready_at_ms - ASTROLOGY_CRITICAL_COOLDOWN_REDUCTION_MS,
        )
        self.cooldown_ready_at_ms[skill_id] = ready_at_ms
        self.critical_reduced_use_at_ms[skill_id] = last_use_at_ms
        update = AstrologyCardUpdate(
            at_ms=at_ms,
            action="critical_reduction",
            skill_id=skill_id,
            skill_suit=self.settings.skill_suits[skill_id],
            card=self.held_card,
            counter=self.counter,
            next_card_number=self.next_card_number,
            cooldown_ready_at_ms=ready_at_ms,
        )
        self.last_update = update
        self.revision += 1
        return update

    def _draw_next_card(self) -> str:
        card = self.settings.deck[self.next_card_index]
        self.next_card_index = (self.next_card_index + 1) % len(self.settings.deck)
        return card
