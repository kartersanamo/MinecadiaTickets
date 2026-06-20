"""
logger.py

This file is responsible for setting up the logging configuration for the Minecadia Tickets bot. It defines a custom
logging formatter that formats log messages with timestamps in EST and includes the log level, function name, and
message content. The logs are written to both the console and rotating log files that are created daily at midnight.
The log files are stored in a "logs" directory and are named with the current date in the format "YYYY-MM-DD.log".
The logging configuration is defined using a dictionary and applied using the logging.config module.

Copyright (c) 2026 Karter Sanamo
License: MIT
"""

from logging.handlers import TimedRotatingFileHandler
from pytz.tzinfo import StaticTzInfo, DstTzInfo
from typing import Any
import logging.config
import datetime
import pytz
import os

GRAY: str = "\033[90m"
LIGHT_PINK: str = "\033[95m"
RESET: str = "\033[0m"

EST: Any | StaticTzInfo | DstTzInfo = pytz.timezone(zone = "US/Eastern")
current_time_est: datetime.datetime = datetime.datetime.now(tz = EST)
log_filename: str = f"logs/{current_time_est.strftime('%Y-%m-%d')}.log"

class ESTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt = None) -> str:
        dt: datetime.datetime = datetime.datetime.fromtimestamp(record.created, tz = EST)
        if datefmt:
            s: str = dt.strftime(datefmt)
        else:
            s: str = dt.strftime("%Y-%m-%d %H:%M:%S.%f EST")
        return s

class CustomTimedRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, filename, when='midnight', interval=1, backupCount=7, encoding=None, delay=False, utc=False, atTime=None) -> None:
        super().__init__(filename = filename, when =  when, interval =  interval, backupCount = backupCount, encoding = encoding, delay = delay, utc = utc, atTime = atTime)
        if not hasattr(self, 'suffix'):
            self.suffix = "%Y-%m-%d"

    def doRollover(self) -> None:
        if self.stream is not None:
            self.stream.close()
        current_time = int(self.rolloverAt - self.interval)
        dt: datetime.datetime = datetime.datetime.fromtimestamp(current_time, tz = EST)
        dfn: str = dt.strftime(self.suffix)
        self.filename: str = dfn
        if self.backupCount > 0:
            for s in self.getFilesToDelete():
                os.remove(path = s)
        self.mode = 'w'
        self.stream = self._open()
        self.rolloverAt = self.rolloverAt + self.interval

LOGGING_CONFIG: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "file": {
            "format": "%(levelname)-10s  %(asctime)s  %(funcName)-15s : %(message)s",
            "()": ESTFormatter
        },
        "standard": {
            "format": f"{GRAY}%(asctime)s{RESET} %(levelname)-8s {LIGHT_PINK}%(name)s{RESET} %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "()": ESTFormatter
        }
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "standard"
        },
        "file": {
            "level": "DEBUG",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": log_filename,
            "when": "midnight",
            "interval": 1,
            "backupCount": 7,
            "formatter": "file"
        }
    },
    "loggers": {
        "Tasks": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False
        },
        "Commands": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False
        },
        "discord": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False
        }
    }
}

logging.config.dictConfig(config = LOGGING_CONFIG)

for logger_name in LOGGING_CONFIG["loggers"]:
    logger: logging.Logger = logging.getLogger(name = logger_name)
    for handler in logger.handlers:
        if isinstance(handler, TimedRotatingFileHandler):
            logger.removeHandler(handler)
            new_handler: CustomTimedRotatingFileHandler = CustomTimedRotatingFileHandler(
                filename = handler.baseFilename,
                when = handler.when,
                interval = handler.interval,
                backupCount = handler.backupCount,
                encoding = handler.encoding,
                delay = handler.delay,
                utc = handler.utc,
                atTime = handler.atTime
            )
            new_handler.setFormatter(fmt = handler.formatter)
            logger.addHandler(hdlr = new_handler)