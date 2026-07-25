import logging
import sys

from pythonjsonlogger import jsonlogger

from app.config.settings import get_settings


def configure_logging() -> None:
    """Text locally (readable in a terminal, the format every log line in this project has used
    so far), JSON in production (LOG_FORMAT=json - set in the ECS task definition, see
    terraform/aws/ecs.tf) so a log shipper (e.g. CloudWatch Logs, or Loki via Promtail) can parse
    fields instead of regexing a formatted string. Same log call sites either way - callers pass
    structured context via `extra={...}` (see request_logging.py), which JsonFormatter merges
    into real JSON fields and the plain text formatter silently ignores, exactly like today."""
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)

    if settings.log_format == "json":
        handler.setFormatter(jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
