from core.agent_access.exceptions import AgentAuditPaginationError
from core.agent_access.schemas import AgentAuditCursor, AgentAuditEventPageParams
from entrypoints.litestar.api.parameters import (
    AgentAuditCursorCreatedAtQuery,
    AgentAuditCursorEventIdQuery,
    AgentAuditPageSizeQuery,
    AgentClientIdPath,
)


def provide_agent_audit_event_page_params(
    client_id: AgentClientIdPath,
    page_size: AgentAuditPageSizeQuery,
    cursor_created_at: AgentAuditCursorCreatedAtQuery = None,
    cursor_event_id: AgentAuditCursorEventIdQuery = None,
) -> AgentAuditEventPageParams:
    if (cursor_created_at is None) != (cursor_event_id is None):
        raise AgentAuditPaginationError
    cursor = (
        AgentAuditCursor(
            created_at=cursor_created_at,
            event_id=cursor_event_id,
        )
        if cursor_created_at is not None and cursor_event_id is not None
        else None
    )
    return AgentAuditEventPageParams(
        agent_client_id=client_id,
        page_size=page_size,
        cursor=cursor,
    )
