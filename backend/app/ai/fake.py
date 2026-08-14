from app.ai.base import AIProviderCallMetadata, GeneratedResponse, ResponseGenerationRequest
from app.schemas.enums import IntentType, KnowledgeTopic, LanguageCode, LanguageMode
from app.schemas.interpretation import InterpretationRequest, InterpretedMessage, MessageIntent


class FakeAIProvider:
    """Deterministic provider for tests and local synthetic evaluation."""

    provider_name = "fake"
    model = "fake-deterministic-v1"

    def __init__(self) -> None:
        self.interpretation_metadata: AIProviderCallMetadata | None = None
        self.response_metadata: AIProviderCallMetadata | None = None

    async def interpret_message(self, request: InterpretationRequest) -> InterpretedMessage:
        text = request.message_text.strip()
        lowered = text.lower()
        language, mode = _detect_language(text)
        intents = _detect_intents(lowered)
        clarification_fields = _clarification_fields(lowered, intents)
        participant_requested_human = any(
            intent.type == IntentType.HUMAN_REQUEST for intent in intents
        )
        self.interpretation_metadata = AIProviderCallMetadata(
            provider_request_id="fake_interpretation",
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
        )
        return InterpretedMessage(
            primary_language=language,
            language_mode=mode,
            intents=intents or [MessageIntent(type=IntentType.UNKNOWN)],
            requires_clarification=bool(clarification_fields),
            clarification_fields=clarification_fields,
            participant_requested_human=participant_requested_human,
        )

    async def generate_response(self, request: ResponseGenerationRequest) -> GeneratedResponse:
        self.response_metadata = AIProviderCallMetadata(
            provider_request_id="fake_response",
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
        )
        text = _draft_response(request)
        return GeneratedResponse(text=text, should_send=False)


def _detect_language(text: str) -> tuple[LanguageCode, LanguageMode]:
    has_cjk = any("\u4e00" <= character <= "\u9fff" for character in text)
    has_latin = any(character.isascii() and character.isalpha() for character in text)
    lowered = text.lower()
    tokens = _tokens(lowered)
    has_malay = any(
        token in tokens
        for token in {
            "pendaftaran",
            "berapa",
            "orang",
            "boleh",
            "sudah",
            "ke",
            "terbayar",
            "daftar",
            "lambat",
            "dekat",
            "mana",
            "kalau",
            "tarik",
            "diri",
            "tak",
            "saya",
            "masuk",
        }
    )
    if has_cjk and has_latin:
        latin_tokens = {
            token
            for token in tokens
            if token.isascii() and any(character.isalpha() for character in token)
        }
        if latin_tokens and all(
            token.startswith("u") and token[1:].isdigit() for token in latin_tokens
        ):
            return LanguageCode.MANDARIN, LanguageMode.SINGLE
        return LanguageCode.MIXED, LanguageMode.MIXED
    if has_cjk:
        return LanguageCode.MANDARIN, LanguageMode.SINGLE
    if has_malay and {"coach", "can", "extra"}.intersection(tokens):
        return LanguageCode.MIXED, LanguageMode.MIXED
    if has_malay and has_latin:
        return LanguageCode.MALAY, LanguageMode.SINGLE
    if any(token in lowered for token in ["ah", "ya", "lah", "sudah", "right"]) and has_latin:
        return LanguageCode.MIXED, LanguageMode.MIXED
    return LanguageCode.ENGLISH, LanguageMode.SINGLE


