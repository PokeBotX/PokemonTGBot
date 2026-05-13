"""Async PostgreSQL database layer."""

from __future__ import annotations

import asyncio
import json
import os
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional, Sequence

import asyncpg
import structlog
from redis import Redis
from redis.exceptions import RedisError

logger = structlog.get_logger()

POKEDOLLAR_CODE = "pokedollar"
POKECOIN_CODE = "pokecoin"
REGULAR_POKEBALL_CODE = "pokeball"
ULTRABALL_CODE = "ultraball"
MASTERBALL_CODE = "masterball"
WELCOME_POKEDOLLAR_AMOUNT = 1000
SHOP_BONUS_CAP = 750
SHOP_BONUS_RATE_PER_HOUR = 125
SHOP_BONUS_CLAIM_INTERVAL_SECONDS = 3600
SHOP_BONUS_CAP_SECONDS = 6 * 3600
CHAT_ENCOUNTER_COOLDOWN_SECONDS = 3 * 3600
CHAT_ENCOUNTER_MESSAGE_THRESHOLD = 10
CHAT_ENCOUNTER_TIMEOUT_SECONDS = 5 * 60
CHAT_ENCOUNTER_COUNTER_TTL_SECONDS = 7 * 24 * 60 * 60
CHAT_ENCOUNTER_TEXT = "Кто-то пришёл..."
CHAT_ENCOUNTER_EXPIRED_TEXT = "Тут кто-то был..."
CHAT_ENCOUNTER_BALL_CATCH_CHANCES = {
    REGULAR_POKEBALL_CODE: 60.0,
    ULTRABALL_CODE: 80.0,
    MASTERBALL_CODE: 100.0,
}
SPIN_PRICE = 500
ULTRABALL_PRICE = 200
MASTERBALL_PRICE = 800
COLLECTION_PAGE_SIZE = 12
MARKET_PAGE_SIZE = 10
MARKET_MAX_ACTIVE_LISTINGS = 2
MARKET_MAX_ACTIVE_BUY_REQUESTS = 5
MARKET_LISTING_LIFETIME_DAYS = 5
MARKET_LISTING_COMMISSION_RATE = 0.01
MARKET_MAINTENANCE_INTERVAL_SECONDS = 60 * 60
MARKET_LISTING_STATUS_ACTIVE = "active"
MARKET_LISTING_STATUS_SOLD = "sold"
MARKET_LISTING_STATUS_REMOVED = "removed"
MARKET_LISTING_STATUS_EXPIRED = "expired"
MARKET_REQUEST_STATUS_ACTIVE = "active"
MARKET_REQUEST_STATUS_FULFILLED = "fulfilled"
MARKET_REQUEST_STATUS_CANCELED = "canceled"
TRADE_STATUS_PENDING = "pending"
TRADE_STATUS_ACTIVE = "active"
TRADE_STATUS_REJECTED = "rejected"
TRADE_STATUS_CANCELED = "canceled"
TRADE_STATUS_EXPIRED = "expired"
TRADE_STATUS_COMPLETED = "completed"
TRADE_PENDING_TTL_SECONDS = 2 * 60
TRADE_ACTIVE_TTL_SECONDS = 10 * 60
TRADE_MAX_OFFERS_PER_SIDE = 6
TRADE_MAINTENANCE_INTERVAL_SECONDS = 30
PVP_CHALLENGE_STATUS_PENDING = "pending"
PVP_CHALLENGE_STATUS_SELECTING_INITIATOR = "selecting_initiator"
PVP_CHALLENGE_STATUS_SELECTING_TARGET = "selecting_target"
PVP_CHALLENGE_STATUS_BATTLING = "battling"
PVP_CHALLENGE_STATUS_REJECTED = "rejected"
PVP_CHALLENGE_STATUS_CANCELED = "canceled"
PVP_CHALLENGE_STATUS_EXPIRED = "expired"
PVP_CHALLENGE_STATUS_COMPLETED = "completed"
PVP_CHALLENGE_PENDING_TTL_SECONDS = 2 * 60
PVP_CHALLENGE_SELECTION_TTL_SECONDS = 8 * 60
PVP_MAINTENANCE_INTERVAL_SECONDS = 30
PVP_TEAM_SLOT_COUNT = 5
PVP_DAILY_REWARD_LIMIT = 3
PVP_WIN_REWARD_POKEDOLLAR = 500
MARKET_SORT_NEWEST = "newest"
MARKET_SORT_CHEAPEST = "cheapest"
POKEMON_RELEASE_REWARDS = {
    "Common": 32,
    "Rare": 100,
    "Epic": 325,
    "Legendary": 1000,
}
EPIC_PITY_THRESHOLD = 15
LEGENDARY_PITY_THRESHOLD = 40
RARITY_PROBABILITIES = {
    "Legendary": 2.0,
    "Epic": 7.5,
    "Rare": 20.2,
    "Common": 70.3,
}
RARITY_ORDER = ("Legendary", "Epic", "Rare", "Common")
FORM_KIND_BASE = "base"
FORM_KIND_SHINY = "shiny"
FORM_KIND_MEGA = "mega"
FORM_KIND_GIGANTAMAX = "gigantamax"
FORM_BADGE_MAP = {
    FORM_KIND_SHINY: "Shiny",
    FORM_KIND_MEGA: "Mega",
    FORM_KIND_GIGANTAMAX: "Gigantamax",
}
FORM_SUFFIX_MAP = {
    FORM_KIND_SHINY: "0",
    FORM_KIND_MEGA: "1",
    FORM_KIND_GIGANTAMAX: "2",
}
FORM_SUFFIX_TO_KIND = {suffix: kind for kind, suffix in FORM_SUFFIX_MAP.items()}
FORM_INTERNAL_ID_OFFSET_MAP = {
    FORM_KIND_SHINY: 10_000,
    FORM_KIND_MEGA: 20_000,
    FORM_KIND_GIGANTAMAX: 30_000,
}
FORM_ENCOUNTER_OVERLAY_PROBABILITIES = {
    FORM_KIND_SHINY: 10.0,
    FORM_KIND_MEGA: 5.0,
    FORM_KIND_GIGANTAMAX: 5.0,
}


def _coerce_json_object(value: object) -> dict[str, object] | None:
    """Best-effort normalize asyncpg JSON/JSONB payloads into dicts."""
    if value is None:
        return None
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"raw": value}
        return dict(parsed) if isinstance(parsed, dict) else {"raw": parsed}
    return {"raw": value}


def build_form_internal_pokemon_id(base_pokemon_id: int, form_kind: str) -> int:
    """Build a deterministic internal catalog id for a first-wave form."""
    offset = FORM_INTERNAL_ID_OFFSET_MAP.get(form_kind)
    if offset is None:
        raise ShopError("Форма должна быть одной из: shiny, mega, gigantamax.")
    if base_pokemon_id <= 0:
        raise ShopError("base_pokemon_id должен быть больше нуля.")
    return base_pokemon_id + offset


def _base_dex_from_form_code(dex_form_code: str | None) -> str | None:
    """Return the base dex portion from one form code."""
    if not dex_form_code:
        return None
    normalized = dex_form_code.strip()
    if not normalized:
        return None
    return normalized.split("-", 1)[0]


def _form_kind_from_dex_form_code(dex_form_code: str | None) -> str:
    """Resolve first-wave form kind from one external form code."""
    if not dex_form_code or "-" not in dex_form_code:
        return FORM_KIND_BASE
    suffix = dex_form_code.rsplit("-", 1)[-1]
    return FORM_SUFFIX_TO_KIND.get(suffix, FORM_KIND_BASE)


def _form_badge_from_dex_form_code(dex_form_code: str | None) -> str | None:
    """Return user-facing form badge text for one form code."""
    return FORM_BADGE_MAP.get(_form_kind_from_dex_form_code(dex_form_code))


def _build_base_dex_form_code(pokemon_id: int) -> str:
    """Build the default base-form code for a catalog entry."""
    return str(pokemon_id)


def _dex_form_sort_sql(*, qualified_column: str) -> str:
    """Build SQL for natural ordering of dex-form codes like 202, 202-0, 203."""
    normalized = f"COALESCE({qualified_column}, '')"
    return (
        f"split_part({normalized}, '-', 1)::int ASC, "
        f"CASE "
        f"WHEN {normalized} = '' THEN -1 "
        f"WHEN position('-' in {normalized}) = 0 THEN -1 "
        f"ELSE split_part({normalized}, '-', 2)::int "
        f"END ASC"
    )


def _choose_form_overlay_kind(
    available_form_kinds: Sequence[str],
    *,
    roll: float | None = None,
) -> str:
    """Choose one first-wave encounter overlay form or fall back to base."""
    normalized_available = set(available_form_kinds)
    if roll is None:
        roll = random.uniform(0.0, 100.0)

    cumulative = 0.0
    for form_kind in (FORM_KIND_SHINY, FORM_KIND_MEGA, FORM_KIND_GIGANTAMAX):
        if form_kind not in normalized_available:
            continue
        cumulative += FORM_ENCOUNTER_OVERLAY_PROBABILITIES[form_kind]
        if roll < cumulative:
            return form_kind
    return FORM_KIND_BASE


class ShopError(RuntimeError):
    """Base class for shop-related failures."""


class ShopUnavailableError(ShopError):
    """Raised when the database-backed shop is unavailable."""


class InsufficientFundsError(ShopError):
    """Raised when the user cannot afford an action."""


class BonusNotReadyError(ShopError):
    """Raised when the daily bonus is still on cooldown."""

    def __init__(self, remaining_seconds: int) -> None:
        self.remaining_seconds = remaining_seconds
        super().__init__("Bonus claim is not ready yet")


class SummarySessionError(ShopError):
    """Raised when a stored x5 result summary is unavailable."""


@dataclass(slots=True)
class ShopView:
    """Shop screen state for a user."""

    user_id: int
    balance: int
    pokecoin_balance: int
    ultraball_quantity: int
    masterball_quantity: int
    epic_pity_counter: int
    legendary_pity_counter: int
    bonus_available: int
    bonus_ready_in_seconds: int


@dataclass(slots=True)
class BonusClaimResult:
    """Result of claiming the daily bonus."""

    amount_claimed: int
    next_bonus_in_seconds: int
    shop_view: ShopView


@dataclass(slots=True)
class ItemPurchaseResult:
    """Result of purchasing one shop item."""

    item_code: str
    item_name: str
    item_price: int
    quantity_after: int
    shop_view: ShopView


@dataclass(slots=True)
class PokemonReward:
    """A user-owned pokemon obtained from the shop gacha."""

    user_pokemon_id: int
    pokemon_id: int
    dex_form_code: Optional[str]
    name: str
    rarity: str
    pokemon_type: Optional[str]
    base_hp: int
    base_attack: int
    base_defense: int
    base_stamina: int
    image_credit_id: Optional[int]
    form_badge: Optional[str]

    def as_session_payload(self) -> dict[str, object]:
        """Convert reward to a JSON-like payload for in-memory sessions."""
        return {
            "user_pokemon_id": self.user_pokemon_id,
            "pokemon_id": self.pokemon_id,
            "dex_form_code": self.dex_form_code,
            "name": self.name,
            "rarity": self.rarity,
            "pokemon_type": self.pokemon_type,
            "base_hp": self.base_hp,
            "base_attack": self.base_attack,
            "base_defense": self.base_defense,
            "base_stamina": self.base_stamina,
            "image_credit_id": self.image_credit_id,
            "form_badge": self.form_badge,
        }


@dataclass(slots=True)
class SpinResult:
    """Outcome of one or multiple shop spins."""

    rewards: list[PokemonReward]
    spent_amount: int
    shop_view: ShopView
 

@dataclass(slots=True)
class CollectionFilterState:
    """Current collection filters used for browsing."""

    rarities: tuple[str, ...] = ()
    types: tuple[str, ...] = ()
    duplicates_only: bool = False
    locked_only: bool = False
    query: str = ""
    page: int = 1

    def with_page(self, page: int) -> "CollectionFilterState":
        """Return a copy with the requested page."""
        return CollectionFilterState(
            rarities=self.rarities,
            types=self.types,
            duplicates_only=self.duplicates_only,
            locked_only=self.locked_only,
            query=self.query,
            page=page,
        )

    def to_session_payload(self) -> dict[str, object]:
        """Serialize filter state for session storage."""
        return {
            "rarities": list(self.rarities),
            "types": list(self.types),
            "duplicates_only": self.duplicates_only,
            "locked_only": self.locked_only,
            "query": self.query,
            "page": self.page,
        }

    @classmethod
    def from_payload(cls, payload: Optional[dict[str, object]]) -> "CollectionFilterState":
        """Deserialize filter state from session payload."""
        if not payload:
            return cls()
        return cls(
            rarities=tuple(str(value) for value in payload.get("rarities", []) if value),
            types=tuple(str(value) for value in payload.get("types", []) if value),
            duplicates_only=bool(payload.get("duplicates_only", False)),
            locked_only=bool(payload.get("locked_only", False)),
            query=str(payload.get("query") or "").strip(),
            page=max(1, int(payload.get("page", 1))),
        )


@dataclass(slots=True)
class PokedexFilterState:
    """Current pokedex filters used for Mini App browsing."""

    rarities: tuple[str, ...] = ()
    types: tuple[str, ...] = ()
    collected_state: str = "all"
    form_kinds: tuple[str, ...] = ()
    query: str = ""
    page: int = 1

    def with_page(self, page: int) -> "PokedexFilterState":
        return PokedexFilterState(
            rarities=self.rarities,
            types=self.types,
            collected_state=self.collected_state,
            form_kinds=self.form_kinds,
            query=self.query,
            page=page,
        )


