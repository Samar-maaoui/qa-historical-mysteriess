"""Logs: readable text for development, one JSON object per line for servers (LOG_FORMAT=json).
Events never contain the text of a question or an e-mail address."""
import json
import logging
import sys
import time


class JsonFormatter(logging.Formatter):
    def format(self, record):
        out = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + "Z", "level": record.levelname, "event": record.getMessage()}
        out.update(getattr(record, "fields", {}))
        if record.exc_info:
            out["error"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    def format(self, record):
        fields = " ".join(f"{k}={v}" for k, v in getattr(record, "fields", {}).items())
        return f"{time.strftime('%H:%M:%S', time.localtime(record.created))} {record.levelname} {record.getMessage()} {fields}".rstrip()


def setup(stream=None, fmt=None, level="INFO"):
    logger = logging.getLogger("qa")
    logger.handlers.clear()
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    logger.propagate = False
    return logger


def log_event(event, **fields):
    logging.getLogger("qa").info(event, extra={"fields": fields})