def _detect_intents(lowered: str) -> list[MessageIntent]:
    intents: list[MessageIntent] = []
    tokens = _tokens(lowered)

    if any(token in lowered for token in ["负责人", "human", "person", "someone", "pic"]):
        intents.append(MessageIntent(type=IntentType.HUMAN_REQUEST))
    if "approve something special" in lowered:
        intents.append(MessageIntent(type=IntentType.UNKNOWN))
    if any(token in lowered for token in ["overage", "too old", "exception"]):
        intents.append(MessageIntent(type=IntentType.ELIGIBILITY_EXCEPTION))
    if (
        "reserve" in lowered
        or "late registration" in lowered
        or ("daftar" in tokens and "lambat" in tokens)
    ):
        intents.append(MessageIntent(type=IntentType.LATE_REGISTRATION))
    if "refund" in lowered or "退款" in lowered:
        intents.append(MessageIntent(type=IntentType.REFUND))
    if "terbayar" in lowered or "overpayment" in lowered or "paid extra" in lowered:
        intents.insert(0, MessageIntent(type=IntentType.OVERPAYMENT))
    withdrawal_requested = (
        "withdraw" in lowered or "退出" in lowered or {"tarik", "diri"}.issubset(tokens)
    )
    if withdrawal_requested:
        intents.insert(0, MessageIntent(type=IntentType.WITHDRAWAL))
    if "walkover" in lowered or "disagree" in lowered:
        intents.append(MessageIntent(type=IntentType.WALKOVER_DISPUTE))
    if "move our game" in lowered or "change our game" in lowered:
        intents.append(MessageIntent(type=IntentType.SCHEDULE_EXCEPTION))
    if "booth" in lowered or "vendor" in lowered:
        intents.append(MessageIntent(type=IntentType.COMMERCIAL))
    if "payment" in lowered or "付款" in lowered or "receive" in lowered:
        intents.append(MessageIntent(type=IntentType.PAYMENT_STATUS))
    if "registration confirmed" in lowered or "team register successfully" in lowered:
        intents.append(MessageIntent(type=IntentType.REGISTRATION_STATUS))
    if "form" in lowered or "upload" in lowered or "cannot submit" in lowered:
        intents.append(MessageIntent(type=IntentType.TECHNICAL_REGISTRATION))
    if "shirt order" in lowered or "order arrive" in lowered:
        intents.append(MessageIntent(type=IntentType.MERCHANDISE_ORDER))
    has_merchandise = "shirt" in lowered or "merch" in lowered or "jersey" in lowered
    has_order_lookup = any(intent.type == IntentType.MERCHANDISE_ORDER for intent in intents)
    if has_merchandise and not has_order_lookup:
        intents.append(
            MessageIntent(
                type=IntentType.MERCHANDISE_INFO,
                knowledge_topic=_merchandise_topic(lowered),
            )
        )
    if (
        not has_merchandise
        and (
            "how much" in lowered
            or "fee" in lowered
            or any(token.startswith("rm") for token in tokens)
            or "报名费" in lowered
            or ("berapa" in tokens and "harga" in tokens)
        )
    ):
        intents.append(
            MessageIntent(
                type=IntentType.FEE,
                category=_category(lowered),
                knowledge_topic=_fee_topic(lowered),
            )
        )
    if (
        any(
            token in lowered
            for token in ["register", "registration", "报名", "pendaftaran", "slot"]
        )
        and "报名费" not in lowered
        and not any(intent.type == IntentType.TECHNICAL_REGISTRATION for intent in intents)
        and not any(intent.type == IntentType.REGISTRATION_STATUS for intent in intents)
        and not any(intent.type == IntentType.LATE_REGISTRATION for intent in intents)
    ):
        intents.append(
            MessageIntent(
                type=IntentType.REGISTRATION_INFO,
                knowledge_topic=_registration_topic(lowered),
            )
        )
    if (
        any(
            token in lowered
            for token in ["date", "day", "sunday", "tomorrow", "几时", "比赛", "schedule", "venue"]
        )
        or {"dekat", "mana"}.issubset(tokens)
    ) and not any(intent.type == IntentType.LATE_REGISTRATION for intent in intents):
        intents.append(
            MessageIntent(
                type=IntentType.SCHEDULE,
                category=_category(lowered),
                knowledge_topic=_schedule_topic(lowered),
            )
        )
    has_player_count_request = any(
        token in lowered for token in ["max", "maximum", "minimum", "players", "orang"]
    )
    has_foreign_player_request = any(
        token in lowered for token in ["foreigner", "foreign", "外国人"]
    )
    explicit_player_count_request = any(token in lowered for token in ["max", "maximum", "minimum"])
    if has_player_count_request and (
        explicit_player_count_request or not has_foreign_player_request
    ):
        intents.append(
            MessageIntent(
                type=IntentType.TEAM_COMPOSITION,
                category=_category(lowered),
                knowledge_topic=_team_topic(lowered),
                entities=_team_entities(lowered),
            )
        )
    if "national" in lowered:
        intents.append(
            MessageIntent(
                type=IntentType.PLAYER_RESTRICTIONS,
                knowledge_topic=KnowledgeTopic.NATIONAL_PLAYER_POLICY,
                entities={"national_player": True},
            )
        )
    elif has_foreign_player_request and (
        "how many foreign" in lowered
        or "max foreign" in lowered
        or "maximum foreign" in lowered
        or "多少外国" in lowered
    ):
        intents.append(
            MessageIntent(
                type=IntentType.PLAYER_RESTRICTIONS,
                knowledge_topic=KnowledgeTopic.FOREIGN_PLAYER_MAX,
                entities={"foreign_player_count": True},
            )
        )
    elif any(token in lowered for token in ["foreigner", "foreign", "外国人"]):
        intents.append(
            MessageIntent(
                type=IntentType.ELIGIBILITY,
                knowledge_topic=KnowledgeTopic.FOREIGN_PLAYERS_ALLOWED,
                entities={"foreign_player": True},
            )
        )
    if any(
        token in lowered
        for token in ["born", "可以打", "can play", "can join", "join u", "son join"]
    ):
        entities = _eligibility_entities(lowered)
        intents.append(
            MessageIntent(
                type=IntentType.ELIGIBILITY,
                category=_category(lowered),
                knowledge_topic=KnowledgeTopic.ELIGIBILITY_CATEGORY,
                entities=entities,
            )
        )
    if "check in" in lowered:
        intents.append(
            MessageIntent(
                type=IntentType.CHECK_IN,
                knowledge_topic=_check_in_topic(lowered),
                entities=_check_in_entities(lowered),
            )
        )
    if "rules" in lowered and "ignore all rules" not in lowered:
        intents.append(
            MessageIntent(
                type=IntentType.RULES,
                knowledge_topic=KnowledgeTopic.RULES_LINK,
            )
        )

    unique: list[MessageIntent] = []
    seen: set[IntentType] = set()
    for intent in intents:
        if intent.type not in seen:
            seen.add(intent.type)
            unique.append(intent)
    if (
        any(intent.type == IntentType.REGISTRATION_INFO for intent in unique)
        and any(intent.type == IntentType.FEE for intent in unique)
        and "where" in tokens
    ):
        unique.sort(key=lambda intent: 0 if intent.type == IntentType.REGISTRATION_INFO else 1)
    return unique


