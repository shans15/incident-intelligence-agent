from pydantic import BaseModel


class PagerDutyAlert(BaseModel):
    """Validated shape of a PagerDuty webhook payload."""
    title: str
    service: str = ""
    severity: str = "unknown"
    triggered_at: str = ""
    description: str = ""


class Incident(BaseModel):
    id: str
    title: str
    severity: str
    date: str
    root_cause: str
    resolution: str
    link: str = ""
    summary: str = ""


class RCADraft(BaseModel):
    raw_markdown: str
    alert_title: str
    generated_at: str
