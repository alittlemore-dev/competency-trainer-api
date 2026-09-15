from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class DatabaseTransactionState:
    rollback_required: bool