def _tokens(text: str) -> set[str]:
    normalized = text
    for character in "?!.,:;()[]{}":
        normalized = normalized.replace(character, " ")
    return set(normalized.split())


def _category(text: str) -> str | None:
    for category in ["U10", "U12", "U14", "U16", "U18", "OPEN"]:
        if category.lower() in text:
            return category
    return None


def _registration_topic(text: str) -> KnowledgeTopic:
    tokens = _tokens(text)
    if "deadline" in text:
        return KnowledgeTopic.REGISTRATION_DEADLINE
    if "close" in text:
        return KnowledgeTopic.REGISTRATION_CLOSE_TIME
    if "open" in text or "buka" in tokens:
        return KnowledgeTopic.REGISTRATION_OPEN
    if "where" in tokens or "link" in text or "qr" in tokens or "报名" in text:
        return KnowledgeTopic.REGISTRATION_LINK
    return KnowledgeTopic.REGISTRATION_METHOD


def _fee_topic(text: str) -> KnowledgeTopic:
    if "early" in text or "bird" in text:
        if "end" in text or "deadline" in text or "until" in text:
            return KnowledgeTopic.EARLY_BIRD_DEADLINE
        return KnowledgeTopic.EARLY_BIRD_FEE
    if "different" in text:
        return KnowledgeTopic.CATEGORY_FEE
    return KnowledgeTopic.REGISTRATION_FEE