@dataclass(slots=True)
class CollectionEntry:
    """Aggregated collection entry for one pokemon species."""

    pokemon_id: int
    sample_user_pokemon_id: int
    name: str
    rarity: str
    pokemon_type: Optional[str]
    quantity: int
    base_hp: int
    base_attack: int
    base_defense: int
    base_stamina: int
    image_credit_id: Optional[int]
    is_locked: bool = False
    dex_form_code: Optional[str] = None
    form_badge: Optional[str] = None

    def as_session_payload(self) -> dict[str, object]:
        """Serialize entry for session storage."""
        return {
            "pokemon_id": self.pokemon_id,
            "sample_user_pokemon_id": self.sample_user_pokemon_id,
            "name": self.name,
            "rarity": self.rarity,
            "pokemon_type": self.pokemon_type,
            "quantity": self.quantity,
            "base_hp": self.base_hp,
            "base_attack": self.base_attack,
            "base_defense": self.base_defense,
            "base_stamina": self.base_stamina,
            "image_credit_id": self.image_credit_id,
            "is_locked": self.is_locked,
            "dex_form_code": self.dex_form_code,
            "form_badge": self.form_badge,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "CollectionEntry":
        """Deserialize entry from session payload."""
        return cls(
            pokemon_id=int(payload["pokemon_id"]),
            sample_user_pokemon_id=int(payload["sample_user_pokemon_id"]),
            name=str(payload["name"]),
            rarity=str(payload["rarity"]),
            pokemon_type=payload.get("pokemon_type"),
            quantity=int(payload["quantity"]),
            base_hp=int(payload["base_hp"]),
            base_attack=int(payload["base_attack"]),
            base_defense=int(payload["base_defense"]),
            base_stamina=int(payload["base_stamina"]),
            image_credit_id=payload.get("image_credit_id"),
            is_locked=bool(payload.get("is_locked", False)),
            dex_form_code=payload.get("dex_form_code"),
            form_badge=payload.get("form_badge"),
        )


@dataclass(slots=True)
class CollectionPage:
    """Paginated collection results."""

    entries: list[CollectionEntry]
    filter_state: CollectionFilterState
    total_entries: int
    current_page: int
    total_pages: int

    def has_previous(self) -> bool:
        return self.current_page > 1

    def has_next(self) -> bool:
        return self.current_page < self.total_pages


@dataclass(slots=True)
class MiniAppCollectionPage:
    """Paginated collection results for the Mini App with variable page size."""

    entries: list[CollectionEntry]
    filter_state: CollectionFilterState
    total_entries: int
    current_page: int
    total_pages: int
    page_size: int

    def has_previous(self) -> bool:
        return self.current_page > 1

    def has_next(self) -> bool:
        return self.current_page < self.total_pages


@dataclass(slots=True)
class PokedexEntry:
    """One exact pokedex catalog entry, including collected state for the current user."""

    pokemon_id: int
    name: str
    rarity: str
    pokemon_type: Optional[str]
    base_hp: int
    base_attack: int
    base_defense: int
    base_stamina: int
    image_credit_id: Optional[int]
    dex_form_code: Optional[str] = None
    form_badge: Optional[str] = None
    owned_quantity: int = 0

    @property
    def is_collected(self) -> bool:
        return self.owned_quantity > 0


@dataclass(slots=True)
class MiniAppPokedexPage:
    """Paginated Mini App pokedex results with exact-form ownership flags."""

    entries: list[PokedexEntry]
    filter_state: PokedexFilterState
    total_entries: int
    current_page: int
    total_pages: int
    page_size: int

    def has_previous(self) -> bool:
        return self.current_page > 1

    def has_next(self) -> bool:
        return self.current_page < self.total_pages


@dataclass(slots=True)
class PokedexRelatedForm:
    """Sibling form metadata for one pokedex detail page."""

    pokemon_id: int
    dex_form_code: Optional[str]
    form_badge: Optional[str]
    is_collected: bool


@dataclass(slots=True)
class PokedexDetail:
    """Read-only Mini App pokedex detail payload."""

    pokemon_id: int
    name: str
    rarity: str
    pokemon_type: Optional[str]
    base_hp: int
    base_attack: int
    base_defense: int
    base_stamina: int
    image_credit_id: Optional[int]
    dex_form_code: Optional[str] = None
    form_badge: Optional[str] = None
    owned_quantity: int = 0
    related_forms: list[PokedexRelatedForm] = field(default_factory=list)

    @property
    def is_collected(self) -> bool:
        return self.owned_quantity > 0


@dataclass(slots=True)
class ProfileRarityProgress:
    """Unique-pokemon progress within one rarity bucket."""

    rarity: str
    owned_unique: int
    total_catalog: int
    percent: int


@dataclass(slots=True)
class ProfileSummary:
    """Read model for the profile root screen."""

    user_id: int
    telegram_id: int
    tg_username: Optional[str]
    nickname: Optional[str]
    language: str
    created_at: datetime
    total_unique_owned: int
    total_catalog: int
    total_unique_percent: int
    rarity_progress: tuple[ProfileRarityProgress, ...]
    profile_pic_credit_id: Optional[int]
    cover_pokemon_name: Optional[str]
    total_form_owned: int = 0
    total_form_catalog: int = 0
    total_form_percent: int = 0


@dataclass(slots=True)
class PvpTeamSlot:
    """One configured PvP team slot."""

    slot_index: int
    entry: Optional[CollectionEntry]


@dataclass(slots=True)
class PvpTeam:
    """Persistent five-slot PvP team for one user."""

    slots: tuple[PvpTeamSlot, ...]

    @property
    def filled_slots(self) -> int:
        return sum(1 for slot in self.slots if slot.entry is not None)

    @property
    def is_complete(self) -> bool:
        return self.filled_slots == PVP_TEAM_SLOT_COUNT


@dataclass(slots=True)
class ProfileReferral:
    """Referral data rendered on the profile screen."""

    referral_code: str
    referral_link: str


@dataclass(slots=True)
class ProfileCoverCandidate:
    """Owned pokemon that can be used as a profile cover."""

    pokemon_id: int
    sample_user_pokemon_id: int
    name: str
    rarity: str
    pokemon_type: Optional[str]
    image_credit_id: int

    def as_session_payload(self) -> dict[str, object]:
        return {
            "pokemon_id": self.pokemon_id,
            "sample_user_pokemon_id": self.sample_user_pokemon_id,
            "name": self.name,
            "rarity": self.rarity,
            "pokemon_type": self.pokemon_type,
            "image_credit_id": self.image_credit_id,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "ProfileCoverCandidate":
        return cls(
            pokemon_id=int(payload["pokemon_id"]),
            sample_user_pokemon_id=int(payload["sample_user_pokemon_id"]),
            name=str(payload["name"]),
            rarity=str(payload["rarity"]),
            pokemon_type=payload.get("pokemon_type"),
            image_credit_id=int(payload["image_credit_id"]),
        )


@dataclass(slots=True)
class PokemonSearchEntry:
    """Catalog pokemon search result."""

    pokemon_id: int
    name: str
    rarity: str
    pokemon_type: Optional[str]
    base_hp: int
    base_attack: int
    base_defense: int
    base_stamina: int
    image_credit_id: Optional[int]
    dex_form_code: Optional[str] = None
    form_badge: Optional[str] = None

    def as_session_payload(self) -> dict[str, object]:
        return {
            "pokemon_id": self.pokemon_id,
            "name": self.name,
            "rarity": self.rarity,
            "pokemon_type": self.pokemon_type,
            "base_hp": self.base_hp,
            "base_attack": self.base_attack,
            "base_defense": self.base_defense,
            "base_stamina": self.base_stamina,
            "image_credit_id": self.image_credit_id,
            "dex_form_code": self.dex_form_code,
            "form_badge": self.form_badge,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "PokemonSearchEntry":
        return cls(
            pokemon_id=int(payload["pokemon_id"]),
            name=str(payload["name"]),
            rarity=str(payload["rarity"]),
            pokemon_type=payload.get("pokemon_type"),
            base_hp=int(payload["base_hp"]),
            base_attack=int(payload["base_attack"]),
            base_defense=int(payload["base_defense"]),
            base_stamina=int(payload["base_stamina"]),
            image_credit_id=payload.get("image_credit_id"),
            dex_form_code=payload.get("dex_form_code"),
            form_badge=payload.get("form_badge"),
        )


@dataclass(slots=True)
class ImageCreditRecord:
    """Stored object metadata for one image asset."""

    image_credit_id: int
    storage_bucket: str
    object_key: str
    content_type: Optional[str]
    source: Optional[str]


@dataclass(slots=True)
class PokemonImageSelection:
    """Resolved image state for one user's view of one pokemon species."""

    pokemon_id: int
    image_credit_id: Optional[int]
    source_url: Optional[str]
    position: int
    total: int

    @property
    def can_switch(self) -> bool:
        return self.total > 1


@dataclass(slots=True)
class UserLookupResult:
    """Resolved Telegram-backed user identity from the bot database."""

    user_id: int
    telegram_id: int
    username: Optional[str]


@dataclass(slots=True)
class AdminAuditRecord:
    """One admin-action audit record for operator views and exports."""

    audit_id: int
    actor_user_id: Optional[int]
    actor_telegram_id: int
    actor_username: Optional[str]
    action_type: str
    target_user_id: Optional[int]
    target_telegram_id: Optional[int]
    target_username: Optional[str]
    status: str
    input_payload: dict[str, object] | None
    result_payload: dict[str, object] | None
    error_message: Optional[str]
    created_at: datetime


@dataclass(slots=True)
class MarketBrowseState:
    """Current browse filters for the market buy screen."""

    rarities: tuple[str, ...] = ()
    affordable_only: bool = False
    sort_mode: str = MARKET_SORT_NEWEST
    query: str = ""
    page: int = 1

    def with_page(self, page: int) -> "MarketBrowseState":
        return MarketBrowseState(
            rarities=self.rarities,
            affordable_only=self.affordable_only,
            sort_mode=self.sort_mode,
            query=self.query,
            page=page,
        )

    def to_session_payload(self) -> dict[str, object]:
        return {
            "rarities": list(self.rarities),
            "affordable_only": self.affordable_only,
            "sort_mode": self.sort_mode,
            "query": self.query,
            "page": self.page,
        }

    @classmethod
    def from_payload(cls, payload: Optional[dict[str, object]]) -> "MarketBrowseState":
        if not payload:
            return cls()
        sort_mode = str(payload.get("sort_mode") or MARKET_SORT_NEWEST)
        if sort_mode not in {MARKET_SORT_NEWEST, MARKET_SORT_CHEAPEST}:
            sort_mode = MARKET_SORT_NEWEST
        return cls(
            rarities=tuple(str(value) for value in payload.get("rarities", []) if value),
            affordable_only=bool(payload.get("affordable_only", False)),
            sort_mode=sort_mode,
            query=str(payload.get("query") or "").strip(),
            page=max(1, int(payload.get("page", 1))),
        )


@dataclass(slots=True)
class MarketListingSummary:
    """Compact sale listing data for browsing and management."""

    listing_id: int
    seller_user_id: int
    seller_label: Optional[str]
    user_pokemon_id: int
    pokemon_id: int
    name: str
    rarity: str
    pokemon_type: Optional[str]
    price: int
    status: str
    listed_at: datetime
    expires_at: datetime
    days_remaining: int
    image_credit_id: Optional[int]
    dex_form_code: Optional[str] = None
    form_badge: Optional[str] = None


@dataclass(slots=True)
class MarketBuyRequestSummary:
    """Compact buy-request data for browsing and management."""

    request_id: int
    requester_user_id: int
    requester_label: Optional[str]
    pokemon_id: int
    name: str
    rarity: str
    pokemon_type: Optional[str]
    price: int
    reserved_amount: int
    status: str
    created_at: datetime
    image_credit_id: Optional[int]
    dex_form_code: Optional[str] = None
    form_badge: Optional[str] = None
    matching_user_pokemon_id: Optional[int] = None


@dataclass(slots=True)
class MarketBrowsePage:
    """Paginated market listings for the buy screen."""

    entries: list[MarketListingSummary]
    filter_state: MarketBrowseState
    total_entries: int
    current_page: int
    total_pages: int
    current_balance: int

    def has_previous(self) -> bool:
        return self.current_page > 1

    def has_next(self) -> bool:
        return self.current_page < self.total_pages


@dataclass(slots=True)
class MarketPurchaseResult:
    """Outcome of buying an active sale listing."""

    listing: MarketListingSummary
    buyer_user_id: int
    seller_user_id: int
    price: int


@dataclass(slots=True)
class MarketRequestFulfillmentResult:
    """Outcome of fulfilling a buy request with an owned pokemon."""

    request: MarketBuyRequestSummary
    seller_user_id: int
    buyer_user_id: int
    transferred_user_pokemon_id: int
    price: int


@dataclass(slots=True)
class PokemonReleaseResult:
    """Outcome of releasing one owned pokemon for pokecoin."""

    user_pokemon_id: int
    pokemon_id: int
    name: str
    rarity: str
    reward_amount: int


@dataclass(slots=True)
class PokemonLockResult:
    """Lock toggle result for one owned pokemon instance."""

    user_pokemon_id: int
    pokemon_id: int
    name: str
    rarity: str
    is_locked: bool


@dataclass(slots=True)
class ChatEncounter:
    """Active or resolved encounter record."""

    encounter_id: int
    chat_id: int
    message_thread_id: Optional[int]
    encounter_message_id: Optional[int]
    pokemon_id: int
    name: str
    rarity: str
    pokemon_type: Optional[str]
    image_credit_id: Optional[int]
    spawned_at: datetime
    expires_at: datetime
    status: str
    caught_by_user_id: Optional[int]
    caught_user_pokemon_id: Optional[int]
    caught_with_item_code: Optional[str]


@dataclass(slots=True)
class ChatEncounterAttemptResult:
    """Result of one user attempt against a chat encounter."""

    status: str
    encounter: Optional[ChatEncounter]
    caught: bool = False
    ball_code: Optional[str] = None
    ball_consumed: bool = False
    catcher_user_id: Optional[int] = None
    catcher_label: Optional[str] = None
    already_attempted: bool = False


@dataclass(slots=True)
class TradeOfferLine:
    """One pokemon currently offered in a trade."""

    user_pokemon_id: int
    pokemon_id: int
    name: str
    rarity: str
    dex_form_code: Optional[str] = None
    form_badge: Optional[str] = None


@dataclass(slots=True)
class TradeParticipantState:
    """Per-user state in one trade session."""

    user_id: int
    telegram_id: int
    username: Optional[str]
    nickname: Optional[str]
    label: str
    is_ready: bool
    offers: list[TradeOfferLine]


@dataclass(slots=True)
class TradeSessionSummary:
    """Shared read model for one pending or active trade."""

    trade_id: int
    chat_id: int
    message_thread_id: Optional[int]
    request_message_id: Optional[int]
    active_message_id: Optional[int]
    status: str
    pending_expires_at: Optional[datetime]
    trade_expires_at: Optional[datetime]
    created_at: datetime
    accepted_at: Optional[datetime]
    canceled_at: Optional[datetime]
    completed_at: Optional[datetime]
    cancel_reason: Optional[str]
    initiator: TradeParticipantState
    target: TradeParticipantState

    @property
    def message_id(self) -> Optional[int]:
        return self.active_message_id or self.request_message_id

    def participant_for_telegram_id(self, telegram_id: int) -> Optional[TradeParticipantState]:
        if self.initiator.telegram_id == telegram_id:
            return self.initiator
        if self.target.telegram_id == telegram_id:
            return self.target
        return None


@dataclass(slots=True)
class TradeReadyToggleResult:
    """Outcome of toggling ready state in an active trade."""

    trade: TradeSessionSummary
    completed: bool = False


@dataclass(slots=True)
class TradeMaintenanceResult:
    """Expired trade projections that should be reflected in Telegram."""

    expired_requests: list[TradeSessionSummary]
    expired_active_trades: list[TradeSessionSummary]


@dataclass(slots=True)
class PvpChallengeParticipant:
    """Per-user state for one PvP challenge."""

    user_id: int
    telegram_id: int
    username: Optional[str]
    nickname: Optional[str]
    label: str
    selected_user_pokemon_id: Optional[int] = None
    selected_name: Optional[str] = None
    selected_rarity: Optional[str] = None
    selected_dex_form_code: Optional[str] = None
    selected_form_badge: Optional[str] = None
    selected_pokemon_type: Optional[str] = None
    selected_base_hp: Optional[int] = None
    selected_base_attack: Optional[int] = None
    selected_base_defense: Optional[int] = None
    selected_base_stamina: Optional[int] = None


@dataclass(slots=True)
class PvpChallengeSummary:
    """Shared read model for one pending or selecting PvP challenge."""

    challenge_id: int
    chat_id: int
    message_thread_id: Optional[int]
    message_id: Optional[int]
    status: str
    pending_expires_at: Optional[datetime]
    selection_expires_at: Optional[datetime]
    created_at: datetime
    accepted_at: Optional[datetime]
    canceled_at: Optional[datetime]
    completed_at: Optional[datetime]
    cancel_reason: Optional[str]
    initiator: PvpChallengeParticipant
    target: PvpChallengeParticipant


@dataclass(slots=True)
class PvpChallengeMaintenanceResult:
    """Expired PvP challenge projections that should be reflected in Telegram."""

    expired_pending_challenges: list[PvpChallengeSummary]
    expired_selecting_challenges: list[PvpChallengeSummary]
    expired_battling_challenges: list[PvpChallengeSummary]


@dataclass(slots=True)
class PvpRewardResolution:
    """Outcome of daily PvP reward accounting for one completed battle."""

    winner_reward_granted: bool
    winner_reward_amount: int
    winner_daily_completed_count: int
    loser_daily_completed_count: int


class Database:
    """Minimal asyncpg pool manager for bot data."""

    def __init__(self, dsn: Optional[str] = None) -> None:
        self.dsn = dsn or os.getenv("DATABASE_URL")
        self.pool: Optional[asyncpg.Pool] = None
        self.redis: Optional[Redis] = None

    async def connect(self) -> None:
        """Create connection pool."""
        if self.pool:
            return

        if self.dsn:
            self.pool = await asyncpg.create_pool(dsn=self.dsn, min_size=1, max_size=10)
        else:
            self.pool = await asyncpg.create_pool(
                host=os.getenv("DB_HOST", "127.0.0.1"),
                port=int(os.getenv("DB_PORT", "5432")),
                database=_required_env("DB_NAME"),
                user=_required_env("DB_USER"),
                password=_required_env("DB_PASSWORD"),
                min_size=1,
                max_size=10,
            )

        if os.getenv("REDIS_ENABLED", "false").lower() == "true":
            redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
            try:
                self.redis = Redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=1,
                    socket_timeout=1,
                    health_check_interval=30,
                )
                await asyncio.to_thread(self.redis.ping)
                logger.info("db_redis_ready", redis_url=redis_url)
            except RedisError as exc:
                self.redis = None
                logger.warning("db_redis_unavailable", redis_url=redis_url, error=str(exc))

        logger.info("db_connected")

    async def close(self) -> None:
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
        if self.redis is not None:
            try:
                self.redis.close()
            except RedisError:
                pass
            self.redis = None
        logger.info("db_closed")

    async def probe(self) -> dict[str, bool]:
        """Perform lightweight dependency probes for runtime health checks."""
        db_ok = False
        redis_ok = self.redis is None

        if self.pool is not None:
            try:
                db_ok = (await self.pool.fetchval("SELECT 1")) == 1
            except Exception:
                db_ok = False

        if self.redis is not None:
            try:
                redis_ok = bool(await asyncio.to_thread(self.redis.ping))
            except RedisError:
                redis_ok = False

        return {"db_ok": db_ok, "redis_ok": redis_ok}

    async def init_schema(self, schema_path: str = "sql/schema.sql") -> None:
        """Apply SQL schema from file."""
        self._ensure_pool()
        sql_text = Path(schema_path).read_text(encoding="utf-8")
        async with self.pool.acquire() as conn:
            await conn.execute(sql_text)
        logger.info("db_schema_applied", schema_path=schema_path)

    async def get_or_create_user(self, telegram_id: int, username: Optional[str]) -> int:
        """Create/update user by telegram_id and return internal id."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
        return user_id

    async def get_or_create_user_status(self, telegram_id: int, username: Optional[str]) -> tuple[int, bool]:
        """Create/update user by telegram_id and return internal id plus whether it was a new user."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                existed = bool(await conn.fetchval("SELECT 1 FROM users WHERE tg_user_id = $1", telegram_id))
                user_id = await self._ensure_user(conn, telegram_id, username)
        return user_id, (not existed)

    async def consume_start_guide_flag(self, telegram_id: int, username: Optional[str]) -> bool:
        """Return True once per user when the start guide should be shown."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                already_seen = await conn.fetchval(
                    "SELECT start_guide_seen_at IS NOT NULL FROM users WHERE id = $1",
                    user_id,
                )
                if already_seen:
                    return False
                await conn.execute(
                    "UPDATE users SET start_guide_seen_at = NOW() WHERE id = $1",
                    user_id,
                )
                return True

    async def get_shop_view(self, telegram_id: int, username: Optional[str]) -> ShopView:
        """Load shop data for the current user."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                return await self._fetch_shop_view(conn, user_id)

    async def get_collection_page(
        self,
        telegram_id: int,
        username: Optional[str],
        filter_state: Optional[CollectionFilterState] = None,
    ) -> CollectionPage:
        """Load a paginated collection view for the current user."""
        self._ensure_pool()
        requested_state = filter_state or CollectionFilterState()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                return await self._fetch_collection_page(conn, user_id, requested_state)

    async def get_mini_app_collection_page(
        self,
        telegram_id: int,
        username: Optional[str],
        filter_state: Optional[CollectionFilterState] = None,
        *,
        page_size: int,
    ) -> MiniAppCollectionPage:
        """Load a Mini App collection page with custom page sizing."""
        self._ensure_pool()
        requested_state = filter_state or CollectionFilterState()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                return await self._fetch_collection_page_with_page_size(
                    conn,
                    user_id,
                    requested_state,
                    page_size=page_size,
                )

    async def get_mini_app_pokedex_page(
        self,
        telegram_id: int,
        username: Optional[str],
        filter_state: Optional[PokedexFilterState] = None,
        *,
        page_size: int,
    ) -> MiniAppPokedexPage:
        """Load one Mini App pokedex page across the full catalog."""
        self._ensure_pool()
        requested_state = filter_state or PokedexFilterState()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                return await self._fetch_pokedex_page_with_page_size(
                    conn,
                    user_id,
                    requested_state,
                    page_size=page_size,
                )

    async def get_pokedex_detail(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        pokemon_id: int,
    ) -> PokedexDetail:
        """Load one read-only pokedex detail entry for the current user."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                return await self._fetch_pokedex_detail(conn, user_id, pokemon_id=pokemon_id)

    async def get_profile_summary(self, telegram_id: int, username: Optional[str]) -> ProfileSummary:
        """Load the profile summary for the current user."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._ensure_user(conn, telegram_id, username)
                user_id = await self._get_user_id_by_telegram_id(conn, telegram_id)
                return await self._fetch_profile_summary_by_user_id(conn, user_id)

    async def get_profile_summary_by_telegram_id(self, telegram_id: int) -> ProfileSummary:
        """Load an existing profile summary by Telegram user id without creating a new user."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await conn.fetchval("SELECT id FROM users WHERE tg_user_id = $1", telegram_id)
                if user_id is None:
                    raise ShopError("Профиль этого пользователя ещё недоступен.")
                return await self._fetch_profile_summary_by_user_id(conn, int(user_id))

    async def get_profile_summary_by_username(self, username: str) -> ProfileSummary:
        """Load an existing profile summary by stored Telegram username."""
        normalized = username.strip().lstrip("@").lower()
        if not normalized:
            raise ShopError("Укажите username после /profile.")

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await conn.fetchval(
                    "SELECT id FROM users WHERE lower(tg_username) = $1",
                    normalized,
                )
                if user_id is None:
                    raise ShopError("Я пока не знаю этого пользователя. Он должен хотя бы раз воспользоваться ботом.")
                return await self._fetch_profile_summary_by_user_id(conn, int(user_id))

    async def get_pvp_team(self, telegram_id: int, username: Optional[str]) -> PvpTeam:
        """Load the current user's persistent PvP team."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._ensure_user(conn, telegram_id, username)
                user_id = await self._get_user_id_by_telegram_id(conn, telegram_id)
                await self._cleanup_invalid_pvp_team_slots(conn, user_id)
                return await self._fetch_pvp_team(conn, user_id)

    async def set_pvp_team_slot(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        slot_index: int,
        user_pokemon_id: Optional[int],
    ) -> PvpTeam:
        """Assign or clear one PvP team slot for the current user."""
        if slot_index < 1 or slot_index > PVP_TEAM_SLOT_COUNT:
            raise ShopError(f"Слот команды должен быть от 1 до {PVP_TEAM_SLOT_COUNT}.")

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._ensure_user(conn, telegram_id, username)
                user_id = await self._get_user_id_by_telegram_id(conn, telegram_id)
                await self._cleanup_invalid_pvp_team_slots(conn, user_id)

                if user_pokemon_id is None:
                    await conn.execute(
                        """
                        DELETE FROM user_pvp_team_slots
                        WHERE user_id = $1
                          AND slot_index = $2
                        """,
                        user_id,
                        slot_index,
                    )
                    return await self._fetch_pvp_team(conn, user_id)

                pokemon_row = await conn.fetchrow(
                    """
                    SELECT id, owner_user_id, released_at
                    FROM user_pokemon
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    user_pokemon_id,
                )
                if not pokemon_row or int(pokemon_row["owner_user_id"]) != user_id:
                    raise ShopError("Этот экземпляр покемона вам не принадлежит.")
                if pokemon_row["released_at"] is not None:
                    raise ShopError("Нельзя добавить в команду отпущенного покемона.")

                duplicate_slot = await conn.fetchval(
                    """
                    SELECT slot_index
                    FROM user_pvp_team_slots
                    WHERE user_id = $1
                      AND user_pokemon_id = $2
                      AND slot_index <> $3
                    LIMIT 1
                    """,
                    user_id,
                    user_pokemon_id,
                    slot_index,
                )
                if duplicate_slot is not None:
                    raise ShopError("Этот покемон уже стоит в другом слоте боевой команды.")

                active_listing = await conn.fetchval(
                    """
                    SELECT 1
                    FROM market_listings
                    WHERE pokemon_instance_id = $1
                      AND status = $2
                    LIMIT 1
                    """,
                    user_pokemon_id,
                    MARKET_LISTING_STATUS_ACTIVE,
                )
                if active_listing:
                    raise ShopError("Сначала снимите этого покемона с рынка.")

                active_trade_offer = await conn.fetchval(
                    """
                    SELECT 1
                    FROM trade_offer_items toi
                    JOIN trade_sessions ts ON ts.id = toi.trade_id
                    WHERE toi.user_pokemon_id = $1
                      AND ts.status = $2
                    LIMIT 1
                    """,
                    user_pokemon_id,
                    TRADE_STATUS_ACTIVE,
                )
                if active_trade_offer:
                    raise ShopError("Сначала уберите этого покемона из активного обмена.")

                await conn.execute(
                    """
                    INSERT INTO user_pvp_team_slots (
                        user_id,
                        slot_index,
                        user_pokemon_id
                    )
                    VALUES ($1, $2, $3)
                    ON CONFLICT (user_id, slot_index)
                    DO UPDATE
                    SET user_pokemon_id = EXCLUDED.user_pokemon_id,
                        updated_at = NOW()
                    """,
                    user_id,
                    slot_index,
                    user_pokemon_id,
                )
                return await self._fetch_pvp_team(conn, user_id)

    async def is_user_pokemon_in_pvp_team(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        user_pokemon_id: int,
    ) -> bool:
        """Return whether one owned pokemon instance is currently in the user's PvP team."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                return await self._is_user_pokemon_in_pvp_team(
                    conn,
                    user_id=user_id,
                    user_pokemon_id=user_pokemon_id,
                )

    async def create_pvp_challenge(
        self,
        *,
        initiator_telegram_id: int,
        initiator_username: Optional[str],
        target_telegram_id: int,
        target_username: Optional[str],
        chat_id: int,
        message_thread_id: Optional[int],
    ) -> PvpChallengeSummary:
        """Create a pending PvP challenge between two users."""
        if initiator_telegram_id == target_telegram_id:
            raise ShopError("Нельзя вызвать самого себя на бой.")

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                initiator_user_id = await self._ensure_user(conn, initiator_telegram_id, initiator_username)
                target_user_id = await self._ensure_user(conn, target_telegram_id, target_username)
                await self._cleanup_invalid_pvp_team_slots(conn, initiator_user_id)
                await self._cleanup_invalid_pvp_team_slots(conn, target_user_id)
                await self._ensure_user_has_complete_pvp_team(
                    conn,
                    user_id=initiator_user_id,
                    own_message="Сначала заполните свою боевую команду в профиле.",
                )
                await self._ensure_user_has_complete_pvp_team(
                    conn,
                    user_id=target_user_id,
                    own_message="У второго игрока пока не заполнена боевая команда.",
                )
                await self._ensure_pvp_initiator_available(conn, initiator_user_id)
                await self._ensure_pvp_user_not_selecting(conn, initiator_user_id, own_message="У вас уже идёт другой бой или выбор бойца.")
                await self._ensure_pvp_user_not_selecting(conn, target_user_id, own_message="Этот пользователь уже участвует в другом бою.")
                inserted = await conn.fetchrow(
                    """
                    INSERT INTO pvp_challenges (
                      chat_id,
                      message_thread_id,
                      initiator_user_id,
                      target_user_id,
                      status,
                      pending_expires_at
                    )
                    VALUES (
                      $1,
                      $2,
                      $3,
                      $4,
                      $5,
                      NOW() + make_interval(secs => $6)
                    )
                    RETURNING id
                    """,
                    chat_id,
                    message_thread_id,
                    initiator_user_id,
                    target_user_id,
                    PVP_CHALLENGE_STATUS_PENDING,
                    PVP_CHALLENGE_PENDING_TTL_SECONDS,
                )
                challenge = await self._fetch_pvp_challenge_summary(conn, int(inserted["id"]))
        logger.info(
            "pvp_challenge_created",
            challenge_id=challenge.challenge_id,
            initiator_telegram_id=initiator_telegram_id,
            target_telegram_id=target_telegram_id,
            chat_id=chat_id,
        )
        return challenge

    async def attach_pvp_challenge_message(self, challenge_id: int, message_id: int) -> None:
        """Persist Telegram message id for one PvP challenge."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE pvp_challenges
                SET message_id = $2
                WHERE id = $1
                """,
                challenge_id,
                message_id,
            )

    async def accept_pvp_challenge(self, challenge_id: int, actor_telegram_id: int) -> PvpChallengeSummary:
        """Accept a pending PvP challenge as the challenged user."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                actor_user_id = await self._get_user_id_by_telegram_id(conn, actor_telegram_id)
                row = await conn.fetchrow(
                    """
                    SELECT *
                    FROM pvp_challenges
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    challenge_id,
                )
                if not row:
                    raise ShopError("Вызов на бой не найден.")
                if str(row["status"]) != PVP_CHALLENGE_STATUS_PENDING:
                    raise ShopError("Этот вызов уже не активен.")
                if int(row["target_user_id"]) != actor_user_id:
                    raise ShopError("Только второй игрок может принять этот вызов.")
                if row["pending_expires_at"] is not None and _normalize_timestamp(row["pending_expires_at"]) <= datetime.now(UTC):
                    await self._close_pvp_challenge(conn, challenge_id, status=PVP_CHALLENGE_STATUS_EXPIRED, cancel_reason="request_expired")
                    raise ShopError("Вызов на бой уже истёк.")
                initiator_user_id = int(row["initiator_user_id"])
                target_user_id = int(row["target_user_id"])
                await self._cleanup_invalid_pvp_team_slots(conn, initiator_user_id)
                await self._cleanup_invalid_pvp_team_slots(conn, target_user_id)
                await self._ensure_user_has_complete_pvp_team(
                    conn,
                    user_id=initiator_user_id,
                    own_message="У первого игрока больше нет полной боевой команды.",
                )
                await self._ensure_user_has_complete_pvp_team(
                    conn,
                    user_id=target_user_id,
                    own_message="Сначала заполните свою боевую команду в профиле.",
                )
                await self._ensure_pvp_user_not_selecting(conn, initiator_user_id, own_message="У первого игрока уже идёт другой бой.")
                await self._ensure_pvp_user_not_selecting(conn, target_user_id, own_message="У вас уже идёт другой бой.")
                await conn.execute(
                    """
                    UPDATE pvp_challenges
                    SET status = $2,
                        accepted_at = NOW(),
                        selection_expires_at = NOW() + make_interval(secs => $3)
                    WHERE id = $1
                    """,
                    challenge_id,
                    PVP_CHALLENGE_STATUS_SELECTING_INITIATOR,
                    PVP_CHALLENGE_SELECTION_TTL_SECONDS,
                )
                challenge = await self._fetch_pvp_challenge_summary(conn, challenge_id)
        logger.info("pvp_challenge_accepted", challenge_id=challenge_id, actor_telegram_id=actor_telegram_id)
        return challenge

    async def cancel_pvp_challenge(
        self,
        challenge_id: int,
        actor_telegram_id: int,
        *,
        cancel_reason: str = "canceled",
    ) -> PvpChallengeSummary:
        """Cancel a pending or selecting PvP challenge as one of its participants."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                actor_user_id = await self._get_user_id_by_telegram_id(conn, actor_telegram_id)
                challenge = await self._fetch_pvp_challenge_summary(conn, challenge_id)
                if actor_user_id not in {challenge.initiator.user_id, challenge.target.user_id}:
                    raise ShopError("Нельзя отменить чужой бой.")
                if challenge.status not in {
                    PVP_CHALLENGE_STATUS_PENDING,
                    PVP_CHALLENGE_STATUS_SELECTING_INITIATOR,
                    PVP_CHALLENGE_STATUS_SELECTING_TARGET,
                }:
                    raise ShopError("Этот вызов уже не активен.")
                await self._close_pvp_challenge(conn, challenge_id, status=PVP_CHALLENGE_STATUS_CANCELED, cancel_reason=cancel_reason)
                closed = await self._fetch_pvp_challenge_summary(conn, challenge_id)
        logger.info("pvp_challenge_canceled", challenge_id=challenge_id, actor_telegram_id=actor_telegram_id, cancel_reason=cancel_reason)
        return closed

    async def select_pvp_challenge_fighter(
        self,
        *,
        challenge_id: int,
        telegram_id: int,
        username: Optional[str],
        user_pokemon_id: int,
    ) -> tuple[PvpChallengeSummary, bool]:
        """Select one fighter from the participant's PvP team.

        Returns (challenge, battle_ready).
        """
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._ensure_user(conn, telegram_id, username)
                actor_user_id = await self._get_user_id_by_telegram_id(conn, telegram_id)
                row = await conn.fetchrow(
                    """
                    SELECT *
                    FROM pvp_challenges
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    challenge_id,
                )
                if not row:
                    raise ShopError("Вызов на бой не найден.")
                status = str(row["status"])
                if status not in {PVP_CHALLENGE_STATUS_SELECTING_INITIATOR, PVP_CHALLENGE_STATUS_SELECTING_TARGET}:
                    raise ShopError("Сейчас нельзя выбрать бойца для этого боя.")
                if row["selection_expires_at"] is not None and _normalize_timestamp(row["selection_expires_at"]) <= datetime.now(UTC):
                    await self._close_pvp_challenge(conn, challenge_id, status=PVP_CHALLENGE_STATUS_EXPIRED, cancel_reason="selection_expired")
                    raise ShopError("Время на выбор бойца истекло.")

                chooser_user_id = int(row["initiator_user_id"]) if status == PVP_CHALLENGE_STATUS_SELECTING_INITIATOR else int(row["target_user_id"])
                if actor_user_id != chooser_user_id:
                    raise ShopError("Сейчас выбирает бойца другой игрок.")
                await self._cleanup_invalid_pvp_team_slots(conn, actor_user_id)
                await self._ensure_user_has_complete_pvp_team(conn, user_id=actor_user_id, own_message="Команда больше не заполнена полностью.")
                if not await self._is_user_pokemon_in_pvp_team(conn, user_id=actor_user_id, user_pokemon_id=user_pokemon_id):
                    raise ShopError("Можно выбрать только покемона из своей боевой команды.")

                pokemon_row = await conn.fetchrow(
                    """
                    SELECT owner_user_id, released_at
                    FROM user_pokemon
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    user_pokemon_id,
                )
                if not pokemon_row or int(pokemon_row["owner_user_id"]) != actor_user_id or pokemon_row["released_at"] is not None:
                    raise ShopError("Этот покемон больше недоступен для боя.")

                battle_ready = status == PVP_CHALLENGE_STATUS_SELECTING_TARGET
                if status == PVP_CHALLENGE_STATUS_SELECTING_INITIATOR:
                    await conn.execute(
                        """
                        UPDATE pvp_challenges
                        SET initiator_selected_user_pokemon_id = $2,
                            status = $3
                        WHERE id = $1
                        """,
                        challenge_id,
                        user_pokemon_id,
                        PVP_CHALLENGE_STATUS_SELECTING_TARGET,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE pvp_challenges
                        SET target_selected_user_pokemon_id = $2,
                            status = $3
                        WHERE id = $1
                        """,
                        challenge_id,
                        user_pokemon_id,
                        PVP_CHALLENGE_STATUS_BATTLING,
                    )
                challenge = await self._fetch_pvp_challenge_summary(conn, challenge_id)
        logger.info(
            "pvp_challenge_fighter_selected",
            challenge_id=challenge_id,
            telegram_id=telegram_id,
            user_pokemon_id=user_pokemon_id,
            battle_ready=battle_ready,
        )
        return challenge, battle_ready

    async def get_pvp_team_selection_options(self, telegram_id: int, username: Optional[str]) -> tuple[CollectionEntry, ...]:
        """Return the ordered five team members usable for one PvP selection step."""
        team = await self.get_pvp_team(telegram_id, username)
        if not team.is_complete:
            raise ShopError("Боевая команда должна быть заполнена полностью.")
        return tuple(slot.entry for slot in team.slots if slot.entry is not None)

    async def get_remaining_pvp_reward_battles(self, telegram_id: int, username: Optional[str]) -> int:
        """Return how many rewarded PvP battles remain for the user today."""
        self._ensure_pool()
        today = datetime.now(UTC).date()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._ensure_user(conn, telegram_id, username)
                user_id = await self._get_user_id_by_telegram_id(conn, telegram_id)
                rewarded_count = await conn.fetchval(
                    """
                    SELECT rewarded_battle_count
                    FROM user_pvp_daily_rewards
                    WHERE user_id = $1
                      AND reward_date = $2
                    """,
                    user_id,
                    today,
                )
        return max(0, PVP_DAILY_REWARD_LIMIT - int(rewarded_count or 0))

    async def complete_pvp_challenge(self, challenge_id: int) -> PvpChallengeSummary:
        """Mark one active PvP challenge as completed and return the final summary."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT status
                    FROM pvp_challenges
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    challenge_id,
                )
                if not row:
                    raise ShopError("Бой не найден.")
                if str(row["status"]) != PVP_CHALLENGE_STATUS_BATTLING:
                    raise ShopError("Этот бой уже не активен.")
                await self._close_pvp_challenge(
                    conn,
                    challenge_id,
                    status=PVP_CHALLENGE_STATUS_COMPLETED,
                    cancel_reason=None,
                )
                return await self._fetch_pvp_challenge_summary(conn, challenge_id)

    async def abort_pvp_challenge(self, challenge_id: int, *, cancel_reason: str) -> PvpChallengeSummary:
        """Force-close one active PvP challenge after runtime failure."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT status
                    FROM pvp_challenges
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    challenge_id,
                )
                if not row:
                    raise ShopError("Бой не найден.")
                if str(row["status"]) not in {
                    PVP_CHALLENGE_STATUS_PENDING,
                    PVP_CHALLENGE_STATUS_SELECTING_INITIATOR,
                    PVP_CHALLENGE_STATUS_SELECTING_TARGET,
                    PVP_CHALLENGE_STATUS_BATTLING,
                }:
                    raise ShopError("Этот бой уже не активен.")
                await self._close_pvp_challenge(
                    conn,
                    challenge_id,
                    status=PVP_CHALLENGE_STATUS_CANCELED,
                    cancel_reason=cancel_reason,
                )
                return await self._fetch_pvp_challenge_summary(conn, challenge_id)

    async def settle_pvp_battle_rewards(
        self,
        *,
        winner_telegram_id: int,
        winner_username: Optional[str],
        loser_telegram_id: int,
        loser_username: Optional[str],
    ) -> PvpRewardResolution:
        """Apply daily PvP reward accounting and winner payout."""
        self._ensure_pool()
        today = datetime.now(UTC).date()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                winner_user_id = await self._ensure_user(conn, winner_telegram_id, winner_username)
                loser_user_id = await self._ensure_user(conn, loser_telegram_id, loser_username)

                winner_before = await conn.fetchval(
                    """
                    SELECT rewarded_battle_count
                    FROM user_pvp_daily_rewards
                    WHERE user_id = $1
                      AND reward_date = $2
                    """,
                    winner_user_id,
                    today,
                )
                loser_before = await conn.fetchval(
                    """
                    SELECT rewarded_battle_count
                    FROM user_pvp_daily_rewards
                    WHERE user_id = $1
                      AND reward_date = $2
                    """,
                    loser_user_id,
                    today,
                )
                winner_before_int = int(winner_before or 0)
                loser_before_int = int(loser_before or 0)
                winner_after = min(PVP_DAILY_REWARD_LIMIT, winner_before_int + 1)
                loser_after = min(PVP_DAILY_REWARD_LIMIT, loser_before_int + 1)

                await conn.execute(
                    """
                    INSERT INTO user_pvp_daily_rewards (user_id, reward_date, rewarded_battle_count)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (user_id, reward_date)
                    DO UPDATE
                    SET rewarded_battle_count = $3,
                        updated_at = NOW()
                    """,
                    winner_user_id,
                    today,
                    winner_after,
                )
                await conn.execute(
                    """
                    INSERT INTO user_pvp_daily_rewards (user_id, reward_date, rewarded_battle_count)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (user_id, reward_date)
                    DO UPDATE
                    SET rewarded_battle_count = $3,
                        updated_at = NOW()
                    """,
                    loser_user_id,
                    today,
                    loser_after,
                )

                reward_granted = winner_before_int < PVP_DAILY_REWARD_LIMIT
                if reward_granted:
                    await self._ensure_user_balance(conn, winner_user_id, POKEDOLLAR_CODE)
                    await self._adjust_balance(conn, winner_user_id, POKEDOLLAR_CODE, PVP_WIN_REWARD_POKEDOLLAR)

        return PvpRewardResolution(
            winner_reward_granted=reward_granted,
            winner_reward_amount=PVP_WIN_REWARD_POKEDOLLAR if reward_granted else 0,
            winner_daily_completed_count=winner_after,
            loser_daily_completed_count=loser_after,
        )

    async def process_pvp_challenge_maintenance(self) -> PvpChallengeMaintenanceResult:
        """Expire stale pending/selecting/battling PvP challenges and return affected projections."""
        self._ensure_pool()
        expired_pending: list[PvpChallengeSummary] = []
        expired_selecting: list[PvpChallengeSummary] = []
        expired_battling: list[PvpChallengeSummary] = []

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                pending_rows = await conn.fetch(
                    """
                    SELECT id
                    FROM pvp_challenges
                    WHERE status = $1
                      AND pending_expires_at <= NOW()
                    FOR UPDATE
                    """,
                    PVP_CHALLENGE_STATUS_PENDING,
                )
                for row in pending_rows:
                    challenge_id = int(row["id"])
                    expired_pending.append(await self._fetch_pvp_challenge_summary(conn, challenge_id))
                    await self._close_pvp_challenge(
                        conn,
                        challenge_id,
                        status=PVP_CHALLENGE_STATUS_EXPIRED,
                        cancel_reason="request_expired",
                    )

                selecting_rows = await conn.fetch(
                    """
                    SELECT id
                    FROM pvp_challenges
                    WHERE status IN ($1, $2)
                      AND selection_expires_at <= NOW()
                    FOR UPDATE
                    """,
                    PVP_CHALLENGE_STATUS_SELECTING_INITIATOR,
                    PVP_CHALLENGE_STATUS_SELECTING_TARGET,
                )
                for row in selecting_rows:
                    challenge_id = int(row["id"])
                    expired_selecting.append(await self._fetch_pvp_challenge_summary(conn, challenge_id))
                    await self._close_pvp_challenge(
                        conn,
                        challenge_id,
                        status=PVP_CHALLENGE_STATUS_EXPIRED,
                        cancel_reason="selection_expired",
                    )

                battling_rows = await conn.fetch(
                    """
                    SELECT id
                    FROM pvp_challenges
                    WHERE status = $1
                      AND selection_expires_at <= NOW()
                    FOR UPDATE
                    """,
                    PVP_CHALLENGE_STATUS_BATTLING,
                )
                for row in battling_rows:
                    challenge_id = int(row["id"])
                    expired_battling.append(await self._fetch_pvp_challenge_summary(conn, challenge_id))
                    await self._close_pvp_challenge(
                        conn,
                        challenge_id,
                        status=PVP_CHALLENGE_STATUS_EXPIRED,
                        cancel_reason="battle_expired",
                    )

        return PvpChallengeMaintenanceResult(
            expired_pending_challenges=expired_pending,
            expired_selecting_challenges=expired_selecting,
            expired_battling_challenges=expired_battling,
        )

    async def get_user_lookup_by_username(self, username: str) -> UserLookupResult:
        """Resolve an existing user by stored Telegram username."""
        normalized = username.strip().lstrip("@").lower()
        if not normalized:
            raise ShopError("Укажите username пользователя.")

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, tg_user_id, tg_username
                FROM users
                WHERE lower(tg_username) = $1
                """,
                normalized,
            )
        if row is None:
            raise ShopError("Я пока не знаю этого пользователя. Он должен хотя бы раз воспользоваться ботом.")
        return UserLookupResult(
            user_id=int(row["id"]),
            telegram_id=int(row["tg_user_id"]),
            username=row["tg_username"],
        )

    async def get_pokemon_catalog_entry_by_id(self, pokemon_id: int) -> PokemonSearchEntry:
        """Load one catalog pokemon by id for admin and Mini App operations."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, dex_form_code, name, type, rarity, base_hp, base_attack, base_defense, base_stamina, image_credit_id
                FROM pokemon_catalog
                WHERE id = $1
                """,
                pokemon_id,
            )
        if row is None:
            raise ShopError("Покемон с таким id не найден.")
        return PokemonSearchEntry(
            pokemon_id=int(row["id"]),
            name=str(row["name"]),
            rarity=str(row["rarity"]),
            pokemon_type=row["type"],
            base_hp=int(row["base_hp"]),
            base_attack=int(row["base_attack"]),
            base_defense=int(row["base_defense"]),
            base_stamina=int(row["base_stamina"]),
            image_credit_id=row["image_credit_id"],
            dex_form_code=row["dex_form_code"],
            form_badge=_form_badge_from_dex_form_code(row["dex_form_code"]),
        )

    async def admin_grant_currency(self, *, target_user_id: int, currency_code: str, amount: int) -> int:
        """Grant currency to a known user."""
        normalized_code = currency_code.strip().lower()
        if normalized_code not in {POKEDOLLAR_CODE, POKECOIN_CODE}:
            raise ShopError("Неподдерживаемая валюта для выдачи.")
        if amount <= 0:
            raise ShopError("Сумма должна быть больше нуля.")

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._ensure_user_balance(conn, target_user_id, normalized_code)
                await self._adjust_balance(conn, target_user_id, normalized_code, amount)
                balance = await self._get_balance_for_update(conn, target_user_id, normalized_code)
        logger.info(
            "admin_currency_granted",
            target_user_id=target_user_id,
            currency_code=normalized_code,
            amount=amount,
            balance=balance,
        )
        return balance

    async def admin_grant_pokemon(self, *, target_user_id: int, pokemon_id: int) -> int:
        """Grant one pokemon species to a known user and return new instance id."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                exists = await conn.fetchval("SELECT 1 FROM pokemon_catalog WHERE id = $1", pokemon_id)
                if not exists:
                    raise ShopError("Покемон с таким id не найден.")
                user_pokemon_id = await self._grant_pokemon_by_id(conn, target_user_id, pokemon_id)
        logger.info(
            "admin_pokemon_granted",
            target_user_id=target_user_id,
            pokemon_id=pokemon_id,
            user_pokemon_id=user_pokemon_id,
        )
        return user_pokemon_id

    async def admin_create_pokemon_species(
        self,
        *,
        pokemon_id: int,
        name: str,
        pokemon_type: Optional[str],
        rarity: str,
        base_hp: int,
        base_attack: int,
        base_defense: int,
        base_stamina: int,
    ) -> int:
        """Create a new catalog pokemon with the full field set."""
        normalized_name = name.strip()
        normalized_type = pokemon_type.strip() if isinstance(pokemon_type, str) else None
        normalized_type = normalized_type or None
        normalized_rarity = rarity.strip()

        if pokemon_id <= 0:
            raise ShopError("pokemon_id должен быть больше нуля.")
        if not normalized_name:
            raise ShopError("Имя покемона не может быть пустым.")
        if not normalized_rarity:
            raise ShopError("Редкость не может быть пустой.")
        numeric_fields = {
            "base_hp": base_hp,
            "base_attack": base_attack,
            "base_defense": base_defense,
            "base_stamina": base_stamina,
        }
        for field_name, value in numeric_fields.items():
            if value < 0:
                raise ShopError(f"{field_name} не может быть отрицательным.")

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                existing_id = await conn.fetchval(
                    "SELECT 1 FROM pokemon_catalog WHERE id = $1",
                    pokemon_id,
                )
                if existing_id:
                    raise ShopError("Покемон с таким id уже существует.")
                existing_name = await conn.fetchval(
                    "SELECT 1 FROM pokemon_catalog WHERE lower(name) = lower($1)",
                    normalized_name,
                )
                if existing_name:
                    raise ShopError("Покемон с таким именем уже существует.")
                created_id = await conn.fetchval(
                    """
                    INSERT INTO pokemon_catalog (
                        id,
                        dex_form_code,
                        name,
                        type,
                        rarity,
                        base_hp,
                        base_attack,
                        base_defense,
                        base_stamina
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    RETURNING id
                    """,
                    pokemon_id,
                    _build_base_dex_form_code(pokemon_id),
                    normalized_name,
                    normalized_type,
                    normalized_rarity,
                    base_hp,
                    base_attack,
                    base_defense,
                    base_stamina,
                )
        logger.info(
            "admin_pokemon_species_created",
            pokemon_id=created_id,
            name=normalized_name,
            rarity=normalized_rarity,
        )
        return int(created_id)

    async def get_next_catalog_pokemon_id(self) -> int:
        """Return the next free internal catalog id."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            next_id = await conn.fetchval("SELECT COALESCE(MAX(id), 0) + 1 FROM pokemon_catalog")
        return int(next_id)

    async def admin_create_pokemon_form(
        self,
        *,
        pokemon_id: int,
        base_pokemon_id: int,
        form_kind: str,
        pokemon_type: Optional[str],
        rarity: str,
        base_hp: int,
        base_attack: int,
        base_defense: int,
        base_stamina: int,
    ) -> int:
        """Create a new catalog form bound to one existing base species."""
        normalized_type = pokemon_type.strip() if isinstance(pokemon_type, str) else None
        normalized_type = normalized_type or None
        normalized_rarity = rarity.strip()
        normalized_form_kind = form_kind.strip().lower()

        if pokemon_id <= 0:
            raise ShopError("pokemon_id должен быть больше нуля.")
        if base_pokemon_id <= 0:
            raise ShopError("base_pokemon_id должен быть больше нуля.")
        if normalized_form_kind not in FORM_SUFFIX_MAP:
            raise ShopError("Форма должна быть одной из: shiny, mega, gigantamax.")
        if not normalized_rarity:
            raise ShopError("Редкость не может быть пустой.")
        numeric_fields = {
            "base_hp": base_hp,
            "base_attack": base_attack,
            "base_defense": base_defense,
            "base_stamina": base_stamina,
        }
        for field_name, value in numeric_fields.items():
            if value < 0:
                raise ShopError(f"{field_name} не может быть отрицательным.")

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                existing_id = await conn.fetchval(
                    "SELECT 1 FROM pokemon_catalog WHERE id = $1",
                    pokemon_id,
                )
                if existing_id:
                    raise ShopError("Покемон с таким id уже существует.")

                base_row = await conn.fetchrow(
                    """
                    SELECT id, name, dex_form_code
                    FROM pokemon_catalog
                    WHERE id = $1
                    """,
                    base_pokemon_id,
                )
                if base_row is None:
                    raise ShopError("Базовый покемон с таким id не найден.")

                base_form_code = _base_dex_from_form_code(base_row["dex_form_code"]) or str(base_row["id"])
                if base_row["dex_form_code"] and "-" in str(base_row["dex_form_code"]):
                    raise ShopError("Нужно привязывать форму именно к базовому виду, а не к другой форме.")

                dex_form_code = f"{base_form_code}-{FORM_SUFFIX_MAP[normalized_form_kind]}"
                existing_form_code = await conn.fetchval(
                    "SELECT 1 FROM pokemon_catalog WHERE dex_form_code = $1",
                    dex_form_code,
                )
                if existing_form_code:
                    raise ShopError("Форма с таким dex_form_code уже существует.")

                created_id = await conn.fetchval(
                    """
                    INSERT INTO pokemon_catalog (
                        id,
                        dex_form_code,
                        name,
                        type,
                        rarity,
                        base_hp,
                        base_attack,
                        base_defense,
                        base_stamina
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    RETURNING id
                    """,
                    pokemon_id,
                    dex_form_code,
                    str(base_row["name"]),
                    normalized_type,
                    normalized_rarity,
                    base_hp,
                    base_attack,
                    base_defense,
                    base_stamina,
                )
        logger.info(
            "admin_pokemon_form_created",
            pokemon_id=created_id,
            base_pokemon_id=base_pokemon_id,
            form_kind=normalized_form_kind,
        )
        return int(created_id)

    async def admin_update_pokemon_species_field(
        self,
        *,
        pokemon_id: int,
        field_key: str,
        new_value: object,
    ) -> PokemonSearchEntry:
        """Update one supported field on an existing pokemon species and return the refreshed row."""
        field_map = {
            "name": "name",
            "pokemon_type": "type",
            "rarity": "rarity",
            "base_hp": "base_hp",
            "base_attack": "base_attack",
            "base_defense": "base_defense",
            "base_stamina": "base_stamina",
        }
        column_name = field_map.get(field_key)
        if column_name is None:
            raise ShopError("Это поле нельзя редактировать через админ-бота.")

        if field_key == "name":
            prepared_value = str(new_value).strip()
            if not prepared_value:
                raise ShopError("Имя покемона не может быть пустым.")
        elif field_key == "pokemon_type":
            normalized_type = str(new_value).strip() if isinstance(new_value, str) else None
            prepared_value = normalized_type or None
        elif field_key == "rarity":
            prepared_value = str(new_value).strip()
            if prepared_value not in {"Common", "Rare", "Epic", "Legendary"}:
                raise ShopError("Редкость должна быть одной из: Common, Rare, Epic, Legendary.")
        else:
            prepared_value = int(new_value)
            if prepared_value < 0:
                raise ShopError(f"{field_key} не может быть отрицательным.")

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                exists = await conn.fetchval(
                    "SELECT 1 FROM pokemon_catalog WHERE id = $1",
                    pokemon_id,
                )
                if not exists:
                    raise ShopError("Покемон с таким id не найден.")
                if field_key == "name":
                    existing_name = await conn.fetchval(
                        """
                        SELECT 1
                        FROM pokemon_catalog
                        WHERE lower(name) = lower($1)
                          AND id <> $2
                        """,
                        prepared_value,
                        pokemon_id,
                    )
                    if existing_name:
                        raise ShopError("Покемон с таким именем уже существует.")
                try:
                    await conn.execute(
                        f"UPDATE pokemon_catalog SET {column_name} = $2 WHERE id = $1",
                        pokemon_id,
                        prepared_value,
                    )
                except asyncpg.UniqueViolationError as exc:
                    raise ShopError("Не удалось сохранить поле из-за ограничения уникальности.") from exc

        logger.info(
            "admin_pokemon_species_updated",
            pokemon_id=pokemon_id,
            field_key=field_key,
        )
        return await self.get_pokemon_catalog_entry_by_id(pokemon_id)

    async def admin_attach_image_variant(
        self,
        *,
        pokemon_id: int,
        storage_bucket: str,
        object_key: str,
        content_type: Optional[str],
        etag: Optional[str],
        source: Optional[str],
        display_order: int,
        is_default: bool,
    ) -> int:
        """Create image_credit and attach it to a pokemon species as a variant."""
        if display_order <= 0:
            raise ShopError("display_order должен быть больше нуля.")
        normalized_source = source.strip() if isinstance(source, str) else None
        normalized_source = normalized_source or None

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                pokemon_row = await conn.fetchrow(
                    "SELECT id, image_credit_id FROM pokemon_catalog WHERE id = $1",
                    pokemon_id,
                )
                if pokemon_row is None:
                    raise ShopError("Покемон с таким id не найден.")

                await self._ensure_catalog_image_variant_materialized(conn, pokemon_id=pokemon_id)

                existing_order = await conn.fetchval(
                    """
                    SELECT 1
                    FROM pokemon_image_variants
                    WHERE pokemon_id = $1 AND display_order = $2
                    """,
                    pokemon_id,
                    display_order,
                )
                if existing_order:
                    raise ShopError("У этого покемона уже есть вариант с таким порядком.")

                image_credit_id = await conn.fetchval(
                    """
                    INSERT INTO image_credits (
                        storage_bucket,
                        object_key,
                        content_type,
                        etag,
                        source
                    )
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                    """,
                    storage_bucket,
                    object_key,
                    content_type,
                    etag,
                    normalized_source,
                )

                should_be_default = is_default
                if not should_be_default:
                    has_default_variant = await conn.fetchval(
                        """
                        SELECT 1
                        FROM pokemon_image_variants
                        WHERE pokemon_id = $1
                          AND is_default = true
                        """,
                        pokemon_id,
                    )
                    if not has_default_variant and pokemon_row["image_credit_id"] is None:
                        should_be_default = True

                if should_be_default:
                    await conn.execute(
                        """
                        UPDATE pokemon_image_variants
                        SET is_default = false
                        WHERE pokemon_id = $1
                          AND is_default = true
                        """,
                        pokemon_id,
                    )

                await conn.execute(
                    """
                    INSERT INTO pokemon_image_variants (
                        pokemon_id,
                        image_credit_id,
                        display_order,
                        is_default
                    )
                    VALUES ($1, $2, $3, $4)
                    """,
                    pokemon_id,
                    image_credit_id,
                    display_order,
                    should_be_default,
                )

                if should_be_default or pokemon_row["image_credit_id"] is None:
                    await conn.execute(
                        """
                        UPDATE pokemon_catalog
                        SET image_credit_id = $2
                        WHERE id = $1
                        """,
                        pokemon_id,
                        image_credit_id,
                    )

        logger.info(
            "admin_image_variant_attached",
            pokemon_id=pokemon_id,
            image_credit_id=image_credit_id,
            display_order=display_order,
            is_default=should_be_default,
        )
        return int(image_credit_id)

    async def admin_update_image_source(self, *, image_credit_id: int, source: Optional[str]) -> int:
        """Update source URL for an existing image_credit."""
        normalized_source = source.strip() if isinstance(source, str) else None
        normalized_source = normalized_source or None

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                exists = await conn.fetchval(
                    "SELECT 1 FROM image_credits WHERE id = $1",
                    image_credit_id,
                )
                if not exists:
                    raise ShopError("image_credit_id не найден.")
                await conn.execute(
                    """
                    UPDATE image_credits
                    SET source = $2
                    WHERE id = $1
                    """,
                    image_credit_id,
                    normalized_source,
                )
        logger.info("admin_image_source_updated", image_credit_id=image_credit_id)
        return image_credit_id

    async def admin_update_image_variant_metadata(
        self,
        *,
        pokemon_id: int,
        image_credit_id: int,
        display_order: int,
        is_default: bool,
    ) -> int:
        """Update display_order and default flag for one image variant."""
        if display_order <= 0:
            raise ShopError("display_order должен быть больше нуля.")

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._ensure_catalog_image_variant_materialized(conn, pokemon_id=pokemon_id)

                variant_row = await conn.fetchrow(
                    """
                    SELECT pokemon_id, image_credit_id
                    FROM pokemon_image_variants
                    WHERE pokemon_id = $1
                      AND image_credit_id = $2
                    """,
                    pokemon_id,
                    image_credit_id,
                )
                if variant_row is None:
                    raise ShopError("Вариант с таким pokemon_id и image_credit_id не найден.")

                conflict = await conn.fetchval(
                    """
                    SELECT 1
                    FROM pokemon_image_variants
                    WHERE pokemon_id = $1
                      AND display_order = $2
                      AND image_credit_id <> $3
                    """,
                    pokemon_id,
                    display_order,
                    image_credit_id,
                )
                if conflict:
                    raise ShopError("У этого покемона уже есть вариант с таким порядком.")

                if is_default:
                    await conn.execute(
                        """
                        UPDATE pokemon_image_variants
                        SET is_default = false
                        WHERE pokemon_id = $1
                          AND is_default = true
                          AND image_credit_id <> $2
                        """,
                        pokemon_id,
                        image_credit_id,
                    )

                await conn.execute(
                    """
                    UPDATE pokemon_image_variants
                    SET display_order = $3,
                        is_default = $4
                    WHERE pokemon_id = $1
                      AND image_credit_id = $2
                    """,
                    pokemon_id,
                    image_credit_id,
                    display_order,
                    is_default,
                )

                if is_default:
                    await conn.execute(
                        """
                        UPDATE pokemon_catalog
                        SET image_credit_id = $2
                        WHERE id = $1
                        """,
                        pokemon_id,
                        image_credit_id,
                    )
                else:
                    has_default_variant = await conn.fetchval(
                        """
                        SELECT image_credit_id
                        FROM pokemon_image_variants
                        WHERE pokemon_id = $1
                          AND is_default = true
                        LIMIT 1
                        """,
                        pokemon_id,
                    )
                    if has_default_variant:
                        await conn.execute(
                            """
                            UPDATE pokemon_catalog
                            SET image_credit_id = $2
                            WHERE id = $1
                            """,
                            pokemon_id,
                            has_default_variant,
                        )

        logger.info(
            "admin_image_variant_metadata_updated",
            pokemon_id=pokemon_id,
            image_credit_id=image_credit_id,
            display_order=display_order,
            is_default=is_default,
        )
        return image_credit_id

    async def record_admin_action_audit(
        self,
        *,
        actor_telegram_id: int,
        actor_username: Optional[str],
        action_type: str,
        status: str,
        input_payload: Optional[dict[str, object]] = None,
        result_payload: Optional[dict[str, object]] = None,
        error_message: Optional[str] = None,
        target_user_id: Optional[int] = None,
        target_telegram_id: Optional[int] = None,
        target_username: Optional[str] = None,
    ) -> int:
        """Persist one admin-bot audit record."""
        self._ensure_pool()
        input_json = json.dumps(input_payload, ensure_ascii=False) if input_payload is not None else None
        result_json = json.dumps(result_payload, ensure_ascii=False) if result_payload is not None else None

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                actor_user_id = await self._ensure_user(conn, actor_telegram_id, actor_username)
                if target_user_id is None and target_telegram_id is not None:
                    target_user_id = await conn.fetchval(
                        "SELECT id FROM users WHERE tg_user_id = $1",
                        target_telegram_id,
                    )
                audit_id = await conn.fetchval(
                    """
                    INSERT INTO admin_action_audit (
                        actor_user_id,
                        actor_telegram_id,
                        actor_username,
                        action_type,
                        target_user_id,
                        target_telegram_id,
                        target_username,
                        status,
                        input_payload,
                        result_payload,
                        error_message
                    )
                    VALUES (
                        $1,
                        $2,
                        $3,
                        $4,
                        $5,
                        $6,
                        $7,
                        $8,
                        $9::jsonb,
                        $10::jsonb,
                        $11
                    )
                    RETURNING id
                    """,
                    actor_user_id,
                    actor_telegram_id,
                    actor_username,
                    action_type,
                    target_user_id,
                    target_telegram_id,
                    target_username,
                    status,
                    input_json,
                    result_json,
                    error_message,
                )
        logger.info(
            "admin_action_audit_recorded",
            audit_id=audit_id,
            actor_telegram_id=actor_telegram_id,
            action_type=action_type,
            status=status,
            target_telegram_id=target_telegram_id,
        )
        return int(audit_id)

    async def get_recent_admin_action_audit(self, *, limit: int = 10) -> list[AdminAuditRecord]:
        """Return recent admin audit records for operator review."""
        self._ensure_pool()
        bounded_limit = max(1, min(limit, 100))
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    id,
                    actor_user_id,
                    actor_telegram_id,
                    actor_username,
                    action_type,
                    target_user_id,
                    target_telegram_id,
                    target_username,
                    status,
                    input_payload,
                    result_payload,
                    error_message,
                    created_at
                FROM admin_action_audit
                ORDER BY created_at DESC, id DESC
                LIMIT $1
                """,
                bounded_limit,
            )
        return [
            AdminAuditRecord(
                audit_id=int(row["id"]),
                actor_user_id=int(row["actor_user_id"]) if row["actor_user_id"] is not None else None,
                actor_telegram_id=int(row["actor_telegram_id"]),
                actor_username=row["actor_username"],
                action_type=str(row["action_type"]),
                target_user_id=int(row["target_user_id"]) if row["target_user_id"] is not None else None,
                target_telegram_id=int(row["target_telegram_id"]) if row["target_telegram_id"] is not None else None,
                target_username=row["target_username"],
                status=str(row["status"]),
                input_payload=_coerce_json_object(row["input_payload"]),
                result_payload=_coerce_json_object(row["result_payload"]),
                error_message=row["error_message"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def get_admin_broadcast_target_chat_ids(self) -> list[int]:
        """Return known group/supergroup chat ids eligible for admin broadcasts."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT chat_id
                FROM chat_encounter_state
                WHERE chat_id < 0
                ORDER BY chat_id
                """
            )
        return [int(row["chat_id"]) for row in rows]

    async def get_profile_referral(self, telegram_id: int, username: Optional[str], bot_username: Optional[str]) -> ProfileReferral:
        """Build the user's referral code and link."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._ensure_user(conn, telegram_id, username)
                await self._get_user_id_by_telegram_id(conn, telegram_id)

        referral_code = f"ref_{telegram_id}"
        referral_link = referral_code
        if bot_username:
            referral_link = f"https://t.me/{bot_username}?start={referral_code}"

        logger.info("profile_referral_loaded", telegram_id=telegram_id, has_bot_username=bool(bot_username))
        return ProfileReferral(referral_code=referral_code, referral_link=referral_link)

    async def update_profile_language(self, telegram_id: int, username: Optional[str], language: str) -> str:
        """Persist the user's profile language."""
        normalized = language.strip().lower()
        if normalized not in {"ru", "en"}:
            raise ShopError(f"Unsupported profile language: {language}")

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._ensure_user(conn, telegram_id, username)
                user_id = await self._get_user_id_by_telegram_id(conn, telegram_id)
                await conn.execute(
                    """
                    UPDATE user_settings
                    SET language = $2,
                        updated_at = NOW()
                    WHERE user_id = $1
                    """,
                    user_id,
                    normalized,
                )
        logger.info("profile_language_updated", telegram_id=telegram_id, language=normalized)
        return normalized

    async def update_profile_nickname(self, telegram_id: int, username: Optional[str], nickname: str) -> str:
        """Persist a custom profile nickname."""
        normalized = nickname.strip()
        if not normalized:
            raise ShopError("Nickname cannot be empty")
        if len(normalized) > 64:
            raise ShopError("Nickname is too long")

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._ensure_user(conn, telegram_id, username)
                user_id = await self._get_user_id_by_telegram_id(conn, telegram_id)
                await conn.execute(
                    """
                    UPDATE users
                    SET nickname = $2
                    WHERE id = $1
                    """,
                    user_id,
                    normalized,
                )
        logger.info("profile_nickname_updated", telegram_id=telegram_id)
        return normalized

    async def _fetch_profile_summary_by_user_id(self, conn: asyncpg.Connection, user_id: int) -> ProfileSummary:
        summary_row = await conn.fetchrow(
            """
            WITH owned_base AS (
              SELECT COUNT(DISTINCT split_part(COALESCE(pc.dex_form_code, pc.id::text), '-', 1))::int AS total_unique_owned
              FROM user_pokemon
              JOIN pokemon_catalog pc ON pc.id = user_pokemon.pokemon_id
              WHERE owner_user_id = $1
                AND released_at IS NULL
            ),
            owned_forms AS (
              SELECT COUNT(DISTINCT pokemon_id)::int AS total_form_owned
              FROM user_pokemon
              WHERE owner_user_id = $1
                AND released_at IS NULL
            ),
            total_base_catalog AS (
              SELECT COUNT(DISTINCT split_part(COALESCE(dex_form_code, id::text), '-', 1))::int AS total_catalog
              FROM pokemon_catalog
            ),
            total_form_catalog AS (
              SELECT COUNT(*)::int AS total_form_catalog
              FROM pokemon_catalog
            )
            SELECT
              u.id AS user_id,
              u.tg_user_id,
              u.tg_username,
              u.nickname,
              u.created_at,
              us.language,
              us.profile_pic_credit_id,
              cover_pc.name AS cover_pokemon_name,
              COALESCE(ob.total_unique_owned, 0) AS total_unique_owned,
              tbc.total_catalog,
              COALESCE(ofm.total_form_owned, 0) AS total_form_owned,
              tfc.total_form_catalog
            FROM users u
            JOIN user_settings us ON us.user_id = u.id
            CROSS JOIN total_base_catalog tbc
            CROSS JOIN total_form_catalog tfc
            LEFT JOIN owned_base ob ON TRUE
            LEFT JOIN owned_forms ofm ON TRUE
            LEFT JOIN pokemon_catalog cover_pc ON cover_pc.image_credit_id = us.profile_pic_credit_id
            WHERE u.id = $1
            """,
            user_id,
        )
        if not summary_row:
            raise ShopError("Unable to load profile summary")

        rarity_rows = await conn.fetch(
            """
            SELECT
              pc.rarity,
              COUNT(DISTINCT split_part(COALESCE(pc.dex_form_code, pc.id::text), '-', 1))::int AS total_catalog,
              COUNT(DISTINCT split_part(COALESCE(owned_pc.dex_form_code, owned_pc.id::text), '-', 1))::int AS owned_unique
            FROM pokemon_catalog pc
            LEFT JOIN user_pokemon up
              ON up.pokemon_id = pc.id
             AND up.owner_user_id = $1
             AND up.released_at IS NULL
            LEFT JOIN pokemon_catalog owned_pc ON owned_pc.id = up.pokemon_id
            WHERE pc.rarity IS NOT NULL
            GROUP BY pc.rarity
            """,
            user_id,
        )

        rarity_map = {
            str(row["rarity"]): ProfileRarityProgress(
                rarity=str(row["rarity"]),
                owned_unique=int(row["owned_unique"]),
                total_catalog=int(row["total_catalog"]),
                percent=_calculate_percent(int(row["owned_unique"]), int(row["total_catalog"])),
            )
            for row in rarity_rows
        }
        rarity_progress = tuple(
            rarity_map.get(
                rarity,
                ProfileRarityProgress(rarity=rarity, owned_unique=0, total_catalog=0, percent=0),
            )
            for rarity in RARITY_ORDER
        )
        total_unique_owned = int(summary_row["total_unique_owned"])
        total_catalog = int(summary_row["total_catalog"])
        total_form_owned = int(summary_row["total_form_owned"])
        total_form_catalog = int(summary_row["total_form_catalog"])
        return ProfileSummary(
            user_id=int(summary_row["user_id"]),
            telegram_id=int(summary_row["tg_user_id"]),
            tg_username=summary_row["tg_username"],
            nickname=summary_row["nickname"],
            language=str(summary_row["language"]),
            created_at=_normalize_timestamp(summary_row["created_at"]),
            total_unique_owned=total_unique_owned,
            total_catalog=total_catalog,
            total_unique_percent=_calculate_percent(total_unique_owned, total_catalog),
            rarity_progress=rarity_progress,
            profile_pic_credit_id=summary_row["profile_pic_credit_id"],
            cover_pokemon_name=summary_row["cover_pokemon_name"],
            total_form_owned=total_form_owned,
            total_form_catalog=total_form_catalog,
            total_form_percent=_calculate_percent(total_form_owned, total_form_catalog),
        )

    async def _cleanup_invalid_pvp_team_slots(self, conn: asyncpg.Connection, user_id: int) -> None:
        """Drop stale team slots that reference missing, transferred, or released pokemon."""
        await conn.execute(
            """
            DELETE FROM user_pvp_team_slots slots
            WHERE slots.user_id = $1
              AND NOT EXISTS (
                SELECT 1
                FROM user_pokemon up
                WHERE up.id = slots.user_pokemon_id
                  AND up.owner_user_id = $1
                  AND up.released_at IS NULL
              )
            """,
            user_id,
        )

    async def _fetch_pvp_team(self, conn: asyncpg.Connection, user_id: int) -> PvpTeam:
        """Load all five PvP team slots for one user."""
        rows = await conn.fetch(
            """
            SELECT
              slots.slot_index,
              pc.id AS pokemon_id,
              up.id AS sample_user_pokemon_id,
              pc.name,
              pc.rarity,
              pc.type,
              pc.dex_form_code,
              (
                SELECT COUNT(*)
                FROM user_pokemon up_count
                WHERE up_count.owner_user_id = up.owner_user_id
                  AND up_count.pokemon_id = up.pokemon_id
                  AND up_count.released_at IS NULL
              )::int AS quantity,
              pc.base_hp,
              pc.base_attack,
              pc.base_defense,
              pc.base_stamina,
              pc.image_credit_id,
              up.is_locked
            FROM user_pvp_team_slots slots
            JOIN user_pokemon up ON up.id = slots.user_pokemon_id
            JOIN pokemon_catalog pc ON pc.id = up.pokemon_id
            WHERE slots.user_id = $1
              AND up.owner_user_id = $1
              AND up.released_at IS NULL
            ORDER BY slots.slot_index ASC
            """,
            user_id,
        )
        entries_by_slot: dict[int, CollectionEntry] = {
            int(row["slot_index"]): CollectionEntry(
                pokemon_id=int(row["pokemon_id"]),
                sample_user_pokemon_id=int(row["sample_user_pokemon_id"]),
                name=str(row["name"]),
                rarity=str(row["rarity"]),
                pokemon_type=row["type"],
                quantity=int(row["quantity"]),
                base_hp=int(row["base_hp"]),
                base_attack=int(row["base_attack"]),
                base_defense=int(row["base_defense"]),
                base_stamina=int(row["base_stamina"]),
                image_credit_id=row["image_credit_id"],
                is_locked=bool(row["is_locked"]),
                dex_form_code=row["dex_form_code"],
                form_badge=_form_badge_from_dex_form_code(row["dex_form_code"]),
            )
            for row in rows
        }
        return PvpTeam(
            slots=tuple(
                PvpTeamSlot(slot_index=slot_index, entry=entries_by_slot.get(slot_index))
                for slot_index in range(1, PVP_TEAM_SLOT_COUNT + 1)
            )
        )

    async def _is_user_pokemon_in_pvp_team(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: int,
        user_pokemon_id: int,
    ) -> bool:
        """Return whether one owned pokemon instance is currently in the user's PvP team."""
        found = await conn.fetchval(
            """
            SELECT 1
            FROM user_pvp_team_slots
            WHERE user_id = $1
              AND user_pokemon_id = $2
            LIMIT 1
            """,
            user_id,
            user_pokemon_id,
        )
        return bool(found)

    async def _ensure_user_has_complete_pvp_team(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: int,
        own_message: str,
    ) -> None:
        team_count = int(
            await conn.fetchval(
                """
                SELECT COUNT(*)::int
                FROM user_pvp_team_slots
                WHERE user_id = $1
                """,
                user_id,
            )
            or 0
        )
        if team_count != PVP_TEAM_SLOT_COUNT:
            raise ShopError(own_message)

    async def _ensure_pvp_initiator_available(self, conn: asyncpg.Connection, user_id: int) -> None:
        """Ensure the user has no other outgoing pending/selecting PvP challenge."""
        conflict = await conn.fetchval(
            """
            SELECT 1
            FROM pvp_challenges
            WHERE initiator_user_id = $1
              AND (
                (status = $2 AND (pending_expires_at IS NULL OR pending_expires_at > NOW()))
                OR (status = $3 AND (selection_expires_at IS NULL OR selection_expires_at > NOW()))
                OR (status = $4 AND (selection_expires_at IS NULL OR selection_expires_at > NOW()))
              )
            LIMIT 1
            """,
            user_id,
            PVP_CHALLENGE_STATUS_PENDING,
            PVP_CHALLENGE_STATUS_SELECTING_INITIATOR,
            PVP_CHALLENGE_STATUS_SELECTING_TARGET,
        )
        if conflict:
            raise ShopError("У вас уже есть исходящий вызов или незавершённый выбор бойца.")

    async def _ensure_pvp_user_not_selecting(
        self,
        conn: asyncpg.Connection,
        user_id: int,
        *,
        own_message: str,
    ) -> None:
        conflict = await conn.fetchval(
            """
            SELECT 1
            FROM pvp_challenges
            WHERE (initiator_user_id = $1 OR target_user_id = $1)
              AND (
                (status = $2 AND (selection_expires_at IS NULL OR selection_expires_at > NOW()))
                OR (status = $3 AND (selection_expires_at IS NULL OR selection_expires_at > NOW()))
                OR (status = $4 AND (selection_expires_at IS NULL OR selection_expires_at > NOW()))
              )
            LIMIT 1
            """,
            user_id,
            PVP_CHALLENGE_STATUS_SELECTING_INITIATOR,
            PVP_CHALLENGE_STATUS_SELECTING_TARGET,
            PVP_CHALLENGE_STATUS_BATTLING,
        )
        if conflict:
            raise ShopError(own_message)

    async def _fetch_pvp_challenge_summary(self, conn: asyncpg.Connection, challenge_id: int) -> PvpChallengeSummary:
        row = await conn.fetchrow(
            """
            SELECT
              pc.id,
              pc.chat_id,
              pc.message_thread_id,
              pc.message_id,
              pc.status,
              pc.pending_expires_at,
              pc.selection_expires_at,
              pc.created_at,
              pc.accepted_at,
              pc.canceled_at,
              pc.completed_at,
              pc.cancel_reason,
              initiator.id AS initiator_user_id,
              initiator.tg_user_id AS initiator_tg_user_id,
              initiator.tg_username AS initiator_tg_username,
              initiator.nickname AS initiator_nickname,
              target.id AS target_user_id,
              target.tg_user_id AS target_tg_user_id,
              target.tg_username AS target_tg_username,
              target.nickname AS target_nickname,
              pc.initiator_selected_user_pokemon_id,
              pc.target_selected_user_pokemon_id,
              ipc.name AS initiator_selected_name,
              ipc.rarity AS initiator_selected_rarity,
              ipc.dex_form_code AS initiator_selected_dex_form_code,
              ipc.type AS initiator_selected_pokemon_type,
              ipc.base_hp AS initiator_selected_base_hp,
              ipc.base_attack AS initiator_selected_base_attack,
              ipc.base_defense AS initiator_selected_base_defense,
              ipc.base_stamina AS initiator_selected_base_stamina,
              tpc.name AS target_selected_name,
              tpc.rarity AS target_selected_rarity,
              tpc.dex_form_code AS target_selected_dex_form_code,
              tpc.type AS target_selected_pokemon_type,
              tpc.base_hp AS target_selected_base_hp,
              tpc.base_attack AS target_selected_base_attack,
              tpc.base_defense AS target_selected_base_defense,
              tpc.base_stamina AS target_selected_base_stamina
            FROM pvp_challenges pc
            JOIN users initiator ON initiator.id = pc.initiator_user_id
            JOIN users target ON target.id = pc.target_user_id
            LEFT JOIN user_pokemon iup ON iup.id = pc.initiator_selected_user_pokemon_id
            LEFT JOIN pokemon_catalog ipc ON ipc.id = iup.pokemon_id
            LEFT JOIN user_pokemon tup ON tup.id = pc.target_selected_user_pokemon_id
            LEFT JOIN pokemon_catalog tpc ON tpc.id = tup.pokemon_id
            WHERE pc.id = $1
            """,
            challenge_id,
        )
        if not row:
            raise ShopError("Вызов на бой не найден.")
        return PvpChallengeSummary(
            challenge_id=int(row["id"]),
            chat_id=int(row["chat_id"]),
            message_thread_id=row["message_thread_id"],
            message_id=int(row["message_id"]) if row["message_id"] is not None else None,
            status=str(row["status"]),
            pending_expires_at=_normalize_optional_timestamp(row["pending_expires_at"]),
            selection_expires_at=_normalize_optional_timestamp(row["selection_expires_at"]),
            created_at=_normalize_timestamp(row["created_at"]),
            accepted_at=_normalize_optional_timestamp(row["accepted_at"]),
            canceled_at=_normalize_optional_timestamp(row["canceled_at"]),
            completed_at=_normalize_optional_timestamp(row["completed_at"]),
            cancel_reason=row["cancel_reason"],
            initiator=PvpChallengeParticipant(
                user_id=int(row["initiator_user_id"]),
                telegram_id=int(row["initiator_tg_user_id"]),
                username=row["initiator_tg_username"],
                nickname=row["initiator_nickname"],
                label=_resolve_trade_user_label(row["initiator_nickname"], row["initiator_tg_username"], int(row["initiator_tg_user_id"])),
                selected_user_pokemon_id=int(row["initiator_selected_user_pokemon_id"]) if row["initiator_selected_user_pokemon_id"] is not None else None,
                selected_name=row["initiator_selected_name"],
                selected_rarity=row["initiator_selected_rarity"],
                selected_dex_form_code=row["initiator_selected_dex_form_code"],
                selected_form_badge=_form_badge_from_dex_form_code(row["initiator_selected_dex_form_code"]),
                selected_pokemon_type=row["initiator_selected_pokemon_type"],
                selected_base_hp=int(row["initiator_selected_base_hp"]) if row["initiator_selected_base_hp"] is not None else None,
                selected_base_attack=int(row["initiator_selected_base_attack"]) if row["initiator_selected_base_attack"] is not None else None,
                selected_base_defense=int(row["initiator_selected_base_defense"]) if row["initiator_selected_base_defense"] is not None else None,
                selected_base_stamina=int(row["initiator_selected_base_stamina"]) if row["initiator_selected_base_stamina"] is not None else None,
            ),
            target=PvpChallengeParticipant(
                user_id=int(row["target_user_id"]),
                telegram_id=int(row["target_tg_user_id"]),
                username=row["target_tg_username"],
                nickname=row["target_nickname"],
                label=_resolve_trade_user_label(row["target_nickname"], row["target_tg_username"], int(row["target_tg_user_id"])),
                selected_user_pokemon_id=int(row["target_selected_user_pokemon_id"]) if row["target_selected_user_pokemon_id"] is not None else None,
                selected_name=row["target_selected_name"],
                selected_rarity=row["target_selected_rarity"],
                selected_dex_form_code=row["target_selected_dex_form_code"],
                selected_form_badge=_form_badge_from_dex_form_code(row["target_selected_dex_form_code"]),
                selected_pokemon_type=row["target_selected_pokemon_type"],
                selected_base_hp=int(row["target_selected_base_hp"]) if row["target_selected_base_hp"] is not None else None,
                selected_base_attack=int(row["target_selected_base_attack"]) if row["target_selected_base_attack"] is not None else None,
                selected_base_defense=int(row["target_selected_base_defense"]) if row["target_selected_base_defense"] is not None else None,
                selected_base_stamina=int(row["target_selected_base_stamina"]) if row["target_selected_base_stamina"] is not None else None,
            ),
        )

    async def _close_pvp_challenge(
        self,
        conn: asyncpg.Connection,
        challenge_id: int,
        *,
        status: str,
        cancel_reason: Optional[str],
    ) -> None:
        should_mark_canceled = status in {
            PVP_CHALLENGE_STATUS_REJECTED,
            PVP_CHALLENGE_STATUS_CANCELED,
            PVP_CHALLENGE_STATUS_EXPIRED,
        }
        should_mark_completed = status == PVP_CHALLENGE_STATUS_COMPLETED
        await conn.execute(
            """
            UPDATE pvp_challenges
            SET status = $2,
                cancel_reason = $3,
                canceled_at = CASE WHEN $4 THEN NOW() ELSE canceled_at END,
                completed_at = CASE WHEN $5 THEN NOW() ELSE completed_at END
            WHERE id = $1
            """,
            challenge_id,
            status,
            cancel_reason,
            should_mark_canceled,
            should_mark_completed,
        )

    async def search_profile_cover_candidates(
        self,
        telegram_id: int,
        username: Optional[str],
        query: str,
        *,
        limit: int = 5,
    ) -> list[ProfileCoverCandidate]:
        """Search owned pokemon with images that can be used as profile covers."""
        normalized = query.strip()
        if not normalized:
            return []

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._ensure_user(conn, telegram_id, username)
                user_id = await self._get_user_id_by_telegram_id(conn, telegram_id)
                rows = await conn.fetch(
                    """
                    SELECT
                      pc.id AS pokemon_id,
                      MIN(up.id)::bigint AS sample_user_pokemon_id,
                      pc.name,
                      pc.rarity,
                      pc.type,
                      pc.image_credit_id
                    FROM user_pokemon up
                    JOIN pokemon_catalog pc ON pc.id = up.pokemon_id
                    WHERE up.owner_user_id = $1
                      AND up.released_at IS NULL
                      AND pc.image_credit_id IS NOT NULL
                      AND pc.name ILIKE '%' || $2 || '%'
                    GROUP BY pc.id, pc.name, pc.rarity, pc.type, pc.image_credit_id
                    ORDER BY
                      CASE WHEN lower(pc.name) = lower($2) THEN 0 ELSE 1 END,
                      length(pc.name) ASC,
                      pc.id ASC
                    LIMIT $3
                    """,
                    user_id,
                    normalized,
                    limit,
                )
        logger.info(
            "profile_cover_candidates_loaded",
            telegram_id=telegram_id,
            query=normalized,
            count=len(rows),
            limit=limit,
        )
        return [
            ProfileCoverCandidate(
                pokemon_id=int(row["pokemon_id"]),
                sample_user_pokemon_id=int(row["sample_user_pokemon_id"]),
                name=str(row["name"]),
                rarity=str(row["rarity"]),
                pokemon_type=row["type"],
                image_credit_id=int(row["image_credit_id"]),
            )
            for row in rows
        ]

    async def update_profile_cover(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        image_credit_id: int,
    ) -> int:
        """Persist a chosen profile cover image for the user."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._ensure_user(conn, telegram_id, username)
                user_id = await self._get_user_id_by_telegram_id(conn, telegram_id)
                exists = await conn.fetchval(
                    """
                    SELECT 1
                    FROM user_pokemon up
                    JOIN pokemon_catalog pc ON pc.id = up.pokemon_id
                    WHERE up.owner_user_id = $1
                      AND up.released_at IS NULL
                      AND pc.image_credit_id = $2
                    LIMIT 1
                    """,
                    user_id,
                    image_credit_id,
                )
                if not exists:
                    logger.warning(
                        "profile_cover_rejected",
                        telegram_id=telegram_id,
                        image_credit_id=image_credit_id,
                        reason="not_owned",
                    )
                    raise ShopError("Нельзя поставить обложку с покемоном, которого у вас нет.")
                await conn.execute(
                    """
                    UPDATE user_settings
                    SET profile_pic_credit_id = $2,
                        updated_at = NOW()
                    WHERE user_id = $1
                    """,
                    user_id,
                    image_credit_id,
                )
        logger.info("profile_cover_updated", telegram_id=telegram_id, image_credit_id=image_credit_id)
        return image_credit_id

    async def search_pokemon_catalog(self, query: str, *, limit: int = 5) -> list[PokemonSearchEntry]:
        """Search the global pokemon catalog by partial name with SQL-side limiting."""
        normalized = query.strip()
        if not normalized:
            return []

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT
                  id AS pokemon_id,
                  dex_form_code,
                  name,
                  rarity,
                  type,
                  base_hp,
                  base_attack,
                  base_defense,
                  base_stamina,
                  image_credit_id
                FROM pokemon_catalog
                WHERE name ILIKE '%' || $1 || '%'
                ORDER BY
                  CASE WHEN lower(name) = lower($1) THEN 0 ELSE 1 END,
                  length(name) ASC,
                  {_dex_form_sort_sql(qualified_column="dex_form_code")}
                LIMIT $2
                """,
                normalized,
                limit,
            )
        logger.info("pokemon_catalog_search_loaded", query=normalized, count=len(rows), limit=limit)
        return [
            PokemonSearchEntry(
                pokemon_id=int(row["pokemon_id"]),
                name=str(row["name"]),
                rarity=str(row["rarity"]),
                pokemon_type=row["type"],
                base_hp=int(row["base_hp"]),
                base_attack=int(row["base_attack"]),
                base_defense=int(row["base_defense"]),
                base_stamina=int(row["base_stamina"]),
                image_credit_id=row["image_credit_id"],
                dex_form_code=row["dex_form_code"],
                form_badge=_form_badge_from_dex_form_code(row["dex_form_code"]),
            )
            for row in rows
        ]

    async def get_pokemon_catalog_entry(self, pokemon_id: int) -> Optional[PokemonSearchEntry]:
        """Load one pokemon catalog entry by species id."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                  id AS pokemon_id,
                  dex_form_code,
                  name,
                  rarity,
                  type,
                  base_hp,
                  base_attack,
                  base_defense,
                  base_stamina,
                  image_credit_id
                FROM pokemon_catalog
                WHERE id = $1
                """,
                pokemon_id,
            )
        if not row:
            return None
        return PokemonSearchEntry(
            pokemon_id=int(row["pokemon_id"]),
            name=str(row["name"]),
            rarity=str(row["rarity"]),
            pokemon_type=row["type"],
            base_hp=int(row["base_hp"]),
            base_attack=int(row["base_attack"]),
            base_defense=int(row["base_defense"]),
            base_stamina=int(row["base_stamina"]),
            image_credit_id=row["image_credit_id"],
            dex_form_code=row["dex_form_code"],
            form_badge=_form_badge_from_dex_form_code(row["dex_form_code"]),
        )

    async def get_pokemon_catalog_entries_by_display_id(self, display_id: str) -> list[PokemonSearchEntry]:
        """Load all catalog entries that share the same player-facing base dex id."""
        normalized = display_id.strip()
        if not normalized:
            return []

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT
                  id AS pokemon_id,
                  dex_form_code,
                  name,
                  rarity,
                  type,
                  base_hp,
                  base_attack,
                  base_defense,
                  base_stamina,
                  image_credit_id
                FROM pokemon_catalog
                WHERE split_part(COALESCE(dex_form_code, id::text), '-', 1) = $1
                ORDER BY {_dex_form_sort_sql(qualified_column="dex_form_code")}
                """,
                normalized,
            )

        return [
            PokemonSearchEntry(
                pokemon_id=int(row["pokemon_id"]),
                name=str(row["name"]),
                rarity=str(row["rarity"]),
                pokemon_type=row["type"],
                base_hp=int(row["base_hp"]),
                base_attack=int(row["base_attack"]),
                base_defense=int(row["base_defense"]),
                base_stamina=int(row["base_stamina"]),
                image_credit_id=row["image_credit_id"],
                dex_form_code=row["dex_form_code"],
                form_badge=_form_badge_from_dex_form_code(row["dex_form_code"]),
            )
            for row in rows
        ]

    async def get_image_credit(self, image_credit_id: int) -> Optional[ImageCreditRecord]:
        """Load one stored object reference by image credit id."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, storage_bucket, object_key, content_type, source
                FROM image_credits
                WHERE id = $1
                """,
                image_credit_id,
            )
        if not row:
            return None
        return ImageCreditRecord(
            image_credit_id=int(row["id"]),
            storage_bucket=str(row["storage_bucket"]),
            object_key=str(row["object_key"]),
            content_type=row["content_type"],
            source=row["source"],
        )

    @staticmethod
    def _normalize_http_source(source: object) -> Optional[str]:
        if not isinstance(source, str):
            return None
        normalized = source.strip()
        if not normalized.startswith(("http://", "https://")):
            return None
        return normalized

    async def _ensure_catalog_image_variant_materialized(
        self,
        conn: asyncpg.Connection,
        *,
        pokemon_id: int,
    ) -> None:
        """Backfill legacy pokemon_catalog.image_credit_id into pokemon_image_variants when needed."""
        catalog_row = await conn.fetchrow(
            """
            SELECT image_credit_id
            FROM pokemon_catalog
            WHERE id = $1
            """,
            pokemon_id,
        )
        if catalog_row is None or catalog_row["image_credit_id"] is None:
            return

        image_credit_id = int(catalog_row["image_credit_id"])
        existing_variant = await conn.fetchval(
            """
            SELECT 1
            FROM pokemon_image_variants
            WHERE pokemon_id = $1
              AND image_credit_id = $2
            """,
            pokemon_id,
            image_credit_id,
        )
        if existing_variant:
            return

        existing_rows = await conn.fetch(
            """
            SELECT image_credit_id, display_order, is_default
            FROM pokemon_image_variants
            WHERE pokemon_id = $1
            ORDER BY display_order ASC, image_credit_id ASC
            """,
            pokemon_id,
        )
        existing_default = next((row for row in existing_rows if bool(row["is_default"])), None)
        next_display_order = 1 if not existing_rows else max(int(row["display_order"]) for row in existing_rows) + 1

        await conn.execute(
            """
            INSERT INTO pokemon_image_variants (
                pokemon_id,
                image_credit_id,
                display_order,
                is_default
            )
            VALUES ($1, $2, $3, $4)
            """,
            pokemon_id,
            image_credit_id,
            next_display_order,
            existing_default is None,
        )
        logger.info(
            "pokemon_image_variant_materialized",
            pokemon_id=pokemon_id,
            image_credit_id=image_credit_id,
            display_order=next_display_order,
            is_default=existing_default is None,
        )

    async def _list_pokemon_image_variants(
        self,
        conn: asyncpg.Connection,
        *,
        pokemon_id: int,
    ) -> list[asyncpg.Record]:
        return await conn.fetch(
            """
            WITH catalog_image AS (
              SELECT image_credit_id
              FROM pokemon_catalog
              WHERE id = $1
            )
            SELECT
              variants.image_credit_id,
              variants.display_order,
              variants.is_default,
              ic.source
            FROM (
              SELECT
                piv.image_credit_id,
                piv.display_order,
                piv.is_default
              FROM pokemon_image_variants piv
              WHERE piv.pokemon_id = $1

              UNION ALL

              SELECT
                ci.image_credit_id,
                1 AS display_order,
                TRUE AS is_default
              FROM catalog_image ci
              WHERE ci.image_credit_id IS NOT NULL
                AND NOT EXISTS(
                  SELECT 1
                  FROM pokemon_image_variants piv
                  WHERE piv.pokemon_id = $1
                    AND piv.image_credit_id = ci.image_credit_id
                )
            ) AS variants
            LEFT JOIN image_credits ic ON ic.id = variants.image_credit_id
            ORDER BY variants.display_order ASC, variants.image_credit_id ASC
            """,
            pokemon_id,
        )

    async def _resolve_pokemon_image_selection_for_user_id(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: int,
        pokemon_id: int,
    ) -> PokemonImageSelection:
        variant_rows = await self._list_pokemon_image_variants(conn, pokemon_id=pokemon_id)
        if not variant_rows:
            return PokemonImageSelection(
                pokemon_id=pokemon_id,
                image_credit_id=None,
                source_url=None,
                position=1,
                total=1,
            )

        preferred_row = await conn.fetchrow(
            """
            SELECT image_credit_id
            FROM user_pokemon_image_preferences
            WHERE user_id = $1
              AND pokemon_id = $2
            """,
            user_id,
            pokemon_id,
        )
        preferred_image_credit_id = (
            int(preferred_row["image_credit_id"])
            if preferred_row and preferred_row["image_credit_id"] is not None
            else None
        )

        resolved_index = 0
        chosen_row = None
        if preferred_image_credit_id is not None:
            for index, row in enumerate(variant_rows):
                if int(row["image_credit_id"]) == preferred_image_credit_id:
                    chosen_row = row
                    resolved_index = index
                    break

        if chosen_row is None:
            chosen_row = next((row for row in variant_rows if bool(row["is_default"])), variant_rows[0])
            resolved_index = variant_rows.index(chosen_row)
            if preferred_image_credit_id is not None:
                await conn.execute(
                    """
                    DELETE FROM user_pokemon_image_preferences
                    WHERE user_id = $1
                      AND pokemon_id = $2
                    """,
                    user_id,
                    pokemon_id,
                )
                logger.info(
                    "pokemon_image_preference_repaired",
                    user_id=user_id,
                    pokemon_id=pokemon_id,
                    invalid_image_credit_id=preferred_image_credit_id,
                    fallback_image_credit_id=int(chosen_row["image_credit_id"]),
                )

        return PokemonImageSelection(
            pokemon_id=pokemon_id,
            image_credit_id=int(chosen_row["image_credit_id"]),
            source_url=self._normalize_http_source(chosen_row["source"]),
            position=resolved_index + 1,
            total=len(variant_rows),
        )

    async def get_pokemon_image_selection(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        pokemon_id: int,
    ) -> PokemonImageSelection:
        """Resolve the active image variant for one viewer and one pokemon species."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                return await self._resolve_pokemon_image_selection_for_user_id(
                    conn,
                    user_id=user_id,
                    pokemon_id=pokemon_id,
                )

    async def cycle_pokemon_image_selection(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        pokemon_id: int,
    ) -> PokemonImageSelection:
        """Persist and return the next image variant for a user's view of a species."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                current = await self._resolve_pokemon_image_selection_for_user_id(
                    conn,
                    user_id=user_id,
                    pokemon_id=pokemon_id,
                )
                if current.total <= 1 or current.image_credit_id is None:
                    return current

                variant_rows = await self._list_pokemon_image_variants(conn, pokemon_id=pokemon_id)
                next_index = current.position % len(variant_rows)
                next_row = variant_rows[next_index]
                next_image_credit_id = int(next_row["image_credit_id"])

                await conn.execute(
                    """
                    INSERT INTO user_pokemon_image_preferences (user_id, pokemon_id, image_credit_id, updated_at)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (user_id, pokemon_id)
                    DO UPDATE SET image_credit_id = EXCLUDED.image_credit_id, updated_at = NOW()
                    """,
                    user_id,
                    pokemon_id,
                    next_image_credit_id,
                )
                logger.info(
                    "pokemon_image_selection_cycled",
                    user_id=user_id,
                    pokemon_id=pokemon_id,
                    next_image_credit_id=next_image_credit_id,
                    next_position=next_index + 1,
                    total_variants=len(variant_rows),
                )
                return PokemonImageSelection(
                    pokemon_id=pokemon_id,
                    image_credit_id=next_image_credit_id,
                    source_url=self._normalize_http_source(next_row["source"]),
                    position=next_index + 1,
                    total=len(variant_rows),
                )

    async def get_market_listings_page(
        self,
        telegram_id: int,
        username: Optional[str],
        filter_state: Optional[MarketBrowseState] = None,
    ) -> MarketBrowsePage:
        """Load a paginated list of active sale listings visible to the user."""
        self._ensure_pool()
        requested_state = filter_state or MarketBrowseState()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                return await self._fetch_market_listings_page(conn, user_id, requested_state)

    async def get_market_listing_summary(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        listing_id: int,
    ) -> MarketListingSummary:
        """Load one active market listing that is visible to the current user."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                listing = await self._fetch_market_listing_summary(conn, listing_id)
                if listing.status != MARKET_LISTING_STATUS_ACTIVE:
                    raise ShopError("Лот больше недоступен.")
                if listing.seller_user_id == user_id:
                    raise ShopError("Это ваш лот.")
                return listing

    async def get_my_market_listings(self, telegram_id: int, username: Optional[str]) -> list[MarketListingSummary]:
        """Load active listings created by the current user."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                rows = await conn.fetch(
                    """
                    SELECT
                      ml.id AS listing_id,
                      ml.seller_user_id,
                      u.nickname AS seller_nickname,
                      u.tg_username AS seller_username,
                      ml.pokemon_instance_id AS user_pokemon_id,
                      pc.id AS pokemon_id,
                      pc.dex_form_code,
                      pc.name,
                      pc.rarity,
                      pc.type,
                      pc.image_credit_id,
                      ml.price,
                      ml.status,
                      ml.listed_at,
                      ml.expires_at
                    FROM market_listings ml
                    JOIN user_pokemon up ON up.id = ml.pokemon_instance_id
                    JOIN pokemon_catalog pc ON pc.id = up.pokemon_id
                    JOIN users u ON u.id = ml.seller_user_id
                    WHERE ml.seller_user_id = $1
                      AND ml.status = $2
                    ORDER BY ml.listed_at DESC, ml.id DESC
                    """,
                    user_id,
                    MARKET_LISTING_STATUS_ACTIVE,
                )
        return [_map_market_listing_summary(row) for row in rows]

    async def get_my_market_listing_summary(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        listing_id: int,
    ) -> MarketListingSummary:
        """Load one active listing owned by the current user."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                listing = await self._fetch_market_listing_summary(conn, listing_id)
                if listing.seller_user_id != user_id:
                    raise ShopError("Лот не найден.")
                if listing.status != MARKET_LISTING_STATUS_ACTIVE:
                    raise ShopError("Этот лот уже не активен.")
                return listing

    async def get_my_market_buy_requests(
        self,
        telegram_id: int,
        username: Optional[str],
    ) -> list[MarketBuyRequestSummary]:
        """Load active buy requests created by the current user."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                rows = await conn.fetch(
                    """
                    SELECT
                      mbr.id AS request_id,
                      mbr.requester_user_id,
                      u.nickname AS requester_nickname,
                      u.tg_username AS requester_username,
                      mbr.pokemon_id,
                      pc.dex_form_code,
                      pc.name,
                      pc.rarity,
                      pc.type,
                      pc.image_credit_id,
                      mbr.price,
                      mbr.reserved_amount,
                      mbr.status,
                      mbr.created_at,
                      NULL::bigint AS matching_user_pokemon_id
                    FROM market_buy_requests mbr
                    JOIN pokemon_catalog pc ON pc.id = mbr.pokemon_id
                    JOIN users u ON u.id = mbr.requester_user_id
                    WHERE mbr.requester_user_id = $1
                      AND mbr.status = $2
                    ORDER BY mbr.created_at DESC, mbr.id DESC
                    """,
                    user_id,
                    MARKET_REQUEST_STATUS_ACTIVE,
                )
        return [_map_market_buy_request_summary(row) for row in rows]

    async def get_my_market_buy_request_summary(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        request_id: int,
    ) -> MarketBuyRequestSummary:
        """Load one active buy request owned by the current user."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                market_request = await self._fetch_market_buy_request_summary(conn, request_id)
                if market_request.requester_user_id != user_id:
                    raise ShopError("Заявка не найдена.")
                if market_request.status != MARKET_REQUEST_STATUS_ACTIVE:
                    raise ShopError("Эта заявка уже не активна.")
                return market_request

    async def get_sellable_market_buy_requests(
        self,
        telegram_id: int,
        username: Optional[str],
    ) -> list[MarketBuyRequestSummary]:
        """Load only foreign buy requests that the current user can fulfill."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                rows = await conn.fetch(
                    """
                    SELECT
                      mbr.id AS request_id,
                      mbr.requester_user_id,
                      u.nickname AS requester_nickname,
                      u.tg_username AS requester_username,
                      mbr.pokemon_id,
                      pc.dex_form_code,
                      pc.name,
                      pc.rarity,
                      pc.type,
                      pc.image_credit_id,
                      mbr.price,
                      mbr.reserved_amount,
                      mbr.status,
                      mbr.created_at,
                      (
                        SELECT MIN(up.id)
                        FROM user_pokemon up
                        WHERE up.owner_user_id = $1
                          AND up.pokemon_id = mbr.pokemon_id
                          AND up.is_locked = FALSE
                          AND up.released_at IS NULL
                          AND NOT EXISTS (
                            SELECT 1
                            FROM market_listings ml
                            WHERE ml.pokemon_instance_id = up.id
                              AND ml.status = $2
                          )
                      ) AS matching_user_pokemon_id
                    FROM market_buy_requests mbr
                    JOIN pokemon_catalog pc ON pc.id = mbr.pokemon_id
                    JOIN users u ON u.id = mbr.requester_user_id
                    WHERE mbr.requester_user_id <> $1
                      AND mbr.status = $3
                      AND EXISTS (
                        SELECT 1
                        FROM user_pokemon up
                        WHERE up.owner_user_id = $1
                          AND up.pokemon_id = mbr.pokemon_id
                          AND up.is_locked = FALSE
                          AND up.released_at IS NULL
                          AND NOT EXISTS (
                            SELECT 1
                            FROM market_listings ml
                            WHERE ml.pokemon_instance_id = up.id
                              AND ml.status = $2
                          )
                      )
                    ORDER BY mbr.created_at DESC, mbr.id DESC
                    """,
                    user_id,
                    MARKET_LISTING_STATUS_ACTIVE,
                    MARKET_REQUEST_STATUS_ACTIVE,
                )
        return [_map_market_buy_request_summary(row) for row in rows]

    async def get_market_sell_precheck_error(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        user_pokemon_id: int,
    ) -> Optional[str]:
        """Return a user-facing reason when a pokemon cannot enter sell flow."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                seller_user_id = await self._ensure_user(conn, telegram_id, username)
                active_count = int(
                    await conn.fetchval(
                        """
                        SELECT COUNT(*)::int
                        FROM market_listings
                        WHERE seller_user_id = $1
                          AND status = $2
                        """,
                        seller_user_id,
                        MARKET_LISTING_STATUS_ACTIVE,
                    )
                    or 0
                )
                pokemon_row = await conn.fetchrow(
                    """
                    SELECT id, owner_user_id, is_locked, released_at
                    FROM user_pokemon
                    WHERE id = $1
                    """,
                    user_pokemon_id,
                )
                if not pokemon_row:
                    return "Нельзя создать лот: экземпляр покемона не найден."
                if int(pokemon_row["owner_user_id"]) != seller_user_id:
                    return "Нельзя создать лот: этот покемон вам не принадлежит."
                if pokemon_row["released_at"] is not None:
                    return "Нельзя создать лот: этот покемон уже отпущен."
                if bool(pokemon_row["is_locked"]):
                    return "Нельзя создать лот: этот покемон заблокирован."
                if await self._is_user_pokemon_in_pvp_team(
                    conn,
                    user_id=seller_user_id,
                    user_pokemon_id=user_pokemon_id,
                ):
                    return "Нельзя создать лот: этот покемон состоит в боевой команде."
                existing_listing = await conn.fetchval(
                    """
                    SELECT 1
                    FROM market_listings
                    WHERE pokemon_instance_id = $1
                      AND status = $2
                    LIMIT 1
                    """,
                    user_pokemon_id,
                    MARKET_LISTING_STATUS_ACTIVE,
                )
                if existing_listing:
                    return "Нельзя создать лот: этот покемон уже выставлен на рынок."
                if active_count >= MARKET_MAX_ACTIVE_LISTINGS:
                    return f"Нельзя создать лот: у вас уже заняты все {MARKET_MAX_ACTIVE_LISTINGS} слота продажи."
                await self._ensure_user_balance(conn, seller_user_id, POKECOIN_CODE)
                balance = await self._get_balance_for_update(conn, seller_user_id, POKECOIN_CODE)
                if balance < 1:
                    return "Нельзя создать лот: не хватает pokecoin даже на стартовую комиссию."
        return None

    async def get_market_buy_request_precheck_error(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        pokemon_id: int,
    ) -> Optional[str]:
        """Return a user-facing reason when a pokemon cannot enter buy-request flow."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                requester_user_id = await self._ensure_user(conn, telegram_id, username)
                active_count = int(
                    await conn.fetchval(
                        """
                        SELECT COUNT(*)::int
                        FROM market_buy_requests
                        WHERE requester_user_id = $1
                          AND status = $2
                        """,
                        requester_user_id,
                        MARKET_REQUEST_STATUS_ACTIVE,
                    )
                    or 0
                )
                if active_count >= MARKET_MAX_ACTIVE_BUY_REQUESTS:
                    return f"Нельзя создать заявку: у вас уже заняты все {MARKET_MAX_ACTIVE_BUY_REQUESTS} слотов заявок."
                pokemon_exists = await conn.fetchval("SELECT 1 FROM pokemon_catalog WHERE id = $1", pokemon_id)
                if not pokemon_exists:
                    return "Нельзя создать заявку: покемон не найден."
                duplicate_request = await conn.fetchval(
                    """
                    SELECT 1
                    FROM market_buy_requests
                    WHERE requester_user_id = $1
                      AND pokemon_id = $2
                      AND status = $3
                    LIMIT 1
                    """,
                    requester_user_id,
                    pokemon_id,
                    MARKET_REQUEST_STATUS_ACTIVE,
                )
                if duplicate_request:
                    return "Нельзя создать заявку: у вас уже есть активная заявка на этого покемона."
                await self._ensure_user_balance(conn, requester_user_id, POKECOIN_CODE)
                balance = await self._get_balance_for_update(conn, requester_user_id, POKECOIN_CODE)
                if balance < 1:
                    return "Нельзя создать заявку: у вас нет pokecoin для резерва."
        return None

    async def get_market_buy_listing_precheck_error(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        listing_id: int,
    ) -> Optional[str]:
        """Return a user-facing reason when a listing cannot be purchased."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                buyer_user_id = await self._ensure_user(conn, telegram_id, username)
                listing_row = await conn.fetchrow(
                    """
                    SELECT seller_user_id, status
                    FROM market_listings
                    WHERE id = $1
                    """,
                    listing_id,
                )
                if not listing_row:
                    return "Этот лот уже удалён."

                seller_user_id = int(listing_row["seller_user_id"])
                if seller_user_id == buyer_user_id:
                    return "Нельзя купить свой собственный лот."

                status = str(listing_row["status"])
                if status == MARKET_LISTING_STATUS_SOLD:
                    return "Этот лот уже купили."
                if status == MARKET_LISTING_STATUS_REMOVED:
                    return "Этот лот уже снят с рынка."
                if status == MARKET_LISTING_STATUS_EXPIRED:
                    return "Срок этого лота истёк."
        return None

    async def get_market_request_fulfill_precheck_error(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        request_id: int,
        user_pokemon_id: int,
    ) -> Optional[str]:
        """Return a user-facing reason when a buy request cannot be fulfilled."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                seller_user_id = await self._ensure_user(conn, telegram_id, username)
                request_row = await conn.fetchrow(
                    """
                    SELECT requester_user_id, pokemon_id, status
                    FROM market_buy_requests
                    WHERE id = $1
                    """,
                    request_id,
                )
                if not request_row:
                    return "Заявка не найдена."

                buyer_user_id = int(request_row["requester_user_id"])
                if buyer_user_id == seller_user_id:
                    return "Нельзя закрыть свою собственную заявку."

                status = str(request_row["status"])
                if status == MARKET_REQUEST_STATUS_FULFILLED:
                    return "Эту заявку уже закрыл другой пользователь."
                if status == MARKET_REQUEST_STATUS_CANCELED:
                    return "Эту заявку уже отменили."

                pokemon_row = await conn.fetchrow(
                    """
                    SELECT owner_user_id, pokemon_id, is_locked, released_at
                    FROM user_pokemon
                    WHERE id = $1
                    """,
                    user_pokemon_id,
                )
                if not pokemon_row:
                    return "Экземпляр покемона не найден."
                if int(pokemon_row["owner_user_id"]) != seller_user_id:
                    return "Этот покемон вам не принадлежит."
                if pokemon_row["released_at"] is not None:
                    return "Этот покемон уже отпущен."
                if bool(pokemon_row["is_locked"]):
                    return "Этот покемон заблокирован."
                if await self._is_user_pokemon_in_pvp_team(
                    conn,
                    user_id=seller_user_id,
                    user_pokemon_id=user_pokemon_id,
                ):
                    return "Сначала уберите этого покемона из боевой команды."
                if int(pokemon_row["pokemon_id"]) != int(request_row["pokemon_id"]):
                    return "Этот покемон не подходит под заявку."

                active_listing = await conn.fetchval(
                    """
                    SELECT 1
                    FROM market_listings
                    WHERE pokemon_instance_id = $1
                      AND status = $2
                    LIMIT 1
                    """,
                    user_pokemon_id,
                    MARKET_LISTING_STATUS_ACTIVE,
                )
                if active_listing:
                    return "Этот покемон уже выставлен на рынок."
        return None

    async def create_market_listing(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        user_pokemon_id: int,
        price: int,
    ) -> MarketListingSummary:
        """Create an active sale listing and charge the initial commission."""
        if price <= 0:
            raise ShopError("Цена лота должна быть больше нуля.")

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                seller_user_id = await self._ensure_user(conn, telegram_id, username)
                active_count = int(
                    await conn.fetchval(
                        """
                        SELECT COUNT(*)::int
                        FROM market_listings
                        WHERE seller_user_id = $1
                          AND status = $2
                        """,
                        seller_user_id,
                        MARKET_LISTING_STATUS_ACTIVE,
                    )
                    or 0
                )
                if active_count >= MARKET_MAX_ACTIVE_LISTINGS:
                    raise ShopError("У вас уже заняты все 2 слота продажи.")

                pokemon_row = await conn.fetchrow(
                    """
                    SELECT up.id, up.owner_user_id, up.is_locked, up.released_at, pc.id AS pokemon_id
                    FROM user_pokemon up
                    JOIN pokemon_catalog pc ON pc.id = up.pokemon_id
                    WHERE up.id = $1
                    FOR UPDATE
                    """,
                    user_pokemon_id,
                )
                if not pokemon_row or int(pokemon_row["owner_user_id"]) != seller_user_id:
                    raise ShopError("Нельзя выставить чужого покемона.")
                if pokemon_row["released_at"] is not None:
                    raise ShopError("Нельзя выставить отпущенного покемона.")
                if bool(pokemon_row["is_locked"]):
                    raise ShopError("Нельзя выставить заблокированного покемона.")
                if await self._is_user_pokemon_in_pvp_team(
                    conn,
                    user_id=seller_user_id,
                    user_pokemon_id=user_pokemon_id,
                ):
                    raise ShopError("Нельзя выставить покемона из боевой команды.")

                existing_listing = await conn.fetchval(
                    """
                    SELECT 1
                    FROM market_listings
                    WHERE pokemon_instance_id = $1
                      AND status = $2
                    LIMIT 1
                    """,
                    user_pokemon_id,
                    MARKET_LISTING_STATUS_ACTIVE,
                )
                if existing_listing:
                    raise ShopError("Этот покемон уже выставлен на рынок.")

                commission_amount = _calculate_market_daily_commission(price)
                await self._ensure_user_balance(conn, seller_user_id, POKECOIN_CODE)
                balance = await self._get_balance_for_update(conn, seller_user_id, POKECOIN_CODE)
                if balance < commission_amount:
                    raise InsufficientFundsError("Недостаточно pokecoin для стартовой комиссии.")

                now = datetime.now(UTC)
                await self._adjust_balance(conn, seller_user_id, POKECOIN_CODE, -commission_amount)
                try:
                    inserted = await conn.fetchrow(
                        """
                        INSERT INTO market_listings (
                          seller_user_id,
                          pokemon_instance_id,
                          currency_id,
                          price,
                          status,
                          listed_at,
                          initial_commission_paid,
                          daily_commission_amount,
                          last_commission_at,
                          next_commission_at,
                          expires_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $7, $6, $8, $9)
                        RETURNING id
                        """,
                        seller_user_id,
                        user_pokemon_id,
                        await self._get_currency_id(conn, POKECOIN_CODE),
                        price,
                        MARKET_LISTING_STATUS_ACTIVE,
                        now,
                        commission_amount,
                        now + timedelta(days=1),
                        now + timedelta(days=MARKET_LISTING_LIFETIME_DAYS),
                    )
                except asyncpg.UniqueViolationError as exc:
                    logger.warning(
                        "market_listing_create_conflict",
                        seller_user_id=seller_user_id,
                        user_pokemon_id=user_pokemon_id,
                        error=str(exc),
                    )
                    raise ShopError("Этот покемон уже выставлен на рынок.") from exc
                listing = await self._fetch_market_listing_summary(conn, int(inserted["id"]))

        logger.info(
            "market_listing_created",
            seller_user_id=listing.seller_user_id,
            listing_id=listing.listing_id,
            user_pokemon_id=listing.user_pokemon_id,
            price=listing.price,
            commission_amount=commission_amount,
        )
        return listing

    async def remove_market_listing(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        listing_id: int,
        reason: str = "manual",
    ) -> MarketListingSummary:
        """Remove one of the user's active sale listings."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                seller_user_id = await self._ensure_user(conn, telegram_id, username)
                listing_row = await conn.fetchrow(
                    """
                    SELECT id, seller_user_id, status
                    FROM market_listings
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    listing_id,
                )
                if not listing_row:
                    raise ShopError("Лот не найден.")
                if int(listing_row["seller_user_id"]) != seller_user_id:
                    raise ShopError("Нельзя снять чужой лот.")
                if str(listing_row["status"]) != MARKET_LISTING_STATUS_ACTIVE:
                    raise ShopError("Этот лот уже не активен.")

                await conn.execute(
                    """
                    UPDATE market_listings
                    SET status = $2,
                        removed_at = NOW(),
                        removal_reason = $3
                    WHERE id = $1
                    """,
                    listing_id,
                    MARKET_LISTING_STATUS_REMOVED,
                    reason,
                )
                listing = await self._fetch_market_listing_summary(conn, listing_id)

        logger.info(
            "market_listing_removed",
            seller_user_id=listing.seller_user_id,
            listing_id=listing.listing_id,
            reason=reason,
        )
        return listing

    async def purchase_market_listing(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        listing_id: int,
    ) -> MarketPurchaseResult:
        """Buy one active listing atomically."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                buyer_user_id = await self._ensure_user(conn, telegram_id, username)
                listing_row = await conn.fetchrow(
                    """
                    SELECT
                      ml.id,
                      ml.seller_user_id,
                      ml.pokemon_instance_id,
                      ml.price,
                      ml.status
                    FROM market_listings ml
                    WHERE ml.id = $1
                    FOR UPDATE
                    """,
                    listing_id,
                )
                if not listing_row:
                    raise ShopError("Лот не найден.")
                if str(listing_row["status"]) != MARKET_LISTING_STATUS_ACTIVE:
                    raise ShopError("Лот уже недоступен.")

                seller_user_id = int(listing_row["seller_user_id"])
                if seller_user_id == buyer_user_id:
                    raise ShopError("Нельзя купить свой собственный лот.")

                await self._ensure_user_balance(conn, buyer_user_id, POKECOIN_CODE)
                await self._ensure_user_balance(conn, seller_user_id, POKECOIN_CODE)
                balance = await self._get_balance_for_update(conn, buyer_user_id, POKECOIN_CODE)
                price = int(listing_row["price"])
                if balance < price:
                    raise InsufficientFundsError("Недостаточно pokecoin для покупки.")

                await self._adjust_balance(conn, buyer_user_id, POKECOIN_CODE, -price)
                await self._adjust_balance(conn, seller_user_id, POKECOIN_CODE, price)
                await conn.execute(
                    """
                    UPDATE user_pokemon
                    SET owner_user_id = $2
                    WHERE id = $1
                    """,
                    int(listing_row["pokemon_instance_id"]),
                    buyer_user_id,
                )
                await conn.execute(
                    """
                    UPDATE market_listings
                    SET status = $2,
                        completed_at = NOW()
                    WHERE id = $1
                    """,
                    listing_id,
                    MARKET_LISTING_STATUS_SOLD,
                )
                listing = await self._fetch_market_listing_summary(conn, listing_id)

        logger.info(
            "market_purchase_completed",
            listing_id=listing.listing_id,
            buyer_user_id=buyer_user_id,
            seller_user_id=seller_user_id,
            price=price,
        )
        return MarketPurchaseResult(
            listing=listing,
            buyer_user_id=buyer_user_id,
            seller_user_id=seller_user_id,
            price=price,
        )

    async def create_market_buy_request(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        pokemon_id: int,
        price: int,
    ) -> MarketBuyRequestSummary:
        """Create a concrete-species buy request with immediate fund reservation."""
        if price <= 0:
            raise ShopError("Цена заявки должна быть больше нуля.")

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                requester_user_id = await self._ensure_user(conn, telegram_id, username)
                active_count = int(
                    await conn.fetchval(
                        """
                        SELECT COUNT(*)::int
                        FROM market_buy_requests
                        WHERE requester_user_id = $1
                          AND status = $2
                        """,
                        requester_user_id,
                        MARKET_REQUEST_STATUS_ACTIVE,
                    )
                    or 0
                )
                if active_count >= MARKET_MAX_ACTIVE_BUY_REQUESTS:
                    raise ShopError("У вас уже заняты все 5 слотов заявок.")

                pokemon_exists = await conn.fetchval("SELECT 1 FROM pokemon_catalog WHERE id = $1", pokemon_id)
                if not pokemon_exists:
                    raise ShopError("Покемон для заявки не найден.")

                duplicate_request = await conn.fetchval(
                    """
                    SELECT 1
                    FROM market_buy_requests
                    WHERE requester_user_id = $1
                      AND pokemon_id = $2
                      AND status = $3
                    LIMIT 1
                    """,
                    requester_user_id,
                    pokemon_id,
                    MARKET_REQUEST_STATUS_ACTIVE,
                )
                if duplicate_request:
                    raise ShopError("У вас уже есть активная заявка на этого покемона.")

                await self._ensure_user_balance(conn, requester_user_id, POKECOIN_CODE)
                balance = await self._get_balance_for_update(conn, requester_user_id, POKECOIN_CODE)
                if balance < price:
                    raise InsufficientFundsError("Недостаточно pokecoin для заявки.")

                await self._adjust_balance(conn, requester_user_id, POKECOIN_CODE, -price)
                try:
                    inserted = await conn.fetchrow(
                        """
                        INSERT INTO market_buy_requests (
                          requester_user_id,
                          pokemon_id,
                          currency_id,
                          price,
                          reserved_amount,
                          status
                        )
                        VALUES ($1, $2, $3, $4, $4, $5)
                        RETURNING id
                        """,
                        requester_user_id,
                        pokemon_id,
                        await self._get_currency_id(conn, POKECOIN_CODE),
                        price,
                        MARKET_REQUEST_STATUS_ACTIVE,
                    )
                except asyncpg.UniqueViolationError as exc:
                    logger.warning(
                        "market_buy_request_create_conflict",
                        requester_user_id=requester_user_id,
                        pokemon_id=pokemon_id,
                        error=str(exc),
                    )
                    raise ShopError("У вас уже есть активная заявка на этого покемона.") from exc
                request = await self._fetch_market_buy_request_summary(conn, int(inserted["id"]))

        logger.info(
            "market_buy_request_created",
            request_id=request.request_id,
            requester_user_id=request.requester_user_id,
            pokemon_id=request.pokemon_id,
            price=request.price,
        )
        return request

    async def cancel_market_buy_request(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        request_id: int,
        reason: str = "manual",
    ) -> MarketBuyRequestSummary:
        """Cancel one of the user's active buy requests and return reserved funds."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                requester_user_id = await self._ensure_user(conn, telegram_id, username)
                request_row = await conn.fetchrow(
                    """
                    SELECT id, requester_user_id, status, reserved_amount
                    FROM market_buy_requests
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    request_id,
                )
                if not request_row:
                    raise ShopError("Заявка не найдена.")
                if int(request_row["requester_user_id"]) != requester_user_id:
                    raise ShopError("Нельзя отменить чужую заявку.")
                if str(request_row["status"]) != MARKET_REQUEST_STATUS_ACTIVE:
                    raise ShopError("Эта заявка уже не активна.")

                await self._adjust_balance(conn, requester_user_id, POKECOIN_CODE, int(request_row["reserved_amount"]))
                await conn.execute(
                    """
                    UPDATE market_buy_requests
                    SET status = $2,
                        canceled_at = NOW(),
                        updated_at = NOW(),
                        cancel_reason = $3
                    WHERE id = $1
                    """,
                    request_id,
                    MARKET_REQUEST_STATUS_CANCELED,
                    reason,
                )
                request = await self._fetch_market_buy_request_summary(conn, request_id)

        logger.info(
            "market_buy_request_canceled",
            request_id=request.request_id,
            requester_user_id=request.requester_user_id,
            reason=reason,
        )
        return request

    async def fulfill_market_buy_request(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        request_id: int,
        user_pokemon_id: int,
    ) -> MarketRequestFulfillmentResult:
        """Fulfill a foreign active buy request with one owned unlocked pokemon."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                seller_user_id = await self._ensure_user(conn, telegram_id, username)
                request_row = await conn.fetchrow(
                    """
                    SELECT id, requester_user_id, pokemon_id, reserved_amount, status, price
                    FROM market_buy_requests
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    request_id,
                )
                if not request_row:
                    raise ShopError("Заявка не найдена.")
                if str(request_row["status"]) != MARKET_REQUEST_STATUS_ACTIVE:
                    raise ShopError("Заявка уже недоступна.")

                buyer_user_id = int(request_row["requester_user_id"])
                if buyer_user_id == seller_user_id:
                    raise ShopError("Нельзя закрыть свою собственную заявку.")

                pokemon_row = await conn.fetchrow(
                    """
                    SELECT id, owner_user_id, pokemon_id, is_locked, released_at
                    FROM user_pokemon
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    user_pokemon_id,
                )
                if not pokemon_row or int(pokemon_row["owner_user_id"]) != seller_user_id:
                    raise ShopError("Нельзя продать чужого покемона.")
                if pokemon_row["released_at"] is not None:
                    raise ShopError("Нельзя продать отпущенного покемона.")
                if bool(pokemon_row["is_locked"]):
                    raise ShopError("Нельзя продать заблокированного покемона.")
                if await self._is_user_pokemon_in_pvp_team(
                    conn,
                    user_id=seller_user_id,
                    user_pokemon_id=user_pokemon_id,
                ):
                    raise ShopError("Сначала уберите этого покемона из боевой команды.")
                if int(pokemon_row["pokemon_id"]) != int(request_row["pokemon_id"]):
                    raise ShopError("Этот покемон не подходит под заявку.")

                active_listing = await conn.fetchval(
                    """
                    SELECT 1
                    FROM market_listings
                    WHERE pokemon_instance_id = $1
                      AND status = $2
                    LIMIT 1
                    """,
                    user_pokemon_id,
                    MARKET_LISTING_STATUS_ACTIVE,
                )
                if active_listing:
                    raise ShopError("Этот покемон уже выставлен на рынок.")

                await self._ensure_user_balance(conn, seller_user_id, POKECOIN_CODE)
                await self._adjust_balance(conn, seller_user_id, POKECOIN_CODE, int(request_row["reserved_amount"]))
                await conn.execute(
                    """
                    UPDATE user_pokemon
                    SET owner_user_id = $2
                    WHERE id = $1
                    """,
                    user_pokemon_id,
                    buyer_user_id,
                )
                await conn.execute(
                    """
                    UPDATE market_buy_requests
                    SET status = $2,
                        fulfilled_at = NOW(),
                        updated_at = NOW(),
                        fulfilled_by_user_id = $3,
                        fulfilled_user_pokemon_id = $4
                    WHERE id = $1
                    """,
                    request_id,
                    MARKET_REQUEST_STATUS_FULFILLED,
                    seller_user_id,
                    user_pokemon_id,
                )
                request = await self._fetch_market_buy_request_summary(conn, request_id)

        logger.info(
            "market_buy_request_fulfilled",
            request_id=request.request_id,
            buyer_user_id=buyer_user_id,
            seller_user_id=seller_user_id,
            user_pokemon_id=user_pokemon_id,
            price=int(request_row["price"]),
        )
        return MarketRequestFulfillmentResult(
            request=request,
            seller_user_id=seller_user_id,
            buyer_user_id=buyer_user_id,
            transferred_user_pokemon_id=user_pokemon_id,
            price=int(request_row["price"]),
        )

    async def process_market_listing_maintenance(
        self,
        *,
        now: Optional[datetime] = None,
    ) -> dict[str, int]:
        """Charge due commissions and deactivate overdue active listings."""
        self._ensure_pool()
        current_time = _normalize_timestamp(now) if now is not None else datetime.now(UTC)
        stats = {
            "charged_listings": 0,
            "charged_cycles": 0,
            "expired_listings": 0,
            "removed_unpaid_listings": 0,
        }

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch(
                    """
                    SELECT
                      id,
                      seller_user_id,
                      daily_commission_amount,
                      next_commission_at,
                      expires_at
                    FROM market_listings
                    WHERE status = $1
                      AND (
                        expires_at <= $2
                        OR next_commission_at <= $2
                      )
                    ORDER BY listed_at ASC, id ASC
                    FOR UPDATE
                    """,
                    MARKET_LISTING_STATUS_ACTIVE,
                    current_time,
                )

                for row in rows:
                    listing_id = int(row["id"])
                    seller_user_id = int(row["seller_user_id"])
                    expires_at = _normalize_timestamp(row["expires_at"])
                    next_commission_at = _normalize_timestamp(row["next_commission_at"])
                    commission_amount = int(row["daily_commission_amount"])

                    if expires_at <= current_time:
                        await conn.execute(
                            """
                            UPDATE market_listings
                            SET status = $2,
                                removed_at = NOW(),
                                removal_reason = $3
                            WHERE id = $1
                            """,
                            listing_id,
                            MARKET_LISTING_STATUS_EXPIRED,
                            "expired",
                        )
                        stats["expired_listings"] += 1
                        logger.info("market_listing_expired", listing_id=listing_id, seller_user_id=seller_user_id)
                        continue

                    due_cycles = _market_due_commission_cycles(
                        next_commission_at=next_commission_at,
                        expires_at=expires_at,
                        now=current_time,
                    )
                    if due_cycles <= 0:
                        continue

                    await self._ensure_user_balance(conn, seller_user_id, POKECOIN_CODE)
                    balance = await self._get_balance_for_update(conn, seller_user_id, POKECOIN_CODE)
                    total_due = commission_amount * due_cycles
                    if balance < total_due:
                        await conn.execute(
                            """
                            UPDATE market_listings
                            SET status = $2,
                                removed_at = NOW(),
                                removal_reason = $3
                            WHERE id = $1
                            """,
                            listing_id,
                            MARKET_LISTING_STATUS_REMOVED,
                            "commission_unpaid",
                        )
                        stats["removed_unpaid_listings"] += 1
                        logger.info(
                            "market_listing_removed_for_unpaid_commission",
                            listing_id=listing_id,
                            seller_user_id=seller_user_id,
                            due_cycles=due_cycles,
                            total_due=total_due,
                            balance=balance,
                        )
                        continue

                    await self._adjust_balance(conn, seller_user_id, POKECOIN_CODE, -total_due)
                    new_next_commission_at = next_commission_at + timedelta(days=due_cycles)
                    last_commission_at = new_next_commission_at - timedelta(days=1)
                    await conn.execute(
                        """
                        UPDATE market_listings
                        SET last_commission_at = $2,
                            next_commission_at = $3
                        WHERE id = $1
                        """,
                        listing_id,
                        last_commission_at,
                        new_next_commission_at,
                    )
                    stats["charged_listings"] += 1
                    stats["charged_cycles"] += due_cycles
                    logger.info(
                        "market_listing_commission_charged",
                        listing_id=listing_id,
                        seller_user_id=seller_user_id,
                        due_cycles=due_cycles,
                        total_due=total_due,
                        next_commission_at=new_next_commission_at.isoformat(),
                    )

        return stats

    async def resolve_trade_target_by_username(self, username: str) -> tuple[int, Optional[str], Optional[str]]:
        """Resolve a known Telegram username for /trade @username."""
        normalized = username.strip().lstrip("@").lower()
        if not normalized:
            raise ShopError("Укажите username после /trade.")

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT tg_user_id, tg_username, nickname
                FROM users
                WHERE lower(tg_username) = $1
                """,
                normalized,
            )
        if not row:
            raise ShopError("Я пока не знаю этого пользователя. Он должен хотя бы раз воспользоваться ботом.")
        return int(row["tg_user_id"]), row["tg_username"], row["nickname"]

    async def get_active_trade_for_user(
        self,
        telegram_id: int,
        username: Optional[str],
    ) -> Optional[TradeSessionSummary]:
        """Return the active accepted trade for a user, if present."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._ensure_user(conn, telegram_id, username)
                user_id = await self._get_user_id_by_telegram_id(conn, telegram_id)
                trade_id = await self._get_linked_trade_id(conn, user_id)
                if trade_id is None:
                    return None
                trade = await self._fetch_trade_summary(conn, trade_id)
                return trade if trade.status == TRADE_STATUS_ACTIVE else None

    async def create_trade_request(
        self,
        *,
        initiator_telegram_id: int,
        initiator_username: Optional[str],
        target_telegram_id: int,
        target_username: Optional[str],
        chat_id: int,
        message_thread_id: Optional[int],
    ) -> TradeSessionSummary:
        """Create a pending trade request between two users."""
        if initiator_telegram_id == target_telegram_id:
            raise ShopError("Нельзя предложить обмен самому себе.")

        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                initiator_user_id = await self._ensure_user(conn, initiator_telegram_id, initiator_username)
                target_user_id = await self._ensure_user(conn, target_telegram_id, target_username)
                await self._ensure_trade_user_available(
                    conn,
                    initiator_user_id,
                    own_message="У вас уже есть активный или ожидающий трейд.",
                )
                await self._ensure_trade_user_available(
                    conn,
                    target_user_id,
                    own_message="У этого пользователя уже есть активный или ожидающий трейд.",
                )
                inserted = await conn.fetchrow(
                    """
                    INSERT INTO trade_sessions (
                      chat_id,
                      message_thread_id,
                      initiator_user_id,
                      target_user_id,
                      status,
                      pending_expires_at
                    )
                    VALUES (
                      $1,
                      $2,
                      $3,
                      $4,
                      $5,
                      NOW() + make_interval(secs => $6)
                    )
                    RETURNING id
                    """,
                    chat_id,
                    message_thread_id,
                    initiator_user_id,
                    target_user_id,
                    TRADE_STATUS_PENDING,
                    TRADE_PENDING_TTL_SECONDS,
                )
                trade_id = int(inserted["id"])
                try:
                    await conn.executemany(
                        """
                        INSERT INTO trade_user_links (user_id, trade_id)
                        VALUES ($1, $2)
                        """,
                        [
                            (initiator_user_id, trade_id),
                            (target_user_id, trade_id),
                        ],
                    )
                except asyncpg.UniqueViolationError as exc:
                    raise ShopError("Один из участников уже занят другим трейдом.") from exc
                trade = await self._fetch_trade_summary(conn, trade_id)

        logger.info(
            "trade_request_created",
            trade_id=trade.trade_id,
            initiator_telegram_id=initiator_telegram_id,
            target_telegram_id=target_telegram_id,
            chat_id=chat_id,
        )
        return trade

    async def attach_trade_request_message(self, trade_id: int, message_id: int) -> None:
        """Persist Telegram message id for a pending trade request."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE trade_sessions
                SET request_message_id = $2,
                    updated_at = NOW()
                WHERE id = $1
                """,
                trade_id,
                message_id,
            )

    async def accept_trade_request(self, trade_id: int, actor_telegram_id: int) -> TradeSessionSummary:
        """Accept a pending trade request as the targeted user."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                actor_user_id = await self._get_user_id_by_telegram_id(conn, actor_telegram_id)
                row = await conn.fetchrow(
                    """
                    SELECT *
                    FROM trade_sessions
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    trade_id,
                )
                if not row:
                    raise ShopError("Трейд не найден.")
                if str(row["status"]) != TRADE_STATUS_PENDING:
                    raise ShopError("Эта заявка уже не активна.")
                if int(row["target_user_id"]) != actor_user_id:
                    raise ShopError("Только второй участник может принять этот трейд.")
                if row["pending_expires_at"] is not None and _normalize_timestamp(row["pending_expires_at"]) <= datetime.now(UTC):
                    await self._close_trade(conn, trade_id, status=TRADE_STATUS_EXPIRED, cancel_reason="request_expired")
                    raise ShopError("Заявка на трейд уже истекла.")
                await conn.execute(
                    """
                    UPDATE trade_sessions
                    SET status = $2,
                        accepted_at = NOW(),
                        trade_expires_at = NOW() + make_interval(secs => $3),
                        active_message_id = COALESCE(active_message_id, request_message_id),
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    trade_id,
                    TRADE_STATUS_ACTIVE,
                    TRADE_ACTIVE_TTL_SECONDS,
                )
                trade = await self._fetch_trade_summary(conn, trade_id)
        logger.info("trade_request_accepted", trade_id=trade_id, actor_telegram_id=actor_telegram_id)
        return trade

    async def cancel_trade(
        self,
        trade_id: int,
        actor_telegram_id: int,
        *,
        cancel_reason: str = "canceled",
    ) -> TradeSessionSummary:
        """Cancel a pending or active trade as one of its participants."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                actor_user_id = await self._get_user_id_by_telegram_id(conn, actor_telegram_id)
                trade = await self._fetch_trade_summary(conn, trade_id)
                if actor_user_id not in {trade.initiator.user_id, trade.target.user_id}:
                    raise ShopError("Нельзя отменить чужой трейд.")
                if trade.status not in {TRADE_STATUS_PENDING, TRADE_STATUS_ACTIVE}:
                    raise ShopError("Этот трейд уже не активен.")
                await self._close_trade(conn, trade_id, status=TRADE_STATUS_CANCELED, cancel_reason=cancel_reason)
                closed = await self._fetch_trade_summary(conn, trade_id)
        logger.info("trade_canceled", trade_id=trade_id, actor_telegram_id=actor_telegram_id, cancel_reason=cancel_reason)
        return closed

    async def add_trade_offer_pokemon(
        self,
        *,
        telegram_id: int,
        username: Optional[str],
        user_pokemon_id: int,
    ) -> TradeSessionSummary:
        """Add one pokemon instance to the caller's active trade side."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._ensure_user(conn, telegram_id, username)
                user_id = await self._get_user_id_by_telegram_id(conn, telegram_id)
                trade_row = await self._fetch_active_trade_row_for_user(conn, user_id, for_update=True)
                trade_id = int(trade_row["id"])
                await self._ensure_trade_mutable(trade_row)
                offered_count = await conn.fetchval(
                    """
                    SELECT COUNT(*)::int
                    FROM trade_offer_items
                    WHERE trade_id = $1 AND user_id = $2
                    """,
                    trade_id,
                    user_id,
                )
                if int(offered_count or 0) >= TRADE_MAX_OFFERS_PER_SIDE:
                    raise ShopError(f"В одной стороне трейда можно держать максимум {TRADE_MAX_OFFERS_PER_SIDE} покемонов.")

                pokemon_row = await conn.fetchrow(
                    """
                    SELECT owner_user_id, is_locked, released_at
                    FROM user_pokemon
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    user_pokemon_id,
                )
                if not pokemon_row or int(pokemon_row["owner_user_id"]) != user_id:
                    raise ShopError("Нельзя добавить в трейд чужого покемона.")
                if pokemon_row["released_at"] is not None:
                    raise ShopError("Нельзя добавить в трейд отпущенного покемона.")
                if bool(pokemon_row["is_locked"]):
                    raise ShopError("Нельзя добавить в трейд заблокированного покемона.")
                if await self._is_user_pokemon_in_pvp_team(
                    conn,
                    user_id=user_id,
                    user_pokemon_id=user_pokemon_id,
                ):
                    raise ShopError("Сначала уберите этого покемона из боевой команды.")

                active_listing = await conn.fetchval(
                    """
                    SELECT 1
                    FROM market_listings
                    WHERE pokemon_instance_id = $1
                      AND status = $2
                    LIMIT 1
                    """,
                    user_pokemon_id,
                    MARKET_LISTING_STATUS_ACTIVE,
                )
                if active_listing:
                    raise ShopError("Сначала снимите этого покемона с рынка.")
                try:
                    await conn.execute(
                        """
                        INSERT INTO trade_offer_items (trade_id, user_id, user_pokemon_id)
                        VALUES ($1, $2, $3)
                        """,
                        trade_id,
                        user_id,
                        user_pokemon_id,
                    )
                except asyncpg.UniqueViolationError as exc:
                    raise ShopError("Этот покемон уже участвует в трейде.") from exc
                await conn.execute(
                    """
                    UPDATE trade_sessions
                    SET initiator_ready = FALSE,
                        target_ready = FALSE,
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    trade_id,
                )
                trade = await self._fetch_trade_summary(conn, trade_id)
        logger.info("trade_offer_added", trade_id=trade.trade_id, telegram_id=telegram_id, user_pokemon_id=user_pokemon_id)
        return trade

    async def remove_trade_offer_pokemon(
        self,
        *,
        telegram_id: int,
        username: Optional[str],
        user_pokemon_id: int,
    ) -> TradeSessionSummary:
        """Remove one pokemon instance from the caller's active trade side."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._ensure_user(conn, telegram_id, username)
                user_id = await self._get_user_id_by_telegram_id(conn, telegram_id)
                trade_row = await self._fetch_active_trade_row_for_user(conn, user_id, for_update=True)
                trade_id = int(trade_row["id"])
                await self._ensure_trade_mutable(trade_row)
                deleted = await conn.execute(
                    """
                    DELETE FROM trade_offer_items
                    WHERE trade_id = $1
                      AND user_id = $2
                      AND user_pokemon_id = $3
                    """,
                    trade_id,
                    user_id,
                    user_pokemon_id,
                )
                if deleted.endswith("0"):
                    raise ShopError("Этот покемон сейчас не добавлен в трейд.")
                await conn.execute(
                    """
                    UPDATE trade_sessions
                    SET initiator_ready = FALSE,
                        target_ready = FALSE,
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    trade_id,
                )
                trade = await self._fetch_trade_summary(conn, trade_id)
        logger.info("trade_offer_removed", trade_id=trade.trade_id, telegram_id=telegram_id, user_pokemon_id=user_pokemon_id)
        return trade

    async def toggle_trade_ready(
        self,
        *,
        telegram_id: int,
        username: Optional[str],
    ) -> TradeReadyToggleResult:
        """Toggle ready state and complete the trade when both are ready."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._ensure_user(conn, telegram_id, username)
                user_id = await self._get_user_id_by_telegram_id(conn, telegram_id)
                trade_row = await self._fetch_active_trade_row_for_user(conn, user_id, for_update=True)
                trade_id = int(trade_row["id"])
                if trade_row["trade_expires_at"] is not None and _normalize_timestamp(trade_row["trade_expires_at"]) <= datetime.now(UTC):
                    await self._close_trade(conn, trade_id, status=TRADE_STATUS_EXPIRED, cancel_reason="trade_expired")
                    raise ShopError("Этот трейд уже истёк.")

                is_initiator = int(trade_row["initiator_user_id"]) == user_id
                ready_column = "initiator_ready" if is_initiator else "target_ready"
                next_ready = not bool(trade_row[ready_column])
                await conn.execute(
                    f"""
                    UPDATE trade_sessions
                    SET {ready_column} = $2,
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    trade_id,
                    next_ready,
                )
                flags = await conn.fetchrow(
                    """
                    SELECT initiator_ready, target_ready
                    FROM trade_sessions
                    WHERE id = $1
                    """,
                    trade_id,
                )
                if bool(flags["initiator_ready"]) and bool(flags["target_ready"]):
                    before_complete = await self._fetch_trade_summary(conn, trade_id)
                    await self._complete_trade(conn, trade_id, before_complete)
                    before_complete.status = TRADE_STATUS_COMPLETED
                    before_complete.completed_at = datetime.now(UTC)
                    logger.info("trade_completed", trade_id=trade_id, telegram_id=telegram_id)
                    return TradeReadyToggleResult(trade=before_complete, completed=True)

                trade = await self._fetch_trade_summary(conn, trade_id)
        logger.info("trade_ready_toggled", trade_id=trade.trade_id, telegram_id=telegram_id, ready=next_ready)
        return TradeReadyToggleResult(trade=trade, completed=False)

    async def process_trade_maintenance(self) -> TradeMaintenanceResult:
        """Expire stale pending requests and active trades."""
        self._ensure_pool()
        expired_requests: list[TradeSessionSummary] = []
        expired_active_trades: list[TradeSessionSummary] = []
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                request_rows = await conn.fetch(
                    """
                    SELECT id
                    FROM trade_sessions
                    WHERE status = $1
                      AND pending_expires_at <= NOW()
                    FOR UPDATE
                    """,
                    TRADE_STATUS_PENDING,
                )
                for row in request_rows:
                    trade_id = int(row["id"])
                    expired_requests.append(await self._fetch_trade_summary(conn, trade_id))
                    await self._close_trade(conn, trade_id, status=TRADE_STATUS_EXPIRED, cancel_reason="request_expired")

                active_rows = await conn.fetch(
                    """
                    SELECT id
                    FROM trade_sessions
                    WHERE status = $1
                      AND trade_expires_at <= NOW()
                    FOR UPDATE
                    """,
                    TRADE_STATUS_ACTIVE,
                )
                for row in active_rows:
                    trade_id = int(row["id"])
                    expired_active_trades.append(await self._fetch_trade_summary(conn, trade_id))
                    await self._close_trade(conn, trade_id, status=TRADE_STATUS_EXPIRED, cancel_reason="trade_expired")

        return TradeMaintenanceResult(
            expired_requests=expired_requests,
            expired_active_trades=expired_active_trades,
        )

    async def note_chat_message(self, chat_id: int, message_thread_id: Optional[int]) -> Optional[ChatEncounter]:
        """Record one group-chat message and spawn an encounter if the threshold is reached."""
        self._ensure_pool()
        if self.redis is not None:
            cached_result = await self._note_chat_message_via_redis(chat_id)
            if cached_result == "cooldown":
                logger.info("chat_encounter_message_ignored", chat_id=chat_id, reason="redis_cooldown_not_ready")
                return None
            if cached_result == "active":
                logger.info("chat_encounter_message_ignored", chat_id=chat_id, reason="redis_active_encounter_exists")
                return None
            if isinstance(cached_result, int) and cached_result < CHAT_ENCOUNTER_MESSAGE_THRESHOLD:
                logger.info(
                    "chat_encounter_counter_incremented",
                    chat_id=chat_id,
                    messages_since_cooldown=cached_result,
                    threshold=CHAT_ENCOUNTER_MESSAGE_THRESHOLD,
                    source="redis",
                )
                return None

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._ensure_chat_encounter_state(conn, chat_id)
                state = await self._fetch_chat_encounter_state(conn, chat_id, for_update=True)
                now = datetime.now(UTC)
                logger.info(
                    "chat_encounter_message_seen",
                    chat_id=chat_id,
                    message_thread_id=message_thread_id,
                    active_encounter_id=state["active_encounter_id"],
                    messages_since_cooldown=int(state["messages_since_cooldown"]),
                    last_spawn_at=_normalize_timestamp(state["last_spawn_at"]).isoformat(),
                    now=now.isoformat(),
                )
                if await self._expire_active_chat_encounter_if_due(conn, chat_id, now):
                    state = await self._fetch_chat_encounter_state(conn, chat_id, for_update=True)
                    logger.info(
                        "chat_encounter_expired_during_message_check",
                        chat_id=chat_id,
                        active_encounter_id=state["active_encounter_id"],
                    )
                if state["active_encounter_id"] is not None:
                    await self._set_active_encounter_cache(chat_id, int(state["active_encounter_id"]))
                    await self._clear_encounter_counter_cache(chat_id)
                    logger.info(
                        "chat_encounter_message_ignored",
                        chat_id=chat_id,
                        reason="active_encounter_exists",
                        active_encounter_id=state["active_encounter_id"],
                    )
                    return None
                if not _chat_encounter_cooldown_ready(state["last_spawn_at"], now):
                    remaining_seconds = max(
                        0,
                        CHAT_ENCOUNTER_COOLDOWN_SECONDS
                        - int((now - _normalize_timestamp(state["last_spawn_at"])).total_seconds()),
                    )
                    await self._set_encounter_cooldown_cache(chat_id, remaining_seconds)
                    await self._clear_encounter_counter_cache(chat_id)
                    logger.info(
                        "chat_encounter_message_ignored",
                        chat_id=chat_id,
                        reason="cooldown_not_ready",
                        remaining_seconds=remaining_seconds,
                    )
                    return None

                message_count = int(state["messages_since_cooldown"]) + 1
                if message_count < CHAT_ENCOUNTER_MESSAGE_THRESHOLD:
                    await conn.execute(
                        """
                        UPDATE chat_encounter_state
                        SET messages_since_cooldown = $2,
                            updated_at = $3
                        WHERE chat_id = $1
                        """,
                        chat_id,
                        message_count,
                        now,
                    )
                    logger.info(
                        "chat_encounter_counter_incremented",
                        chat_id=chat_id,
                        messages_since_cooldown=message_count,
                        threshold=CHAT_ENCOUNTER_MESSAGE_THRESHOLD,
                    )
                    return None

                logger.info(
                    "chat_encounter_threshold_reached",
                    chat_id=chat_id,
                    messages_since_cooldown=message_count,
                    threshold=CHAT_ENCOUNTER_MESSAGE_THRESHOLD,
                )
                return await self._spawn_chat_encounter(conn, chat_id, message_thread_id, now)

    async def trigger_find_encounter(self, chat_id: int, message_thread_id: Optional[int]) -> Optional[ChatEncounter]:
        """Spawn an encounter via /find if the chat cooldown is ready."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._ensure_chat_encounter_state(conn, chat_id)
                state = await self._fetch_chat_encounter_state(conn, chat_id, for_update=True)
                now = datetime.now(UTC)
                if await self._expire_active_chat_encounter_if_due(conn, chat_id, now):
                    state = await self._fetch_chat_encounter_state(conn, chat_id, for_update=True)
                if state["active_encounter_id"] is not None:
                    await self._set_active_encounter_cache(chat_id, int(state["active_encounter_id"]))
                    return None
                if not _chat_encounter_cooldown_ready(state["last_spawn_at"], now):
                    remaining_seconds = max(
                        0,
                        CHAT_ENCOUNTER_COOLDOWN_SECONDS
                        - int((now - _normalize_timestamp(state["last_spawn_at"])).total_seconds()),
                    )
                    await self._set_encounter_cooldown_cache(chat_id, remaining_seconds)
                    return None

                return await self._spawn_chat_encounter(conn, chat_id, message_thread_id, now)

    async def attach_chat_encounter_message(self, encounter_id: int, encounter_message_id: int) -> None:
        """Attach the sent Telegram message id to an encounter."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE chat_encounters
                SET encounter_message_id = $2
                WHERE id = $1
                """,
                encounter_id,
                encounter_message_id,
            )

    async def cancel_chat_encounter(self, encounter_id: int) -> None:
        """Cancel an encounter if message delivery failed."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT id, chat_id
                    FROM chat_encounters
                    WHERE id = $1 AND status = 'active'
                    FOR UPDATE
                    """,
                    encounter_id,
                )
                if not row:
                    return
                await conn.execute(
                    """
                    UPDATE chat_encounters
                    SET status = 'cancelled',
                        resolved_at = $2
                    WHERE id = $1
                    """,
                    encounter_id,
                    datetime.now(UTC),
                )
                await conn.execute(
                    """
                    UPDATE chat_encounter_state
                    SET active_encounter_id = NULL,
                        updated_at = $2
                    WHERE chat_id = $1 AND active_encounter_id = $3
                    """,
                    int(row["chat_id"]),
                    datetime.now(UTC),
                    encounter_id,
                )
                await self._clear_active_encounter_cache(int(row["chat_id"]))

    async def get_active_chat_encounter(self, chat_id: int) -> Optional[ChatEncounter]:
        """Return the current active encounter for a chat, if any."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT ce.id, ce.chat_id, ce.message_thread_id, ce.encounter_message_id,
                       ce.pokemon_id, ce.spawned_at, ce.expires_at, ce.status,
                       ce.caught_by_user_id, ce.caught_user_pokemon_id, ce.caught_with_item_code,
                       pc.name, pc.rarity, pc.type, pc.image_credit_id
                FROM chat_encounters ce
                JOIN pokemon_catalog pc ON pc.id = ce.pokemon_id
                WHERE ce.chat_id = $1 AND ce.status = 'active'
                ORDER BY ce.spawned_at DESC
                LIMIT 1
                """,
                chat_id,
            )
        return _map_chat_encounter(row) if row else None

    async def expire_chat_encounter(self, encounter_id: int) -> Optional[ChatEncounter]:
        """Expire an active encounter and clear it from the chat state."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT ce.id, ce.chat_id, ce.message_thread_id, ce.encounter_message_id,
                           ce.pokemon_id, ce.spawned_at, ce.expires_at, ce.status,
                           ce.caught_by_user_id, ce.caught_user_pokemon_id, ce.caught_with_item_code,
                           pc.name, pc.rarity, pc.type, pc.image_credit_id
                    FROM chat_encounters ce
                    JOIN pokemon_catalog pc ON pc.id = ce.pokemon_id
                    WHERE ce.id = $1 AND ce.status = 'active'
                    FOR UPDATE
                    """,
                    encounter_id,
                )
                if not row:
                    return None

                now = datetime.now(UTC)
                await conn.execute(
                    """
                    UPDATE chat_encounters
                    SET status = 'expired',
                        resolved_at = $2
                    WHERE id = $1
                    """,
                    encounter_id,
                    now,
                )
                await conn.execute(
                    """
                    UPDATE chat_encounter_state
                    SET active_encounter_id = NULL,
                        messages_since_cooldown = 0,
                        updated_at = $2
                    WHERE chat_id = $1 AND active_encounter_id = $3
                    """,
                    int(row["chat_id"]),
                    now,
                    encounter_id,
                )
                await self._clear_active_encounter_cache(int(row["chat_id"]))
                return _map_chat_encounter(row)

    async def attempt_chat_encounter(
        self,
        chat_id: int,
        encounter_message_id: int,
        telegram_id: int,
        username: Optional[str],
        catcher_label: str,
        ball_code: str,
    ) -> ChatEncounterAttemptResult:
        """Attempt to catch the active encounter in a chat."""
        self._ensure_pool()
        if ball_code not in CHAT_ENCOUNTER_BALL_CATCH_CHANCES:
            raise ShopError(f"Unsupported encounter ball: {ball_code}")

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._ensure_chat_encounter_state(conn, chat_id)
                state = await self._fetch_chat_encounter_state(conn, chat_id, for_update=True)
                if state["active_encounter_id"] is None:
                    return ChatEncounterAttemptResult(status="missing", encounter=None)

                encounter_row = await conn.fetchrow(
                    """
                    SELECT ce.id, ce.chat_id, ce.message_thread_id, ce.encounter_message_id,
                           ce.pokemon_id, ce.spawned_at, ce.expires_at, ce.status,
                           ce.caught_by_user_id, ce.caught_user_pokemon_id, ce.caught_with_item_code,
                           pc.name, pc.rarity, pc.type, pc.image_credit_id
                    FROM chat_encounters ce
                    JOIN pokemon_catalog pc ON pc.id = ce.pokemon_id
                    WHERE ce.id = $1
                    FOR UPDATE
                    """,
                    int(state["active_encounter_id"]),
                )
                if not encounter_row or encounter_row["status"] != "active":
                    return ChatEncounterAttemptResult(status="missing", encounter=None)

                encounter = _map_chat_encounter(encounter_row)
                if encounter.encounter_message_id != encounter_message_id:
                    return ChatEncounterAttemptResult(status="stale", encounter=encounter)

                now = datetime.now(UTC)
                if encounter.expires_at <= now:
                    await conn.execute(
                        """
                        UPDATE chat_encounters
                        SET status = 'expired',
                            resolved_at = $2
                        WHERE id = $1
                        """,
                        encounter.encounter_id,
                        now,
                    )
                    await conn.execute(
                        """
                        UPDATE chat_encounter_state
                        SET active_encounter_id = NULL,
                            messages_since_cooldown = 0,
                            updated_at = $2
                        WHERE chat_id = $1 AND active_encounter_id = $3
                        """,
                        chat_id,
                        now,
                        encounter.encounter_id,
                    )
                    await self._clear_active_encounter_cache(chat_id)
                    return ChatEncounterAttemptResult(status="expired", encounter=encounter)

                user_id = await self._ensure_user(conn, telegram_id, username)
                attempted = await conn.fetchval(
                    """
                    SELECT 1
                    FROM chat_encounter_attempts
                    WHERE encounter_id = $1 AND user_id = $2
                    """,
                    encounter.encounter_id,
                    user_id,
                )
                if attempted:
                    return ChatEncounterAttemptResult(
                        status="already_attempted",
                        encounter=encounter,
                        ball_code=ball_code,
                        already_attempted=True,
                    )

                ball_consumed = False
                if ball_code in {ULTRABALL_CODE, MASTERBALL_CODE}:
                    await self._ensure_user_balance(conn, user_id, POKEDOLLAR_CODE)
                    item_row = await conn.fetchrow(
                        """
                        SELECT ui.quantity, i.id
                        FROM user_items ui
                        JOIN items i ON i.id = ui.item_id
                        WHERE ui.user_id = $1 AND i.code = $2
                        FOR UPDATE
                        """,
                        user_id,
                        ball_code,
                    )
                    if not item_row or int(item_row["quantity"]) <= 0:
                        return ChatEncounterAttemptResult(status="no_ball", encounter=encounter, ball_code=ball_code)
                    await conn.execute(
                        """
                        UPDATE user_items
                        SET quantity = quantity - 1
                        WHERE user_id = $1 AND item_id = $2
                        """,
                        user_id,
                        int(item_row["id"]),
                    )
                    ball_consumed = True

                caught = _roll_chat_encounter_catch(ball_code)
                await conn.execute(
                    """
                    INSERT INTO chat_encounter_attempts (encounter_id, user_id, ball_code, success)
                    VALUES ($1, $2, $3, $4)
                    """,
                    encounter.encounter_id,
                    user_id,
                    ball_code,
                    caught,
                )

                if not caught:
                    return ChatEncounterAttemptResult(
                        status="failed",
                        encounter=encounter,
                        caught=False,
                        ball_code=ball_code,
                        ball_consumed=ball_consumed,
                    )

                user_pokemon_id = await self._grant_pokemon_by_id(conn, user_id, encounter.pokemon_id)
                await conn.execute(
                    """
                    UPDATE chat_encounters
                    SET status = 'caught',
                        resolved_at = $2,
                        caught_by_user_id = $3,
                        caught_user_pokemon_id = $4,
                        caught_with_item_code = $5
                    WHERE id = $1
                    """,
                    encounter.encounter_id,
                    now,
                    user_id,
                    user_pokemon_id,
                    ball_code,
                )
                await conn.execute(
                    """
                    UPDATE chat_encounter_state
                    SET active_encounter_id = NULL,
                        messages_since_cooldown = 0,
                        updated_at = $2
                    WHERE chat_id = $1 AND active_encounter_id = $3
                    """,
                    chat_id,
                    now,
                    encounter.encounter_id,
                )
                await self._clear_active_encounter_cache(chat_id)
                return ChatEncounterAttemptResult(
                    status="caught",
                    encounter=ChatEncounter(
                        encounter_id=encounter.encounter_id,
                        chat_id=encounter.chat_id,
                        message_thread_id=encounter.message_thread_id,
                        encounter_message_id=encounter.encounter_message_id,
                        pokemon_id=encounter.pokemon_id,
                        name=encounter.name,
                        rarity=encounter.rarity,
                        pokemon_type=encounter.pokemon_type,
                        image_credit_id=encounter.image_credit_id,
                        spawned_at=encounter.spawned_at,
                        expires_at=encounter.expires_at,
                        status="caught",
                        caught_by_user_id=user_id,
                        caught_user_pokemon_id=user_pokemon_id,
                        caught_with_item_code=ball_code,
                    ),
                    caught=True,
                    ball_code=ball_code,
                    ball_consumed=ball_consumed,
                    catcher_user_id=user_id,
                    catcher_label=catcher_label,
                )

    async def get_chat_encounter(self, encounter_id: int) -> Optional[ChatEncounter]:
        """Load one encounter by id."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT ce.id, ce.chat_id, ce.message_thread_id, ce.encounter_message_id,
                       ce.pokemon_id, ce.spawned_at, ce.expires_at, ce.status,
                       ce.caught_by_user_id, ce.caught_user_pokemon_id, ce.caught_with_item_code,
                       pc.name, pc.rarity, pc.type, pc.image_credit_id
                FROM chat_encounters ce
                JOIN pokemon_catalog pc ON pc.id = ce.pokemon_id
                WHERE ce.id = $1
                """,
                encounter_id,
            )
        return _map_chat_encounter(row) if row else None

    async def get_user_pokemon_entry(self, user_pokemon_id: int) -> Optional[CollectionEntry]:
        """Load one owned pokemon instance as a card-ready entry."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                  pc.id AS pokemon_id,
                  up.id AS sample_user_pokemon_id,
                  pc.name,
                  pc.rarity,
                  pc.type,
                  pc.dex_form_code,
                  (
                    SELECT COUNT(*)
                    FROM user_pokemon up_count
                    WHERE up_count.owner_user_id = up.owner_user_id
                      AND up_count.pokemon_id = up.pokemon_id
                      AND up_count.released_at IS NULL
                  )::int AS quantity,
                  pc.base_hp,
                  pc.base_attack,
                  pc.base_defense,
                  pc.base_stamina,
                  pc.image_credit_id,
                  up.is_locked
                FROM user_pokemon up
                JOIN pokemon_catalog pc ON pc.id = up.pokemon_id
                WHERE up.id = $1
                  AND up.released_at IS NULL
                """,
                user_pokemon_id,
            )
        if not row:
            return None
        return CollectionEntry(
            pokemon_id=int(row["pokemon_id"]),
            sample_user_pokemon_id=int(row["sample_user_pokemon_id"]),
            name=str(row["name"]),
            rarity=str(row["rarity"]),
            pokemon_type=row["type"],
            quantity=int(row["quantity"]),
            base_hp=int(row["base_hp"]),
            base_attack=int(row["base_attack"]),
            base_defense=int(row["base_defense"]),
            base_stamina=int(row["base_stamina"]),
            image_credit_id=row["image_credit_id"],
            is_locked=bool(row["is_locked"]),
            dex_form_code=row["dex_form_code"],
            form_badge=_form_badge_from_dex_form_code(row["dex_form_code"]),
        )

    async def get_owned_user_pokemon_entry(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        user_pokemon_id: int,
    ) -> Optional[CollectionEntry]:
        """Load one owned pokemon instance for the current user only."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                row = await conn.fetchrow(
                    """
                    SELECT
                      pc.id AS pokemon_id,
                      up.id AS sample_user_pokemon_id,
                      pc.name,
                      pc.rarity,
                      pc.type,
                      pc.dex_form_code,
                      (
                        SELECT COUNT(*)
                        FROM user_pokemon up_count
                        WHERE up_count.owner_user_id = up.owner_user_id
                          AND up_count.pokemon_id = up.pokemon_id
                          AND up_count.released_at IS NULL
                      )::int AS quantity,
                      pc.base_hp,
                      pc.base_attack,
                      pc.base_defense,
                      pc.base_stamina,
                      pc.image_credit_id,
                      up.is_locked
                    FROM user_pokemon up
                    JOIN pokemon_catalog pc ON pc.id = up.pokemon_id
                    WHERE up.id = $1
                      AND up.owner_user_id = $2
                      AND up.released_at IS NULL
                    """,
                    user_pokemon_id,
                    user_id,
                )
        if not row:
            return None
        return CollectionEntry(
            pokemon_id=int(row["pokemon_id"]),
            sample_user_pokemon_id=int(row["sample_user_pokemon_id"]),
            name=str(row["name"]),
            rarity=str(row["rarity"]),
            pokemon_type=row["type"],
            quantity=int(row["quantity"]),
            base_hp=int(row["base_hp"]),
            base_attack=int(row["base_attack"]),
            base_defense=int(row["base_defense"]),
            base_stamina=int(row["base_stamina"]),
            image_credit_id=row["image_credit_id"],
            is_locked=bool(row["is_locked"]),
            dex_form_code=row["dex_form_code"],
            form_badge=_form_badge_from_dex_form_code(row["dex_form_code"]),
        )

    async def get_user_pokemon_instances_for_species(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        pokemon_id: int,
        limit: int = 12,
    ) -> list[CollectionEntry]:
        """Load explicit owned instances for one species to avoid ambiguous duplicate actions."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                rows = await conn.fetch(
                """
                SELECT
                  pc.id AS pokemon_id,
                  up.id AS sample_user_pokemon_id,
                  pc.name,
                  pc.rarity,
                  pc.type,
                  pc.dex_form_code,
                  COUNT(*) OVER (PARTITION BY up.owner_user_id, up.pokemon_id)::int AS quantity,
                  pc.base_hp,
                  pc.base_attack,
                  pc.base_defense,
                  pc.base_stamina,
                  pc.image_credit_id,
                      up.is_locked
                    FROM user_pokemon up
                    JOIN pokemon_catalog pc ON pc.id = up.pokemon_id
                    WHERE up.owner_user_id = $1
                      AND up.pokemon_id = $2
                      AND up.released_at IS NULL
                    ORDER BY up.is_locked ASC, up.id ASC
                    LIMIT $3
                    """,
                    user_id,
                    pokemon_id,
                    limit,
                )
        return [
            CollectionEntry(
                pokemon_id=int(row["pokemon_id"]),
                sample_user_pokemon_id=int(row["sample_user_pokemon_id"]),
                name=str(row["name"]),
                rarity=str(row["rarity"]),
                pokemon_type=row["type"],
                quantity=int(row["quantity"]),
                base_hp=int(row["base_hp"]),
                base_attack=int(row["base_attack"]),
                base_defense=int(row["base_defense"]),
                base_stamina=int(row["base_stamina"]),
                image_credit_id=row["image_credit_id"],
                is_locked=bool(row["is_locked"]),
                dex_form_code=row["dex_form_code"],
                form_badge=_form_badge_from_dex_form_code(row["dex_form_code"]),
            )
            for row in rows
        ]

    async def toggle_user_pokemon_lock(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        user_pokemon_id: int,
    ) -> PokemonLockResult:
        """Toggle lock state for one owned pokemon instance."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                row = await conn.fetchrow(
                    """
                    SELECT
                      up.id,
                      up.owner_user_id,
                      up.is_locked,
                      up.released_at,
                      pc.id AS pokemon_id,
                      pc.name,
                      pc.rarity
                    FROM user_pokemon up
                    JOIN pokemon_catalog pc ON pc.id = up.pokemon_id
                    WHERE up.id = $1
                    FOR UPDATE
                    """,
                    user_pokemon_id,
                )
                if not row or int(row["owner_user_id"]) != user_id:
                    raise ShopError("Нельзя изменить статус чужого покемона.")
                if row["released_at"] is not None:
                    raise ShopError("Нельзя изменить статус отпущенного покемона.")

                current_locked = bool(row["is_locked"])
                if not current_locked:
                    active_listing = await conn.fetchval(
                        """
                        SELECT 1
                        FROM market_listings
                        WHERE pokemon_instance_id = $1
                          AND status = $2
                        LIMIT 1
                        """,
                        user_pokemon_id,
                        MARKET_LISTING_STATUS_ACTIVE,
                    )
                    if active_listing:
                        raise ShopError("Сначала снимите покемона с рынка.")

                next_locked = not current_locked
                await conn.execute(
                    """
                    UPDATE user_pokemon
                    SET is_locked = $2
                    WHERE id = $1
                    """,
                    user_pokemon_id,
                    next_locked,
                )
        return PokemonLockResult(
            user_pokemon_id=int(row["id"]),
            pokemon_id=int(row["pokemon_id"]),
            name=str(row["name"]),
            rarity=str(row["rarity"]),
            is_locked=next_locked,
        )

    async def release_user_pokemon(
        self,
        telegram_id: int,
        username: Optional[str],
        *,
        user_pokemon_id: int,
    ) -> PokemonReleaseResult:
        """Release one owned unlocked pokemon and grant pokecoin by rarity."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                row = await conn.fetchrow(
                    """
                    SELECT
                      up.id,
                      up.owner_user_id,
                      up.is_locked,
                      up.released_at,
                      pc.id AS pokemon_id,
                      pc.name,
                      pc.rarity
                    FROM user_pokemon up
                    JOIN pokemon_catalog pc ON pc.id = up.pokemon_id
                    WHERE up.id = $1
                    FOR UPDATE
                    """,
                    user_pokemon_id,
                )
                if not row or int(row["owner_user_id"]) != user_id:
                    raise ShopError("Нельзя отпустить чужого покемона.")
                if row["released_at"] is not None:
                    raise ShopError("Этот покемон уже отпущен.")
                if bool(row["is_locked"]):
                    raise ShopError("Нельзя отпустить заблокированного покемона.")
                if await self._is_user_pokemon_in_pvp_team(
                    conn,
                    user_id=user_id,
                    user_pokemon_id=user_pokemon_id,
                ):
                    raise ShopError("Сначала уберите этого покемона из боевой команды.")

                active_listing = await conn.fetchval(
                    """
                    SELECT 1
                    FROM market_listings
                    WHERE pokemon_instance_id = $1
                      AND status = $2
                    LIMIT 1
                    """,
                    user_pokemon_id,
                    MARKET_LISTING_STATUS_ACTIVE,
                )
                if active_listing:
                    raise ShopError("Сначала снимите покемона с рынка.")

                rarity = str(row["rarity"])
                reward_amount = _pokemon_release_reward(rarity)
                await self._ensure_user_balance(conn, user_id, POKECOIN_CODE)
                await self._adjust_balance(conn, user_id, POKECOIN_CODE, reward_amount)
                await conn.execute(
                    """
                    UPDATE user_pokemon
                    SET released_at = NOW()
                    WHERE id = $1
                    """,
                    user_pokemon_id,
                )

        logger.info(
            "pokemon_released",
            telegram_id=telegram_id,
            user_pokemon_id=user_pokemon_id,
            pokemon_id=int(row["pokemon_id"]),
            rarity=rarity,
            reward_amount=reward_amount,
        )
        return PokemonReleaseResult(
            user_pokemon_id=user_pokemon_id,
            pokemon_id=int(row["pokemon_id"]),
            name=str(row["name"]),
            rarity=rarity,
            reward_amount=reward_amount,
        )

    async def claim_daily_bonus(self, telegram_id: int, username: Optional[str]) -> BonusClaimResult:
        """Claim the accumulated daily bonus if it is ready."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                state = await self._fetch_shop_state_row(conn, user_id, for_update=True)
                now = datetime.now(UTC)
                amount = _calculate_bonus_amount(state["bonus_last_claim_at"], now)
                if amount < SHOP_BONUS_RATE_PER_HOUR:
                    raise BonusNotReadyError(
                        remaining_seconds=_bonus_remaining_seconds(state["bonus_last_claim_at"], now)
                    )

                await self._adjust_balance(conn, user_id, POKEDOLLAR_CODE, amount)
                await conn.execute(
                    """
                    UPDATE user_shop_state
                    SET bonus_last_claim_at = $2,
                        updated_at = $2
                    WHERE user_id = $1
                    """,
                    user_id,
                    now,
                )
                shop_view = await self._fetch_shop_view(conn, user_id)

        logger.info("shop_bonus_claimed", telegram_id=telegram_id, amount=amount)
        return BonusClaimResult(
            amount_claimed=amount,
            next_bonus_in_seconds=SHOP_BONUS_CLAIM_INTERVAL_SECONDS,
            shop_view=shop_view,
        )

    async def purchase_item(
        self, telegram_id: int, username: Optional[str], item_code: str
    ) -> ItemPurchaseResult:
        """Purchase one shop item."""
        self._ensure_pool()
        if item_code not in {"ultraball", "masterball"}:
            raise ShopError(f"Unsupported item: {item_code}")

        item_price = ULTRABALL_PRICE if item_code == "ultraball" else MASTERBALL_PRICE
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                await self._ensure_user_balance(conn, user_id, POKEDOLLAR_CODE)
                await self._ensure_shop_state(conn, user_id)
                balance = await self._get_balance_for_update(conn, user_id, POKEDOLLAR_CODE)
                if balance < item_price:
                    raise InsufficientFundsError("Not enough pokedollar")

                item_row = await conn.fetchrow(
                    "SELECT id, name FROM items WHERE code = $1",
                    item_code,
                )
                if not item_row:
                    raise ShopError(f"Item seed missing for {item_code}")

                await conn.execute(
                    """
                    UPDATE user_balances
                    SET amount = amount - $3
                    WHERE user_id = $1 AND currency_id = $2
                    """,
                    user_id,
                    await self._get_currency_id(conn, POKEDOLLAR_CODE),
                    item_price,
                )
                await conn.execute(
                    """
                    INSERT INTO user_items (user_id, item_id, quantity)
                    VALUES ($1, $2, 1)
                    ON CONFLICT (user_id, item_id)
                    DO UPDATE SET quantity = user_items.quantity + 1
                    """,
                    user_id,
                    int(item_row["id"]),
                )
                quantity_after = await conn.fetchval(
                    "SELECT quantity FROM user_items WHERE user_id = $1 AND item_id = $2",
                    user_id,
                    int(item_row["id"]),
                )
                shop_view = await self._fetch_shop_view(conn, user_id)

        logger.info(
            "shop_item_purchased",
            telegram_id=telegram_id,
            item_code=item_code,
            price=item_price,
        )
        return ItemPurchaseResult(
            item_code=item_code,
            item_name=str(item_row["name"]),
            item_price=item_price,
            quantity_after=int(quantity_after),
            shop_view=shop_view,
        )

    async def spin_gacha(
        self, telegram_id: int, username: Optional[str], spin_count: int
    ) -> SpinResult:
        """Perform one or multiple gacha spins."""
        self._ensure_pool()
        if spin_count not in {1, 5}:
            raise ShopError("Only x1 and x5 spins are supported")

        total_cost = SPIN_PRICE * spin_count
        rewards: list[PokemonReward] = []

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                await self._ensure_user_balance(conn, user_id, POKEDOLLAR_CODE)
                state = await self._fetch_shop_state_row(conn, user_id, for_update=True)
                balance = await self._get_balance_for_update(conn, user_id, POKEDOLLAR_CODE)
                if balance < total_cost:
                    raise InsufficientFundsError("Not enough pokedollar")

                await conn.execute(
                    """
                    UPDATE user_balances
                    SET amount = amount - $3
                    WHERE user_id = $1 AND currency_id = $2
                    """,
                    user_id,
                    await self._get_currency_id(conn, POKEDOLLAR_CODE),
                    total_cost,
                )

                epic_counter = int(state["epic_pity_counter"])
                legendary_counter = int(state["legendary_pity_counter"])
                for _ in range(spin_count):
                    reward = await self._draw_pokemon_reward(conn, user_id, epic_counter, legendary_counter)
                    rewards.append(reward)
                    epic_counter, legendary_counter = _update_pity_counters(
                        reward.rarity,
                        epic_counter,
                        legendary_counter,
                    )

                await conn.execute(
                    """
                    UPDATE user_shop_state
                    SET epic_pity_counter = $2,
                        legendary_pity_counter = $3,
                        updated_at = $4
                    WHERE user_id = $1
                    """,
                    user_id,
                    epic_counter,
                    legendary_counter,
                    datetime.now(UTC),
                )
                shop_view = await self._fetch_shop_view(conn, user_id)

        logger.info(
            "shop_spin_completed",
            telegram_id=telegram_id,
            spin_count=spin_count,
            spent_amount=total_cost,
            rewards=[reward.rarity for reward in rewards],
        )
        return SpinResult(rewards=rewards, spent_amount=total_cost, shop_view=shop_view)

    async def _get_linked_trade_id(self, conn: asyncpg.Connection, user_id: int) -> Optional[int]:
        trade_id = await conn.fetchval(
            """
            SELECT trade_id
            FROM trade_user_links
            WHERE user_id = $1
            """,
            user_id,
        )
        return int(trade_id) if trade_id is not None else None

    async def _ensure_trade_user_available(
        self,
        conn: asyncpg.Connection,
        user_id: int,
        *,
        own_message: str,
    ) -> None:
        linked_trade_id = await self._get_linked_trade_id(conn, user_id)
        if linked_trade_id is not None:
            raise ShopError(own_message)

    async def _fetch_active_trade_row_for_user(
        self,
        conn: asyncpg.Connection,
        user_id: int,
        *,
        for_update: bool = False,
    ) -> asyncpg.Record:
        lock_clause = " FOR UPDATE" if for_update else ""
        row = await conn.fetchrow(
            (
                """
                SELECT ts.*
                FROM trade_user_links tul
                JOIN trade_sessions ts ON ts.id = tul.trade_id
                WHERE tul.user_id = $1
                  AND ts.status = $2
                """
                + lock_clause
            ),
            user_id,
            TRADE_STATUS_ACTIVE,
        )
        if not row:
            raise ShopError("У вас нет активного трейда.")
        return row

    async def _ensure_trade_mutable(self, trade_row: asyncpg.Record) -> None:
        if str(trade_row["status"]) != TRADE_STATUS_ACTIVE:
            raise ShopError("Этот трейд уже не активен.")
        if bool(trade_row["initiator_ready"]) or bool(trade_row["target_ready"]):
            raise ShopError("Нельзя менять состав трейда, пока кто-то в статусе готов.")
        expires_at = trade_row["trade_expires_at"]
        if expires_at is not None and _normalize_timestamp(expires_at) <= datetime.now(UTC):
            raise ShopError("Этот трейд уже истёк.")

    async def _fetch_trade_summary(self, conn: asyncpg.Connection, trade_id: int) -> TradeSessionSummary:
        row = await conn.fetchrow(
            """
            SELECT
              ts.id,
              ts.chat_id,
              ts.message_thread_id,
              ts.request_message_id,
              ts.active_message_id,
              ts.status,
              ts.pending_expires_at,
              ts.trade_expires_at,
              ts.created_at,
              ts.accepted_at,
              ts.canceled_at,
              ts.completed_at,
              ts.cancel_reason,
              ts.initiator_user_id,
              ts.target_user_id,
              ts.initiator_ready,
              ts.target_ready,
              iu.tg_user_id AS initiator_tg_user_id,
              iu.tg_username AS initiator_tg_username,
              iu.nickname AS initiator_nickname,
              tu.tg_user_id AS target_tg_user_id,
              tu.tg_username AS target_tg_username,
              tu.nickname AS target_nickname
            FROM trade_sessions ts
            JOIN users iu ON iu.id = ts.initiator_user_id
            JOIN users tu ON tu.id = ts.target_user_id
            WHERE ts.id = $1
            """,
            trade_id,
        )
        if not row:
            raise ShopError("Трейд не найден.")

        offer_rows = await conn.fetch(
            """
            SELECT
              toi.user_id,
              toi.user_pokemon_id,
              pc.id AS pokemon_id,
              pc.name,
              pc.rarity,
              pc.dex_form_code
            FROM trade_offer_items toi
            JOIN user_pokemon up ON up.id = toi.user_pokemon_id
            JOIN pokemon_catalog pc ON pc.id = up.pokemon_id
            WHERE toi.trade_id = $1
            ORDER BY toi.created_at ASC, toi.user_pokemon_id ASC
            """,
            trade_id,
        )

        initiator_offers: list[TradeOfferLine] = []
        target_offers: list[TradeOfferLine] = []
        initiator_user_id = int(row["initiator_user_id"])
        target_user_id = int(row["target_user_id"])
        for offer in offer_rows:
            line = TradeOfferLine(
                user_pokemon_id=int(offer["user_pokemon_id"]),
                pokemon_id=int(offer["pokemon_id"]),
                name=str(offer["name"]),
                rarity=str(offer["rarity"]),
                dex_form_code=offer["dex_form_code"],
                form_badge=_form_badge_from_dex_form_code(offer["dex_form_code"]),
            )
            if int(offer["user_id"]) == initiator_user_id:
                initiator_offers.append(line)
            else:
                target_offers.append(line)

        initiator = TradeParticipantState(
            user_id=initiator_user_id,
            telegram_id=int(row["initiator_tg_user_id"]),
            username=row["initiator_tg_username"],
            nickname=row["initiator_nickname"],
            label=_resolve_trade_user_label(row["initiator_nickname"], row["initiator_tg_username"], int(row["initiator_tg_user_id"])),
            is_ready=bool(row["initiator_ready"]),
            offers=initiator_offers,
        )
        target = TradeParticipantState(
            user_id=target_user_id,
            telegram_id=int(row["target_tg_user_id"]),
            username=row["target_tg_username"],
            nickname=row["target_nickname"],
            label=_resolve_trade_user_label(row["target_nickname"], row["target_tg_username"], int(row["target_tg_user_id"])),
            is_ready=bool(row["target_ready"]),
            offers=target_offers,
        )
        return TradeSessionSummary(
            trade_id=int(row["id"]),
            chat_id=int(row["chat_id"]),
            message_thread_id=row["message_thread_id"],
            request_message_id=row["request_message_id"],
            active_message_id=row["active_message_id"],
            status=str(row["status"]),
            pending_expires_at=_normalize_optional_timestamp(row["pending_expires_at"]),
            trade_expires_at=_normalize_optional_timestamp(row["trade_expires_at"]),
            created_at=_normalize_timestamp(row["created_at"]),
            accepted_at=_normalize_optional_timestamp(row["accepted_at"]),
            canceled_at=_normalize_optional_timestamp(row["canceled_at"]),
            completed_at=_normalize_optional_timestamp(row["completed_at"]),
            cancel_reason=row["cancel_reason"],
            initiator=initiator,
            target=target,
        )

    async def _close_trade(
        self,
        conn: asyncpg.Connection,
        trade_id: int,
        *,
        status: str,
        cancel_reason: Optional[str] = None,
    ) -> None:
        should_mark_canceled = status in {
            TRADE_STATUS_CANCELED,
            TRADE_STATUS_REJECTED,
            TRADE_STATUS_EXPIRED,
        }
        await conn.execute(
            """
            UPDATE trade_sessions
            SET status = $2,
                cancel_reason = $3,
                canceled_at = CASE
                  WHEN $4 THEN NOW()
                  ELSE canceled_at
                END,
                updated_at = NOW()
            WHERE id = $1
            """,
            trade_id,
            status,
            cancel_reason,
            should_mark_canceled,
        )
        await conn.execute("DELETE FROM trade_offer_items WHERE trade_id = $1", trade_id)
        await conn.execute("DELETE FROM trade_user_links WHERE trade_id = $1", trade_id)

    async def _complete_trade(
        self,
        conn: asyncpg.Connection,
        trade_id: int,
        summary: TradeSessionSummary,
    ) -> None:
        offer_rows = await conn.fetch(
            """
            SELECT
              toi.user_id,
              toi.user_pokemon_id,
              up.owner_user_id,
              up.is_locked,
              up.released_at
            FROM trade_offer_items toi
            JOIN user_pokemon up ON up.id = toi.user_pokemon_id
            WHERE toi.trade_id = $1
            ORDER BY toi.created_at ASC, toi.user_pokemon_id ASC
            FOR UPDATE OF up, toi
            """,
            trade_id,
        )
        initiator_ids = {offer.user_pokemon_id for offer in summary.initiator.offers}
        target_ids = {offer.user_pokemon_id for offer in summary.target.offers}
        valid_ids = initiator_ids | target_ids
        if valid_ids != {int(row["user_pokemon_id"]) for row in offer_rows}:
            raise ShopError("Состав трейда устарел. Откройте его заново.")
        for row in offer_rows:
            owner_user_id = int(row["owner_user_id"])
            user_pokemon_id = int(row["user_pokemon_id"])
            if user_pokemon_id in initiator_ids and owner_user_id != summary.initiator.user_id:
                raise ShopError("Один из ваших покемонов больше вам не принадлежит.")
            if user_pokemon_id in target_ids and owner_user_id != summary.target.user_id:
                raise ShopError("Один из покемонов второй стороны больше ей не принадлежит.")
            if row["released_at"] is not None or bool(row["is_locked"]):
                raise ShopError("Один из покемонов больше недоступен для трейда.")
            active_listing = await conn.fetchval(
                """
                SELECT 1
                FROM market_listings
                WHERE pokemon_instance_id = $1
                  AND status = $2
                LIMIT 1
                """,
                user_pokemon_id,
                MARKET_LISTING_STATUS_ACTIVE,
            )
            if active_listing:
                raise ShopError("Один из покемонов уже выставлен на рынок.")

        if initiator_ids:
            await conn.execute(
                """
                UPDATE user_pokemon
                SET owner_user_id = $2
                WHERE id = ANY($1::bigint[])
                """,
                list(initiator_ids),
                summary.target.user_id,
            )
        if target_ids:
            await conn.execute(
                """
                UPDATE user_pokemon
                SET owner_user_id = $2
                WHERE id = ANY($1::bigint[])
                """,
                list(target_ids),
                summary.initiator.user_id,
            )
        await conn.execute(
            """
            UPDATE trade_sessions
            SET status = $2,
                completed_at = NOW(),
                updated_at = NOW()
            WHERE id = $1
            """,
            trade_id,
            TRADE_STATUS_COMPLETED,
        )
        await conn.execute("DELETE FROM trade_offer_items WHERE trade_id = $1", trade_id)
        await conn.execute("DELETE FROM trade_user_links WHERE trade_id = $1", trade_id)

    def _ensure_pool(self) -> None:
        if not self.pool:
            raise ShopUnavailableError("Database is not connected")

    async def _ensure_user(
        self, conn: asyncpg.Connection, telegram_id: int, username: Optional[str]
    ) -> int:
        row = await conn.fetchrow(
            """
            WITH upserted_user AS (
                INSERT INTO users (tg_user_id, tg_username, nickname)
                VALUES ($1, $2, $2)
                ON CONFLICT (tg_user_id)
                DO UPDATE SET
                    tg_username = COALESCE(EXCLUDED.tg_username, users.tg_username),
                    nickname = COALESCE(users.nickname, EXCLUDED.nickname)
                RETURNING id
            ),
            ensured_settings AS (
                INSERT INTO user_settings (user_id)
                SELECT id FROM upserted_user
                ON CONFLICT (user_id) DO NOTHING
            ),
            ensured_shop_state AS (
                INSERT INTO user_shop_state (user_id, bonus_last_claim_at)
                SELECT id, NOW() - make_interval(secs => $5) FROM upserted_user
                ON CONFLICT (user_id) DO NOTHING
            ),
            ensured_balance AS (
                INSERT INTO user_balances (user_id, currency_id, amount)
                SELECT upserted_user.id, currencies.id, $4
                FROM upserted_user
                JOIN currencies ON currencies.code = $3
                ON CONFLICT (user_id, currency_id) DO NOTHING
            )
            SELECT id FROM upserted_user;
            """,
            telegram_id,
            username,
            POKEDOLLAR_CODE,
            WELCOME_POKEDOLLAR_AMOUNT,
            SHOP_BONUS_CAP_SECONDS,
        )
        if not row:
            raise ShopError("Unable to ensure user record")
        return int(row["id"])

    async def _get_user_id_by_telegram_id(self, conn: asyncpg.Connection, telegram_id: int) -> int:
        user_id = await conn.fetchval(
            """
            SELECT id
            FROM users
            WHERE tg_user_id = $1
            ORDER BY id ASC
            LIMIT 1
            """,
            telegram_id,
        )
        if user_id is None:
            raise ShopError("Профиль пользователя не найден.")
        return int(user_id)

    async def _ensure_shop_state(self, conn: asyncpg.Connection, user_id: int) -> None:
        await conn.execute(
            """
            INSERT INTO user_shop_state (user_id, bonus_last_claim_at)
            VALUES ($1, NOW() - make_interval(secs => $2))
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
            SHOP_BONUS_CAP_SECONDS,
        )

    async def _ensure_user_balance(
        self, conn: asyncpg.Connection, user_id: int, currency_code: str
    ) -> None:
        await conn.execute(
            """
            INSERT INTO user_balances (user_id, currency_id, amount)
            VALUES ($1, $2, 0)
            ON CONFLICT (user_id, currency_id) DO NOTHING
            """,
            user_id,
            await self._get_currency_id(conn, currency_code),
        )

    async def _get_currency_id(self, conn: asyncpg.Connection, code: str) -> int:
        currency_id = await conn.fetchval("SELECT id FROM currencies WHERE code = $1", code)
        if currency_id is None:
            raise ShopError(f"Currency seed missing for {code}")
        return int(currency_id)

    async def _fetch_shop_state_row(
        self, conn: asyncpg.Connection, user_id: int, *, for_update: bool = False
    ) -> asyncpg.Record:
        await self._ensure_shop_state(conn, user_id)
        lock_clause = " FOR UPDATE" if for_update else ""
        row = await conn.fetchrow(
            (
                "SELECT user_id, bonus_last_claim_at, epic_pity_counter, legendary_pity_counter "
                "FROM user_shop_state WHERE user_id = $1" + lock_clause
            ),
            user_id,
        )
        if not row:
            raise ShopError("Shop state is missing")
        return row

    async def _fetch_shop_view(self, conn: asyncpg.Connection, user_id: int) -> ShopView:
        await self._ensure_shop_state(conn, user_id)
        await self._ensure_user_balance(conn, user_id, POKEDOLLAR_CODE)
        row = await conn.fetchrow(
            """
            SELECT
              uss.user_id,
              uss.bonus_last_claim_at,
              uss.epic_pity_counter,
              uss.legendary_pity_counter,
              COALESCE((
                SELECT ub.amount
                FROM user_balances ub
                JOIN currencies c ON c.id = ub.currency_id
                WHERE ub.user_id = uss.user_id AND c.code = 'pokedollar'
              ), 0) AS balance,
              COALESCE((
                SELECT ub.amount
                FROM user_balances ub
                JOIN currencies c ON c.id = ub.currency_id
                WHERE ub.user_id = uss.user_id AND c.code = 'pokecoin'
              ), 0) AS pokecoin_balance,
              COALESCE((
                SELECT ui.quantity
                FROM user_items ui
                JOIN items i ON i.id = ui.item_id
                WHERE ui.user_id = uss.user_id AND i.code = 'ultraball'
              ), 0) AS ultraball_quantity,
              COALESCE((
                SELECT ui.quantity
                FROM user_items ui
                JOIN items i ON i.id = ui.item_id
                WHERE ui.user_id = uss.user_id AND i.code = 'masterball'
              ), 0) AS masterball_quantity
            FROM user_shop_state uss
            WHERE uss.user_id = $1
            """,
            user_id,
        )
        if not row:
            raise ShopError("Unable to fetch shop view")

        now = datetime.now(UTC)
        bonus_available = _calculate_bonus_amount(row["bonus_last_claim_at"], now)
        bonus_ready_in_seconds = _bonus_remaining_seconds(row["bonus_last_claim_at"], now)
        return ShopView(
            user_id=int(row["user_id"]),
            balance=int(row["balance"]),
            pokecoin_balance=int(row["pokecoin_balance"]),
            ultraball_quantity=int(row["ultraball_quantity"]),
            masterball_quantity=int(row["masterball_quantity"]),
            epic_pity_counter=int(row["epic_pity_counter"]),
            legendary_pity_counter=int(row["legendary_pity_counter"]),
            bonus_available=bonus_available,
            bonus_ready_in_seconds=bonus_ready_in_seconds,
        )

    async def _get_balance_for_update(
        self, conn: asyncpg.Connection, user_id: int, currency_code: str
    ) -> int:
        row = await conn.fetchrow(
            """
            SELECT ub.amount
            FROM user_balances ub
            JOIN currencies c ON c.id = ub.currency_id
            WHERE ub.user_id = $1 AND c.code = $2
            FOR UPDATE
            """,
            user_id,
            currency_code,
        )
        if not row:
            return 0
        return int(row["amount"])

    async def _get_balance(
        self, conn: asyncpg.Connection, user_id: int, currency_code: str
    ) -> int:
        row = await conn.fetchrow(
            """
            SELECT ub.amount
            FROM user_balances ub
            JOIN currencies c ON c.id = ub.currency_id
            WHERE ub.user_id = $1 AND c.code = $2
            """,
            user_id,
            currency_code,
        )
        if not row:
            return 0
        return int(row["amount"])

    async def _adjust_balance(
        self, conn: asyncpg.Connection, user_id: int, currency_code: str, delta: int
    ) -> None:
        await self._ensure_user_balance(conn, user_id, currency_code)
        await conn.execute(
            """
            UPDATE user_balances
            SET amount = amount + $3
            WHERE user_id = $1 AND currency_id = $2
            """,
            user_id,
            await self._get_currency_id(conn, currency_code),
            delta,
        )

    async def _draw_pokemon_reward(
        self,
        conn: asyncpg.Connection,
        user_id: int,
        epic_counter: int,
        legendary_counter: int,
    ) -> PokemonReward:
        reward_rarity = _resolve_roll_rarity(epic_counter, legendary_counter)
        base_pokemon_row = await self._select_random_base_pokemon(conn, reward_rarity)
        pokemon_row = await self._select_encounter_overlay_variant(conn, base_pokemon_row=base_pokemon_row)
        inserted = await conn.fetchrow(
            """
            INSERT INTO user_pokemon (owner_user_id, pokemon_id)
            VALUES ($1, $2)
            RETURNING id
            """,
            user_id,
            int(pokemon_row["id"]),
        )
        return PokemonReward(
            user_pokemon_id=int(inserted["id"]),
            pokemon_id=int(pokemon_row["id"]),
            dex_form_code=pokemon_row["dex_form_code"],
            name=str(pokemon_row["name"]),
            rarity=str(pokemon_row["rarity"]),
            pokemon_type=pokemon_row["type"],
            base_hp=int(pokemon_row["base_hp"]),
            base_attack=int(pokemon_row["base_attack"]),
            base_defense=int(pokemon_row["base_defense"]),
            base_stamina=int(pokemon_row["base_stamina"]),
            image_credit_id=pokemon_row["image_credit_id"],
            form_badge=_form_badge_from_dex_form_code(pokemon_row["dex_form_code"]),
        )

    async def _select_random_pokemon(
        self, conn: asyncpg.Connection, target_rarity: str
    ) -> asyncpg.Record:
        rarities = _rarity_pool_for_target(target_rarity)
        row = await conn.fetchrow(
            """
            SELECT id, dex_form_code, name, type, rarity, base_hp, base_attack, base_defense, base_stamina, image_credit_id
            FROM pokemon_catalog
            WHERE rarity = ANY($1::text[])
            ORDER BY random()
            LIMIT 1
            """,
            list(rarities),
        )
        if not row:
            raise ShopError(f"No pokemon found for rarity pool {rarities}")
        return row

    async def _select_random_base_pokemon(
        self,
        conn: asyncpg.Connection,
        target_rarity: str,
    ) -> asyncpg.Record:
        """Select one random base-form pokemon for encounter overlays."""
        rarities = _rarity_pool_for_target(target_rarity)
        row = await conn.fetchrow(
            """
            SELECT id, dex_form_code, name, type, rarity, base_hp, base_attack, base_defense, base_stamina, image_credit_id
            FROM pokemon_catalog
            WHERE rarity = ANY($1::text[])
              AND COALESCE(dex_form_code, id::text) NOT LIKE '%-%'
            ORDER BY random()
            LIMIT 1
            """,
            list(rarities),
        )
        if not row:
            raise ShopError(f"No base pokemon found for rarity pool {rarities}")
        return row

    async def _select_encounter_overlay_variant(
        self,
        conn: asyncpg.Connection,
        *,
        base_pokemon_row: asyncpg.Record,
    ) -> asyncpg.Record:
        """Resolve optional shiny/mega/gigantamax overlay for one base encounter species."""
        base_form_code = _base_dex_from_form_code(base_pokemon_row["dex_form_code"]) or str(base_pokemon_row["id"])
        rows = await conn.fetch(
            """
            SELECT id, dex_form_code, name, type, rarity, base_hp, base_attack, base_defense, base_stamina, image_credit_id
            FROM pokemon_catalog
            WHERE split_part(COALESCE(dex_form_code, id::text), '-', 1) = $1
            """,
            base_form_code,
        )
        if not rows:
            return base_pokemon_row

        variants_by_kind = {
            _form_kind_from_dex_form_code(row["dex_form_code"]): row
            for row in rows
        }
        selected_kind = _choose_form_overlay_kind(tuple(variants_by_kind.keys()))
        return variants_by_kind.get(selected_kind, variants_by_kind.get(FORM_KIND_BASE, base_pokemon_row))

    async def _grant_pokemon_by_id(
        self,
        conn: asyncpg.Connection,
        user_id: int,
        pokemon_id: int,
    ) -> int:
        inserted = await conn.fetchrow(
            """
            INSERT INTO user_pokemon (owner_user_id, pokemon_id)
            VALUES ($1, $2)
            RETURNING id
            """,
            user_id,
            pokemon_id,
        )
        return int(inserted["id"])

    async def _fetch_collection_page(
        self,
        conn: asyncpg.Connection,
        user_id: int,
        filter_state: CollectionFilterState,
    ) -> CollectionPage:
        mini_page = await self._fetch_collection_page_with_page_size(
            conn,
            user_id,
            filter_state,
            page_size=COLLECTION_PAGE_SIZE,
        )
        return CollectionPage(
            entries=mini_page.entries,
            filter_state=mini_page.filter_state,
            total_entries=mini_page.total_entries,
            current_page=mini_page.current_page,
            total_pages=mini_page.total_pages,
        )

    async def _fetch_collection_page_with_page_size(
        self,
        conn: asyncpg.Connection,
        user_id: int,
        filter_state: CollectionFilterState,
        *,
        page_size: int,
    ) -> MiniAppCollectionPage:
        current_page = max(1, filter_state.page)
        resolved_page_size = max(1, min(page_size, 100))
        offset = (current_page - 1) * resolved_page_size

        where_sql, having_sql, params = _build_collection_filter_clauses(user_id, filter_state)
        count_sql = f"""
            SELECT COUNT(*)::int AS total_entries
            FROM (
              SELECT pc.id
              FROM user_pokemon up
              JOIN pokemon_catalog pc ON pc.id = up.pokemon_id
              {where_sql}
              GROUP BY pc.id
              {having_sql}
            ) filtered_species
        """
        total_entries = int(await conn.fetchval(count_sql, *params) or 0)
        total_pages = max(1, (total_entries + resolved_page_size - 1) // resolved_page_size)
        current_page = min(current_page, total_pages)
        offset = (current_page - 1) * resolved_page_size

        data_params = [*params, resolved_page_size, offset]
        limit_index = len(params) + 1
        offset_index = len(params) + 2
        rows = await conn.fetch(
            f"""
            SELECT
              pc.id AS pokemon_id,
              MIN(up.id) AS sample_user_pokemon_id,
              pc.name,
              pc.rarity,
              pc.type,
              pc.dex_form_code,
              COUNT(*)::int AS quantity,
              pc.base_hp,
              pc.base_attack,
              pc.base_defense,
              pc.base_stamina,
              pc.image_credit_id
            FROM user_pokemon up
            JOIN pokemon_catalog pc ON pc.id = up.pokemon_id
            {where_sql}
            GROUP BY
              pc.id,
              pc.name,
              pc.rarity,
              pc.type,
              pc.dex_form_code,
              pc.base_hp,
              pc.base_attack,
              pc.base_defense,
              pc.base_stamina,
              pc.image_credit_id
            {having_sql}
            ORDER BY {_dex_form_sort_sql(qualified_column="pc.dex_form_code")}
            LIMIT ${limit_index}
            OFFSET ${offset_index}
            """,
            *data_params,
        )
        entries = [
            CollectionEntry(
                pokemon_id=int(row["pokemon_id"]),
                sample_user_pokemon_id=int(row["sample_user_pokemon_id"]),
                name=str(row["name"]),
                rarity=str(row["rarity"]),
                pokemon_type=row["type"],
                quantity=int(row["quantity"]),
                base_hp=int(row["base_hp"]),
                base_attack=int(row["base_attack"]),
                base_defense=int(row["base_defense"]),
                base_stamina=int(row["base_stamina"]),
                image_credit_id=row["image_credit_id"],
                dex_form_code=row["dex_form_code"],
                form_badge=_form_badge_from_dex_form_code(row["dex_form_code"]),
            )
            for row in rows
        ]
        return MiniAppCollectionPage(
            entries=entries,
            filter_state=filter_state.with_page(current_page),
            total_entries=total_entries,
            current_page=current_page,
            total_pages=total_pages,
            page_size=resolved_page_size,
        )

    async def _fetch_pokedex_page_with_page_size(
        self,
        conn: asyncpg.Connection,
        user_id: int,
        filter_state: PokedexFilterState,
        *,
        page_size: int,
    ) -> MiniAppPokedexPage:
        current_page = max(1, filter_state.page)
        resolved_page_size = max(1, min(page_size, 100))
        offset = (current_page - 1) * resolved_page_size

        where_sql, having_sql, params = _build_pokedex_filter_clauses(user_id, filter_state)
        count_sql = f"""
            SELECT COUNT(*)::int AS total_entries
            FROM (
              SELECT pc.id
              FROM pokemon_catalog pc
              LEFT JOIN user_pokemon up
                ON up.pokemon_id = pc.id
               AND up.owner_user_id = $1
               AND up.released_at IS NULL
              {where_sql}
              GROUP BY pc.id
              {having_sql}
            ) filtered_catalog
        """
        total_entries = int(await conn.fetchval(count_sql, *params) or 0)
        total_pages = max(1, (total_entries + resolved_page_size - 1) // resolved_page_size)
        current_page = min(current_page, total_pages)
        offset = (current_page - 1) * resolved_page_size

        data_params = [*params, resolved_page_size, offset]
        limit_index = len(params) + 1
        offset_index = len(params) + 2
        rows = await conn.fetch(
            f"""
            SELECT
              pc.id AS pokemon_id,
              pc.dex_form_code,
              pc.name,
              pc.rarity,
              pc.type,
              pc.base_hp,
              pc.base_attack,
              pc.base_defense,
              pc.base_stamina,
              pc.image_credit_id,
              COUNT(up.id)::int AS owned_quantity
            FROM pokemon_catalog pc
            LEFT JOIN user_pokemon up
              ON up.pokemon_id = pc.id
             AND up.owner_user_id = $1
             AND up.released_at IS NULL
            {where_sql}
            GROUP BY
              pc.id,
              pc.dex_form_code,
              pc.name,
              pc.rarity,
              pc.type,
              pc.base_hp,
              pc.base_attack,
              pc.base_defense,
              pc.base_stamina,
              pc.image_credit_id
            {having_sql}
            ORDER BY {_dex_form_sort_sql(qualified_column="pc.dex_form_code")}
            LIMIT ${limit_index}
            OFFSET ${offset_index}
            """,
            *data_params,
        )
        entries = [
            PokedexEntry(
                pokemon_id=int(row["pokemon_id"]),
                name=str(row["name"]),
                rarity=str(row["rarity"]),
                pokemon_type=row["type"],
                base_hp=int(row["base_hp"]),
                base_attack=int(row["base_attack"]),
                base_defense=int(row["base_defense"]),
                base_stamina=int(row["base_stamina"]),
                image_credit_id=row["image_credit_id"],
                dex_form_code=row["dex_form_code"],
                form_badge=_form_badge_from_dex_form_code(row["dex_form_code"]),
                owned_quantity=int(row["owned_quantity"]),
            )
            for row in rows
        ]
        return MiniAppPokedexPage(
            entries=entries,
            filter_state=filter_state.with_page(current_page),
            total_entries=total_entries,
            current_page=current_page,
            total_pages=total_pages,
            page_size=resolved_page_size,
        )

    async def _fetch_pokedex_detail(
        self,
        conn: asyncpg.Connection,
        user_id: int,
        *,
        pokemon_id: int,
    ) -> PokedexDetail:
        row = await conn.fetchrow(
            """
            SELECT
              pc.id AS pokemon_id,
              pc.dex_form_code,
              pc.name,
              pc.rarity,
              pc.type,
              pc.base_hp,
              pc.base_attack,
              pc.base_defense,
              pc.base_stamina,
              pc.image_credit_id,
              COUNT(up.id)::int AS owned_quantity
            FROM pokemon_catalog pc
            LEFT JOIN user_pokemon up
              ON up.pokemon_id = pc.id
             AND up.owner_user_id = $1
             AND up.released_at IS NULL
            WHERE pc.id = $2
            GROUP BY
              pc.id,
              pc.dex_form_code,
              pc.name,
              pc.rarity,
              pc.type,
              pc.base_hp,
              pc.base_attack,
              pc.base_defense,
              pc.base_stamina,
              pc.image_credit_id
            """,
            user_id,
            pokemon_id,
        )
        if not row:
            raise ShopError("Покемон не найден.")

        base_dex_code = _base_dex_from_form_code(row["dex_form_code"]) or str(pokemon_id)
        related_rows = await conn.fetch(
            f"""
            SELECT
              pc.id AS pokemon_id,
              pc.dex_form_code,
              COUNT(up.id)::int AS owned_quantity
            FROM pokemon_catalog pc
            LEFT JOIN user_pokemon up
              ON up.pokemon_id = pc.id
             AND up.owner_user_id = $1
             AND up.released_at IS NULL
            WHERE split_part(COALESCE(pc.dex_form_code, pc.id::text), '-', 1) = $2
              AND pc.id <> $3
            GROUP BY pc.id, pc.dex_form_code
            ORDER BY {_dex_form_sort_sql(qualified_column="pc.dex_form_code")}
            """,
            user_id,
            base_dex_code,
            pokemon_id,
        )
        related_forms = [
            PokedexRelatedForm(
                pokemon_id=int(related_row["pokemon_id"]),
                dex_form_code=related_row["dex_form_code"],
                form_badge=_form_badge_from_dex_form_code(related_row["dex_form_code"]),
                is_collected=int(related_row["owned_quantity"]) > 0,
            )
            for related_row in related_rows
        ]
        return PokedexDetail(
            pokemon_id=int(row["pokemon_id"]),
            name=str(row["name"]),
            rarity=str(row["rarity"]),
            pokemon_type=row["type"],
            base_hp=int(row["base_hp"]),
            base_attack=int(row["base_attack"]),
            base_defense=int(row["base_defense"]),
            base_stamina=int(row["base_stamina"]),
            image_credit_id=row["image_credit_id"],
            dex_form_code=row["dex_form_code"],
            form_badge=_form_badge_from_dex_form_code(row["dex_form_code"]),
            owned_quantity=int(row["owned_quantity"]),
            related_forms=related_forms,
        )

    async def _ensure_chat_encounter_state(self, conn: asyncpg.Connection, chat_id: int) -> None:
        await conn.execute(
            """
            INSERT INTO chat_encounter_state (chat_id)
            VALUES ($1)
            ON CONFLICT (chat_id) DO NOTHING
            """,
            chat_id,
        )

    async def _fetch_chat_encounter_state(
        self,
        conn: asyncpg.Connection,
        chat_id: int,
        *,
        for_update: bool = False,
    ) -> asyncpg.Record:
        await self._ensure_chat_encounter_state(conn, chat_id)
        lock_clause = " FOR UPDATE" if for_update else ""
        row = await conn.fetchrow(
            (
                "SELECT chat_id, last_spawn_at, messages_since_cooldown, active_encounter_id "
                "FROM chat_encounter_state WHERE chat_id = $1" + lock_clause
            ),
            chat_id,
        )
        if not row:
            raise ShopError("Chat encounter state is missing")
        return row

    async def _spawn_chat_encounter(
        self,
        conn: asyncpg.Connection,
        chat_id: int,
        message_thread_id: Optional[int],
        now: datetime,
    ) -> ChatEncounter:
        target_rarity = _weighted_rarity_choice(RARITY_PROBABILITIES)
        base_pokemon_row = await self._select_random_base_pokemon(conn, target_rarity)
        pokemon_row = await self._select_encounter_overlay_variant(conn, base_pokemon_row=base_pokemon_row)
        expires_at = now + timedelta(seconds=CHAT_ENCOUNTER_TIMEOUT_SECONDS)
        encounter_row = await conn.fetchrow(
            """
            INSERT INTO chat_encounters (
              chat_id,
              message_thread_id,
              pokemon_id,
              status,
              spawned_at,
              expires_at
            )
            VALUES ($1, $2, $3, 'active', $4, $5)
            RETURNING id, chat_id, message_thread_id, encounter_message_id,
                      pokemon_id, spawned_at, expires_at, status,
                      caught_by_user_id, caught_user_pokemon_id, caught_with_item_code
            """,
            chat_id,
            message_thread_id,
            int(pokemon_row["id"]),
            now,
            expires_at,
        )
        await conn.execute(
            """
            UPDATE chat_encounter_state
            SET last_spawn_at = $2,
                messages_since_cooldown = 0,
                active_encounter_id = $3,
                updated_at = $2
            WHERE chat_id = $1
            """,
            chat_id,
            now,
            int(encounter_row["id"]),
        )
        await self._set_encounter_cooldown_cache(chat_id, CHAT_ENCOUNTER_COOLDOWN_SECONDS)
        await self._set_active_encounter_cache(chat_id, int(encounter_row["id"]))
        await self._clear_encounter_counter_cache(chat_id)
        merged_row = {
            **dict(encounter_row),
            "name": pokemon_row["name"],
            "rarity": pokemon_row["rarity"],
            "type": pokemon_row["type"],
            "image_credit_id": pokemon_row["image_credit_id"],
        }
        logger.info(
            "chat_encounter_spawned",
            chat_id=chat_id,
            encounter_id=int(encounter_row["id"]),
            pokemon_id=int(pokemon_row["id"]),
            rarity=str(pokemon_row["rarity"]),
            dex_form_code=pokemon_row["dex_form_code"],
            form_kind=_form_kind_from_dex_form_code(pokemon_row["dex_form_code"]),
        )
        return _map_chat_encounter(merged_row)

    async def _expire_active_chat_encounter_if_due(
        self,
        conn: asyncpg.Connection,
        chat_id: int,
        now: datetime,
    ) -> bool:
        state = await self._fetch_chat_encounter_state(conn, chat_id, for_update=True)
        active_encounter_id = state["active_encounter_id"]
        if active_encounter_id is None:
            return False
        encounter_row = await conn.fetchrow(
            """
            SELECT id, expires_at, status
            FROM chat_encounters
            WHERE id = $1
            FOR UPDATE
            """,
            int(active_encounter_id),
        )
        if not encounter_row or encounter_row["status"] != "active":
            await conn.execute(
                """
                UPDATE chat_encounter_state
                SET active_encounter_id = NULL,
                    updated_at = $2
                WHERE chat_id = $1
                """,
                chat_id,
                now,
            )
            await self._clear_active_encounter_cache(chat_id)
            return True
        if _normalize_timestamp(encounter_row["expires_at"]) > now:
            return False
        await conn.execute(
            """
            UPDATE chat_encounters
            SET status = 'expired',
                resolved_at = $2
            WHERE id = $1
            """,
            int(active_encounter_id),
            now,
        )
        await conn.execute(
            """
            UPDATE chat_encounter_state
            SET active_encounter_id = NULL,
                messages_since_cooldown = 0,
                updated_at = $2
            WHERE chat_id = $1
            """,
            chat_id,
            now,
        )
        await self._clear_active_encounter_cache(chat_id)
        return True

    async def _note_chat_message_via_redis(self, chat_id: int) -> str | int | None:
        return await asyncio.to_thread(self._note_chat_message_via_redis_sync, chat_id)

    def _note_chat_message_via_redis_sync(self, chat_id: int) -> str | int | None:
        if self.redis is None:
            return None
        try:
            if self.redis.exists(_encounter_active_key(chat_id)):
                return "active"
            if self.redis.exists(_encounter_cooldown_key(chat_id)):
                return "cooldown"
            counter = self.redis.incr(_encounter_counter_key(chat_id))
            if counter == 1:
                self.redis.expire(_encounter_counter_key(chat_id), CHAT_ENCOUNTER_COUNTER_TTL_SECONDS)
            return int(counter)
        except RedisError as exc:
            logger.warning("chat_encounter_redis_bypass", chat_id=chat_id, error=str(exc))
            return None

    async def _fetch_market_listings_page(
        self,
        conn: asyncpg.Connection,
        user_id: int,
        filter_state: MarketBrowseState,
    ) -> MarketBrowsePage:
        current_page = max(1, filter_state.page)
        offset = (current_page - 1) * MARKET_PAGE_SIZE
        where_sql, params = await self._build_market_listing_filter_sql(conn, user_id, filter_state)

        total_entries = int(
            await conn.fetchval(
                f"""
                SELECT COUNT(*)::int
                FROM market_listings ml
                JOIN user_pokemon up ON up.id = ml.pokemon_instance_id
                JOIN pokemon_catalog pc ON pc.id = up.pokemon_id
                {where_sql}
                """,
                *params,
            )
            or 0
        )
        total_pages = max(1, (total_entries + MARKET_PAGE_SIZE - 1) // MARKET_PAGE_SIZE)
        current_page = min(current_page, total_pages)
        offset = (current_page - 1) * MARKET_PAGE_SIZE
        sort_sql = _market_sort_sql(filter_state.sort_mode)

        rows = await conn.fetch(
            f"""
            SELECT
              ml.id AS listing_id,
              ml.seller_user_id,
              u.nickname AS seller_nickname,
              u.tg_username AS seller_username,
              ml.pokemon_instance_id AS user_pokemon_id,
              pc.id AS pokemon_id,
              pc.dex_form_code,
              pc.name,
              pc.rarity,
              pc.type,
              pc.image_credit_id,
              ml.price,
              ml.status,
              ml.listed_at,
              ml.expires_at
            FROM market_listings ml
            JOIN user_pokemon up ON up.id = ml.pokemon_instance_id
            JOIN pokemon_catalog pc ON pc.id = up.pokemon_id
            JOIN users u ON u.id = ml.seller_user_id
            {where_sql}
            ORDER BY {sort_sql}
            LIMIT ${len(params) + 1}
            OFFSET ${len(params) + 2}
            """,
            *params,
            MARKET_PAGE_SIZE,
            offset,
        )
        balance = await self._get_balance(conn, user_id, POKECOIN_CODE)
        return MarketBrowsePage(
            entries=[_map_market_listing_summary(row) for row in rows],
            filter_state=filter_state.with_page(current_page),
            total_entries=total_entries,
            current_page=current_page,
            total_pages=total_pages,
            current_balance=balance,
        )

    async def _build_market_listing_filter_sql(
        self,
        conn: asyncpg.Connection,
        user_id: int,
        filter_state: MarketBrowseState,
    ) -> tuple[str, list[object]]:
        await self._ensure_user_balance(conn, user_id, POKECOIN_CODE)
        params: list[object] = [MARKET_LISTING_STATUS_ACTIVE, user_id]
        conditions = ["ml.status = $1", "ml.seller_user_id <> $2"]

        if filter_state.rarities:
            params.append(list(filter_state.rarities))
            conditions.append(f"pc.rarity = ANY(${len(params)}::text[])")

        if filter_state.affordable_only:
            balance = await self._get_balance(conn, user_id, POKECOIN_CODE)
            params.append(balance)
            conditions.append(f"ml.price <= ${len(params)}")

        normalized_query = filter_state.query.strip()
        if normalized_query:
            params.append(normalized_query)
            conditions.append(
                f"("
                f"pc.name ILIKE '%' || ${len(params)} || '%' "
                f"OR COALESCE(pc.dex_form_code, pc.id::text) ILIKE '%' || ${len(params)} || '%' "
                f"OR split_part(COALESCE(pc.dex_form_code, pc.id::text), '-', 1) = ${len(params)}"
                f")"
            )

        return "WHERE " + " AND ".join(conditions), params

    async def _fetch_market_listing_summary(
        self,
        conn: asyncpg.Connection,
        listing_id: int,
    ) -> MarketListingSummary:
        row = await conn.fetchrow(
            """
            SELECT
              ml.id AS listing_id,
              ml.seller_user_id,
              u.nickname AS seller_nickname,
              u.tg_username AS seller_username,
              ml.pokemon_instance_id AS user_pokemon_id,
              pc.id AS pokemon_id,
              pc.dex_form_code,
              pc.name,
              pc.rarity,
              pc.type,
              pc.image_credit_id,
              ml.price,
              ml.status,
              ml.listed_at,
              ml.expires_at
            FROM market_listings ml
            JOIN user_pokemon up ON up.id = ml.pokemon_instance_id
            JOIN pokemon_catalog pc ON pc.id = up.pokemon_id
            JOIN users u ON u.id = ml.seller_user_id
            WHERE ml.id = $1
            """,
            listing_id,
        )
        if not row:
            raise ShopError("Лот не найден.")
        return _map_market_listing_summary(row)

    async def _fetch_market_buy_request_summary(
        self,
        conn: asyncpg.Connection,
        request_id: int,
    ) -> MarketBuyRequestSummary:
        row = await conn.fetchrow(
            """
            SELECT
              mbr.id AS request_id,
              mbr.requester_user_id,
              u.nickname AS requester_nickname,
              u.tg_username AS requester_username,
              mbr.pokemon_id,
              pc.dex_form_code,
              pc.name,
              pc.rarity,
              pc.type,
              pc.image_credit_id,
              mbr.price,
              mbr.reserved_amount,
              mbr.status,
              mbr.created_at,
              NULL::bigint AS matching_user_pokemon_id
            FROM market_buy_requests mbr
            JOIN pokemon_catalog pc ON pc.id = mbr.pokemon_id
            JOIN users u ON u.id = mbr.requester_user_id
            WHERE mbr.id = $1
            """,
            request_id,
        )
        if not row:
            raise ShopError("Заявка не найдена.")
        return _map_market_buy_request_summary(row)

    async def _set_encounter_cooldown_cache(self, chat_id: int, remaining_seconds: int) -> None:
        await asyncio.to_thread(self._set_encounter_cooldown_cache_sync, chat_id, remaining_seconds)

    def _set_encounter_cooldown_cache_sync(self, chat_id: int, remaining_seconds: int) -> None:
        if self.redis is None or remaining_seconds <= 0:
            return
        try:
            self.redis.setex(_encounter_cooldown_key(chat_id), remaining_seconds, "1")
        except RedisError as exc:
            logger.warning("chat_encounter_redis_write_failed", chat_id=chat_id, key="cooldown", error=str(exc))

    async def _set_active_encounter_cache(self, chat_id: int, encounter_id: int) -> None:
        await asyncio.to_thread(self._set_active_encounter_cache_sync, chat_id, encounter_id)

    def _set_active_encounter_cache_sync(self, chat_id: int, encounter_id: int) -> None:
        if self.redis is None:
            return
        try:
            self.redis.setex(
                _encounter_active_key(chat_id),
                CHAT_ENCOUNTER_TIMEOUT_SECONDS,
                str(encounter_id),
            )
        except RedisError as exc:
            logger.warning("chat_encounter_redis_write_failed", chat_id=chat_id, key="active", error=str(exc))

    async def _clear_active_encounter_cache(self, chat_id: int) -> None:
        await asyncio.to_thread(self._clear_active_encounter_cache_sync, chat_id)

    def _clear_active_encounter_cache_sync(self, chat_id: int) -> None:
        if self.redis is None:
            return
        try:
            self.redis.delete(_encounter_active_key(chat_id))
        except RedisError as exc:
            logger.warning("chat_encounter_redis_write_failed", chat_id=chat_id, key="active", error=str(exc))

    async def _clear_encounter_counter_cache(self, chat_id: int) -> None:
        await asyncio.to_thread(self._clear_encounter_counter_cache_sync, chat_id)

    def _clear_encounter_counter_cache_sync(self, chat_id: int) -> None:
        if self.redis is None:
            return
        try:
            self.redis.delete(_encounter_counter_key(chat_id))
        except RedisError as exc:
            logger.warning("chat_encounter_redis_write_failed", chat_id=chat_id, key="counter", error=str(exc))


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is required when DATABASE_URL is not set")
    return value


def _calculate_bonus_amount(last_claim_at: datetime, now: datetime) -> int:
    elapsed_seconds = max(0.0, (now - _normalize_timestamp(last_claim_at)).total_seconds())
    capped_seconds = min(elapsed_seconds, SHOP_BONUS_CAP_SECONDS)
    return int(capped_seconds * SHOP_BONUS_RATE_PER_HOUR / 3600)


def _bonus_remaining_seconds(last_claim_at: datetime, now: datetime) -> int:
    elapsed_seconds = max(0.0, (now - _normalize_timestamp(last_claim_at)).total_seconds())
    if elapsed_seconds >= SHOP_BONUS_CLAIM_INTERVAL_SECONDS:
        return 0
    return int(SHOP_BONUS_CLAIM_INTERVAL_SECONDS - elapsed_seconds)


def _calculate_percent(value: int, total: int) -> int:
    if total <= 0:
        return 0
    return int((value * 100) / total)


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize_optional_timestamp(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return _normalize_timestamp(value)


def _resolve_trade_user_label(
    nickname: Optional[str],
    username: Optional[str],
    telegram_id: int,
) -> str:
    if nickname:
        return str(nickname)
    if username:
        normalized = str(username).lstrip("@")
        if normalized:
            return f"@{normalized}"
    return f"id:{telegram_id}"


def _resolve_roll_rarity(epic_counter: int, legendary_counter: int) -> str:
    if legendary_counter >= LEGENDARY_PITY_THRESHOLD - 1:
        return "Legendary"
    if epic_counter >= EPIC_PITY_THRESHOLD - 1:
        guaranteed_pool = {"Legendary": RARITY_PROBABILITIES["Legendary"], "Epic": RARITY_PROBABILITIES["Epic"]}
        return _weighted_rarity_choice(guaranteed_pool)
    return _weighted_rarity_choice(RARITY_PROBABILITIES)


def _weighted_rarity_choice(weights: dict[str, float]) -> str:
    roll = random.uniform(0, sum(weights.values()))
    cumulative = 0.0
    for rarity in RARITY_ORDER:
        if rarity not in weights:
            continue
        cumulative += weights[rarity]
        if roll <= cumulative:
            return rarity
    return next(reversed(weights))


def _rarity_pool_for_target(target_rarity: str) -> Sequence[str]:
    if target_rarity in {"Legendary", "Epic", "Rare", "Common"}:
        return (target_rarity,)
    return ("Common",)


def _update_pity_counters(result_rarity: str, epic_counter: int, legendary_counter: int) -> tuple[int, int]:
    if result_rarity == "Epic":
        return 0, legendary_counter + 1
    if result_rarity == "Legendary":
        return epic_counter + 1, 0
    return epic_counter + 1, legendary_counter + 1


def _chat_encounter_cooldown_ready(last_spawn_at: datetime, now: datetime) -> bool:
    return (now - _normalize_timestamp(last_spawn_at)).total_seconds() >= CHAT_ENCOUNTER_COOLDOWN_SECONDS


def _roll_chat_encounter_catch(ball_code: str) -> bool:
    chance = CHAT_ENCOUNTER_BALL_CATCH_CHANCES[ball_code]
    if chance >= 100.0:
        return True
    return random.uniform(0, 100) < chance


def _encounter_cooldown_key(chat_id: int) -> str:
    return f"encounter:cooldown:{chat_id}"


def _encounter_counter_key(chat_id: int) -> str:
    return f"encounter:count:{chat_id}"


def _encounter_active_key(chat_id: int) -> str:
    return f"encounter:active:{chat_id}"


def _calculate_market_daily_commission(price: int) -> int:
    if price <= 0:
        return 0
    return max(1, int(price * MARKET_LISTING_COMMISSION_RATE))


def _pokemon_release_reward(rarity: str) -> int:
    return POKEMON_RELEASE_REWARDS.get(rarity, 32)


def _market_due_commission_cycles(
    *,
    next_commission_at: datetime,
    expires_at: datetime,
    now: datetime,
) -> int:
    due_at = _normalize_timestamp(next_commission_at)
    expires = _normalize_timestamp(expires_at)
    current_time = _normalize_timestamp(now)
    cycles = 0
    while due_at <= current_time and due_at < expires:
        cycles += 1
        due_at += timedelta(days=1)
    return cycles


def _market_sort_sql(sort_mode: str) -> str:
    if sort_mode == MARKET_SORT_CHEAPEST:
        return "ml.price ASC, ml.listed_at DESC, ml.id DESC"
    return "ml.listed_at DESC, ml.id DESC"


def _resolve_market_user_label(nickname: Optional[str], username: Optional[str]) -> Optional[str]:
    if nickname:
        return str(nickname)
    if username:
        return f"@{username}"
    return None


def _market_days_remaining(expires_at: Optional[datetime]) -> int:
    if expires_at is None:
        return 0
    remaining_seconds = max(0.0, (_normalize_timestamp(expires_at) - datetime.now(UTC)).total_seconds())
    if remaining_seconds <= 0:
        return 0
    return max(1, int((remaining_seconds + 86399) // 86400))


def _map_market_listing_summary(row: asyncpg.Record | dict[str, object]) -> MarketListingSummary:
    data = dict(row)
    expires_at = _normalize_timestamp(data["expires_at"]) if data.get("expires_at") is not None else datetime.now(UTC)
    return MarketListingSummary(
        listing_id=int(data["listing_id"]),
        seller_user_id=int(data["seller_user_id"]),
        seller_label=_resolve_market_user_label(data.get("seller_nickname"), data.get("seller_username")),
        user_pokemon_id=int(data["user_pokemon_id"]),
        pokemon_id=int(data["pokemon_id"]),
        name=str(data["name"]),
        rarity=str(data["rarity"]),
        pokemon_type=data.get("type"),
        price=int(data["price"]),
        status=str(data["status"]),
        listed_at=_normalize_timestamp(data["listed_at"]),
        expires_at=expires_at,
        days_remaining=_market_days_remaining(expires_at),
        image_credit_id=data.get("image_credit_id"),
        dex_form_code=data.get("dex_form_code"),
        form_badge=_form_badge_from_dex_form_code(data.get("dex_form_code")),
    )


def _map_market_buy_request_summary(row: asyncpg.Record | dict[str, object]) -> MarketBuyRequestSummary:
    data = dict(row)
    return MarketBuyRequestSummary(
        request_id=int(data["request_id"]),
        requester_user_id=int(data["requester_user_id"]),
        requester_label=_resolve_market_user_label(data.get("requester_nickname"), data.get("requester_username")),
        pokemon_id=int(data["pokemon_id"]),
        name=str(data["name"]),
        rarity=str(data["rarity"]),
        pokemon_type=data.get("type"),
        price=int(data["price"]),
        reserved_amount=int(data["reserved_amount"]),
        status=str(data["status"]),
        created_at=_normalize_timestamp(data["created_at"]),
        image_credit_id=data.get("image_credit_id"),
        dex_form_code=data.get("dex_form_code"),
        form_badge=_form_badge_from_dex_form_code(data.get("dex_form_code")),
        matching_user_pokemon_id=(
            int(data["matching_user_pokemon_id"]) if data.get("matching_user_pokemon_id") is not None else None
        ),
    )


def _map_chat_encounter(row: asyncpg.Record | dict[str, object]) -> ChatEncounter:
    data = dict(row)
    return ChatEncounter(
        encounter_id=int(data["id"]),
        chat_id=int(data["chat_id"]),
        message_thread_id=data.get("message_thread_id"),
        encounter_message_id=data.get("encounter_message_id"),
        pokemon_id=int(data["pokemon_id"]),
        name=str(data["name"]),
        rarity=str(data["rarity"]),
        pokemon_type=data.get("type"),
        image_credit_id=data.get("image_credit_id"),
        spawned_at=_normalize_timestamp(data["spawned_at"]),
        expires_at=_normalize_timestamp(data["expires_at"]),
        status=str(data["status"]),
        caught_by_user_id=(int(data["caught_by_user_id"]) if data.get("caught_by_user_id") is not None else None),
        caught_user_pokemon_id=(
            int(data["caught_user_pokemon_id"]) if data.get("caught_user_pokemon_id") is not None else None
        ),
        caught_with_item_code=data.get("caught_with_item_code"),
    )


def _normalize_collection_types(raw_type: Optional[str]) -> tuple[str, ...]:
    if not raw_type:
        return ()
    values = []
    for part in str(raw_type).split("/"):
        normalized = part.strip().lower()
        if not normalized or normalized.isdigit():
            continue
        values.append(normalized)
    return tuple(dict.fromkeys(values))


def _build_collection_filter_clauses(
    user_id: int,
    filter_state: CollectionFilterState,
) -> tuple[str, str, list[object]]:
    params: list[object] = [user_id]
    where_conditions = ["up.owner_user_id = $1", "up.released_at IS NULL"]

    if filter_state.locked_only:
        where_conditions.append("up.is_locked = TRUE")

    if filter_state.rarities:
        params.append(list(filter_state.rarities))
        where_conditions.append(f"pc.rarity = ANY(${len(params)}::text[])")

    for pokemon_type in filter_state.types:
        params.append(pokemon_type.lower())
        where_conditions.append(
            f"EXISTS ("
            f"SELECT 1 "
            f"FROM unnest(string_to_array(COALESCE(lower(pc.type), ''), '/')) AS part "
            f"WHERE btrim(part) = ${len(params)}"
            f")"
        )

    normalized_query = filter_state.query.strip()
    if normalized_query:
        params.append(normalized_query)
        where_conditions.append(
            f"("
            f"pc.name ILIKE '%' || ${len(params)} || '%' "
            f"OR COALESCE(pc.dex_form_code, pc.id::text) ILIKE '%' || ${len(params)} || '%' "
            f"OR split_part(COALESCE(pc.dex_form_code, pc.id::text), '-', 1) = ${len(params)}"
            f")"
        )

    where_sql = "WHERE " + " AND ".join(where_conditions)
    having_sql = "HAVING COUNT(*) > 1" if filter_state.duplicates_only else ""
    return where_sql, having_sql, params


def _build_pokedex_filter_clauses(
    user_id: int,
    filter_state: PokedexFilterState,
) -> tuple[str, str, list[object]]:
    params: list[object] = [user_id]
    where_conditions = ["1 = 1"]
    having_conditions: list[str] = []

    if filter_state.rarities:
        params.append(list(filter_state.rarities))
        where_conditions.append(f"pc.rarity = ANY(${len(params)}::text[])")

    for pokemon_type in filter_state.types:
        params.append(pokemon_type.lower())
        where_conditions.append(
            f"EXISTS ("
            f"SELECT 1 "
            f"FROM unnest(string_to_array(COALESCE(lower(pc.type), ''), '/')) AS part "
            f"WHERE btrim(part) = ${len(params)}"
            f")"
        )

    if filter_state.form_kinds:
        params.append(list(filter_state.form_kinds))
        where_conditions.append(
            f"CASE "
            f"WHEN position('-' in COALESCE(pc.dex_form_code, '')) = 0 THEN '{FORM_KIND_BASE}' "
            f"ELSE COALESCE("
            f"  CASE split_part(pc.dex_form_code, '-', 2) "
            f"    WHEN '{FORM_SUFFIX_MAP[FORM_KIND_SHINY]}' THEN '{FORM_KIND_SHINY}' "
            f"    WHEN '{FORM_SUFFIX_MAP[FORM_KIND_MEGA]}' THEN '{FORM_KIND_MEGA}' "
            f"    WHEN '{FORM_SUFFIX_MAP[FORM_KIND_GIGANTAMAX]}' THEN '{FORM_KIND_GIGANTAMAX}' "
            f"    ELSE '{FORM_KIND_BASE}' "
            f"  END, "
            f"  '{FORM_KIND_BASE}'"
            f") "
            f"END = ANY(${len(params)}::text[])"
        )

    normalized_query = filter_state.query.strip()
    if normalized_query:
        params.append(normalized_query)
        where_conditions.append(
            f"("
            f"pc.name ILIKE '%' || ${len(params)} || '%' "
            f"OR COALESCE(pc.dex_form_code, pc.id::text) ILIKE '%' || ${len(params)} || '%' "
            f"OR split_part(COALESCE(pc.dex_form_code, pc.id::text), '-', 1) = ${len(params)}"
            f")"
        )

    if filter_state.collected_state == "collected":
        having_conditions.append("COUNT(up.id) > 0")
    elif filter_state.collected_state == "missing":
        having_conditions.append("COUNT(up.id) = 0")

    where_sql = "WHERE " + " AND ".join(where_conditions)
    having_sql = f"HAVING {' AND '.join(having_conditions)}" if having_conditions else ""
    return where_sql, having_sql, params


def _entry_matches_filter(entry: CollectionEntry, filter_state: CollectionFilterState) -> bool:
    if filter_state.locked_only and not entry.is_locked:
        return False

    if filter_state.rarities and entry.rarity not in filter_state.rarities:
        return False

    entry_types = set(_normalize_collection_types(entry.pokemon_type))
    if filter_state.types and not set(filter_state.types).issubset(entry_types):
        return False

    if filter_state.duplicates_only and entry.quantity <= 1:
        return False

    return True


def _paginate_collection_entries(
    entries: list[CollectionEntry], filter_state: CollectionFilterState
) -> CollectionPage:
    filtered_entries = [entry for entry in entries if _entry_matches_filter(entry, filter_state)]
    total_entries = len(filtered_entries)
    total_pages = max(1, (total_entries + COLLECTION_PAGE_SIZE - 1) // COLLECTION_PAGE_SIZE)
    current_page = min(max(1, filter_state.page), total_pages)
    start = (current_page - 1) * COLLECTION_PAGE_SIZE
    end = start + COLLECTION_PAGE_SIZE
    return CollectionPage(
        entries=filtered_entries[start:end],
        filter_state=filter_state.with_page(current_page),
        total_entries=total_entries,
        current_page=current_page,
        total_pages=total_pages,
    )
