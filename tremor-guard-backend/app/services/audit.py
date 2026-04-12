from sqlalchemy.orm import Session

from app.models.clinical import ApiAuditLog


def record_audit_log(
    session: Session,
    *,
    user_id: str | None,
    endpoint: str,
    method: str,
    action: str,
    idempotency_key: str | None = None,
    request_summary: dict | None = None,
    response_summary: dict | None = None,
    risk_flag: bool = False,
) -> ApiAuditLog:
    audit_log = ApiAuditLog(
        user_id=user_id,
        endpoint=endpoint,
        method=method,
        action=action,
        idempotency_key=idempotency_key,
        request_summary=request_summary,
        response_summary=response_summary,
        risk_flag=risk_flag,
    )
    session.add(audit_log)
    session.flush()
    return audit_log
