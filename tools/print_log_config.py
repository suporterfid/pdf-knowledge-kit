import json
import logging
import os
import sys


def get_log_config():
    log_dir = os.getenv("LOG_DIR", "logs")
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_json = os.getenv("LOG_JSON", "false").lower() == "true"
    retention_days = int(os.getenv("LOG_RETENTION_DAYS", "7"))
    rotate_utc = os.getenv("LOG_ROTATE_UTC", "false").lower() == "true"

    log_level = getattr(logging, log_level_str, logging.INFO)

    return {
        "log_dir": os.path.abspath(log_dir),
        "log_level": logging.getLevelName(log_level),
        "log_json": log_json,
        "retention_days": retention_days,
        "rotate_utc": rotate_utc,
    }


def main():
    sys.stdout.write(json.dumps(get_log_config(), indent=2) + "\n")


if __name__ == "__main__":
    main()
