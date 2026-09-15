from core.enums import StrEnum


class AgentClientStatusEnum(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class AgentScopeEnum(StrEnum):
    MATRIX_QUEUE_CLAIM = "matrix.queue.claim"
    MATRIX_CONTEXT_READ = "matrix.context.read"
    MATRIX_RESOURCES_READ = "matrix.resources.read"
    MATRIX_DRAFT_CREATE = "matrix.draft.create"


class AgentActionEnum(StrEnum):
    CLAIM_NEXT_MATRIX_QUESTION = "claim_next_matrix_question"
    GET_MATRIX_AUTHORING_CONTEXT = "get_matrix_authoring_context"
    SEARCH_MATRIX_RESOURCES = "search_matrix_resources"
    SAVE_MATRIX_QUESTION_DRAFT = "save_matrix_question_draft"
    RELEASE_MATRIX_QUESTION_CLAIM = "release_matrix_question_claim"
    ROTATE_AGENT_CERTIFICATE = "rotate_agent_certificate"
    CONFIRM_AGENT_CERTIFICATE_ROTATION = "confirm_agent_certificate_rotation"


class AgentAuditResultEnum(StrEnum):
    SUCCESS = "success"
    REJECTED = "rejected"
    FAILED = "failed"
