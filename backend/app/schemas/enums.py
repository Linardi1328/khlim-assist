from enum import StrEnum


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class EventStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class FAQCategory(StrEnum):
    REGISTRATION = "REGISTRATION"
    FEES = "FEES"
    TEAM_COMPOSITION = "TEAM_COMPOSITION"
    ELIGIBILITY = "ELIGIBILITY"
    PLAYER_RESTRICTIONS = "PLAYER_RESTRICTIONS"
    SCHEDULE = "SCHEDULE"
    RULES = "RULES"
    CHECK_IN = "CHECK_IN"
    PAYMENT = "PAYMENT"
    WITHDRAWAL = "WITHDRAWAL"
    MERCHANDISE = "MERCHANDISE"
    TECHNICAL = "TECHNICAL"
    COMMERCIAL = "COMMERCIAL"
    GENERAL = "GENERAL"


class FAQDisposition(StrEnum):
    AUTO = "AUTO"
    LOOKUP = "LOOKUP"
    CLARIFY = "CLARIFY"
    HUMAN = "HUMAN"


class FAQStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    RETIRED = "RETIRED"


class AnswerSource(StrEnum):
    EVENT_CONFIG = "EVENT_CONFIG"
    FAQ_MASTER = "FAQ_MASTER"
    RULE_ENGINE = "RULE_ENGINE"
    REGISTRATION_SYSTEM = "REGISTRATION_SYSTEM"
    PAYMENT_SYSTEM = "PAYMENT_SYSTEM"
    MERCHANDISE_SYSTEM = "MERCHANDISE_SYSTEM"
    HUMAN_PIC = "HUMAN_PIC"
    PUBLISHED_DOCUMENT = "PUBLISHED_DOCUMENT"
    EXTERNAL_URL = "EXTERNAL_URL"


class RuleStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    RETIRED = "RETIRED"


class ChannelName(StrEnum):
    WHATSAPP = "WHATSAPP"
    INSTAGRAM = "INSTAGRAM"


class LanguageCode(StrEnum):
    ENGLISH = "en"
    MALAY = "ms"
    MANDARIN = "zh"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class LanguageMode(StrEnum):
    SINGLE = "single"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ConversationState(StrEnum):
    AI_ACTIVE = "AI_ACTIVE"
    WAITING_FOR_CLARIFICATION = "WAITING_FOR_CLARIFICATION"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"
    HUMAN_ACTIVE = "HUMAN_ACTIVE"
    RESOLVED = "RESOLVED"


class MessageDirection(StrEnum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class SenderType(StrEnum):
    PARTICIPANT = "PARTICIPANT"
    AI = "AI"
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"


class ContentType(StrEnum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    DOCUMENT = "DOCUMENT"
    AUDIO = "AUDIO"
    UNKNOWN = "UNKNOWN"


class DecisionLevel(StrEnum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class HandoffPriority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class HandoffStatus(StrEnum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class PICRole(StrEnum):
    GENERAL_ADMIN = "GENERAL_ADMIN"
    REGISTRATION = "REGISTRATION"
    FINANCE = "FINANCE"
    COMPETITION = "COMPETITION"
    TOURNAMENT_DIRECTOR = "TOURNAMENT_DIRECTOR"
    OPERATIONS = "OPERATIONS"
    MERCHANDISE = "MERCHANDISE"
    COMMERCIAL = "COMMERCIAL"


class ReasonCode(StrEnum):
    REGISTRATION_EXCEPTION = "REGISTRATION_EXCEPTION"
    REGISTRATION_STATUS_LOOKUP = "REGISTRATION_STATUS_LOOKUP"
    PAYMENT_VERIFICATION = "PAYMENT_VERIFICATION"
    REFUND_REQUEST = "REFUND_REQUEST"
    OVERPAYMENT = "OVERPAYMENT"
    ELIGIBILITY_EXCEPTION = "ELIGIBILITY_EXCEPTION"
    RULE_DISPUTE = "RULE_DISPUTE"
    SCHEDULE_EXCEPTION = "SCHEDULE_EXCEPTION"
    WITHDRAWAL = "WITHDRAWAL"
    WALKOVER_DISPUTE = "WALKOVER_DISPUTE"
    MERCHANDISE_ORDER_LOOKUP = "MERCHANDISE_ORDER_LOOKUP"
    TECHNICAL_REGISTRATION_FAILURE = "TECHNICAL_REGISTRATION_FAILURE"
    COMMERCIAL_ENQUIRY = "COMMERCIAL_ENQUIRY"
    HUMAN_REQUESTED = "HUMAN_REQUESTED"
    UNKNOWN_HIGH_RISK = "UNKNOWN_HIGH_RISK"


class IntentType(StrEnum):
    REGISTRATION_INFO = "registration_info"
    REGISTRATION_STATUS = "registration_status"
    LATE_REGISTRATION = "late_registration"
    FEE = "fee"
    TEAM_COMPOSITION = "team_composition"
    ELIGIBILITY = "eligibility"
    ELIGIBILITY_EXCEPTION = "eligibility_exception"
    SCHEDULE = "schedule"
    SCHEDULE_EXCEPTION = "schedule_exception"
    RULES = "rules"
    RULE_DISPUTE = "rule_dispute"
    CHECK_IN = "check_in"
    PAYMENT_STATUS = "payment_status"
    REFUND = "refund"
    OVERPAYMENT = "overpayment"
    WITHDRAWAL = "withdrawal"
    WALKOVER_DISPUTE = "walkover_dispute"
    MERCHANDISE_INFO = "merchandise_info"
    MERCHANDISE_ORDER = "merchandise_order"
    TECHNICAL_REGISTRATION = "technical_registration"
    COMMERCIAL = "commercial"
    HUMAN_REQUEST = "human_request"
    UNKNOWN = "unknown"


class AuditActorType(StrEnum):
    SYSTEM = "SYSTEM"
    AI = "AI"
    HUMAN = "HUMAN"
    WEBHOOK = "WEBHOOK"