def _schedule_topic(text: str) -> KnowledgeTopic:
    if "release" in text or "final schedule" in text:
        return KnowledgeTopic.SCHEDULE_RELEASE
    if "both" in text:
        return KnowledgeTopic.KEEP_BOTH_EVENT_DAYS
    if "same day" in text:
        return KnowledgeTopic.CATEGORIES_SAME_DAY
    return KnowledgeTopic.CATEGORY_PLAYING_DATE


def _team_topic(text: str) -> KnowledgeTopic:
    if "3" in text or "three" in text:
        return KnowledgeTopic.TEAM_THREE_PLAYERS
    if "min" in text or "minimum" in text:
        return KnowledgeTopic.TEAM_MIN_PLAYERS
    if "mix" in text or "boys and girls" in text:
        return KnowledgeTopic.TEAM_MIXED_GENDER
    return KnowledgeTopic.TEAM_MAX_PLAYERS


def _team_entities(text: str) -> dict[str, int | bool]:
    topic = _team_topic(text)
    if topic == KnowledgeTopic.TEAM_THREE_PLAYERS:
        return {"requested_players": 3}
    if topic == KnowledgeTopic.TEAM_MIN_PLAYERS:
        return {"minimum_players": 1}
    if topic == KnowledgeTopic.TEAM_MIXED_GENDER:
        return {"mixed_gender": True}
    return {"maximum_players": 1}


def _check_in_topic(text: str) -> KnowledgeTopic:
    if "one player" in text or "1 player" in text or "single" in text:
        return KnowledgeTopic.CHECK_IN_SINGLE_PLAYER
    return KnowledgeTopic.CHECK_IN_WHOLE_TEAM


def _check_in_entities(text: str) -> dict[str, bool]:
    if _check_in_topic(text) == KnowledgeTopic.CHECK_IN_SINGLE_PLAYER:
        return {"single_player": True}
    return {"whole_team": True}


def _merchandise_topic(text: str) -> KnowledgeTopic:
    if "included" in text:
        return KnowledgeTopic.MERCHANDISE_INCLUDED
    if "price" in text or "how much" in text:
        return KnowledgeTopic.MERCHANDISE_PRICE
    if "deadline" in text or "preorder" in text:
        return KnowledgeTopic.MERCHANDISE_PREORDER_DEADLINE
    if "delivery fee" in text:
        return KnowledgeTopic.MERCHANDISE_DELIVERY_FEE
    return KnowledgeTopic.MERCHANDISE_ORDER_LINK


def _eligibility_entities(text: str) -> dict[str, int]:
    entities: dict[str, int] = {}
    for year in range(2000, 2031):
        if str(year) in text:
            entities["birth_year"] = year
            break
    return entities


def _clarification_fields(lowered: str, intents: list[MessageIntent]) -> list[str]:
    fields: set[str] = set()
    for intent in intents:
        if intent.type != IntentType.ELIGIBILITY:
            continue
        if not intent.category and "foreign_player" not in intent.entities:
            fields.add("category")
        if "birth_year" not in intent.entities and "foreign_player" not in intent.entities:
            fields.add("birth_year")
    if "can my son join" in lowered:
        fields.update({"birth_year", "category"})
    return sorted(fields)


def _draft_response(request: ResponseGenerationRequest) -> str:
    if request.decision_result.level.value == "GREEN":
        facts = [result.value for result in request.knowledge_results if result.found]
        if facts:
            return f"Hi! Based on the approved event info: {facts[0]} 😊"
        return "Hi! I can answer this once approved event info is available ya."
    if request.decision_result.clarification_fields:
        fields = " and ".join(request.decision_result.clarification_fields)
        return f"Sure! May I know the {fields} first? 😊"
    if request.decision_result.level.value == "RED":
        return "This one needs confirmation from our team ya 🙏🏻"
    return "This one needs verified checking first ya 🙏🏻"
