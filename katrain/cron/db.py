"""Independent SQLAlchemy engine and session factory for katrain-cron."""

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from katrain.cron import config

logger = logging.getLogger("katrain_cron")

# Build engine with connection pooling suitable for concurrent analysis jobs.
_engine_kwargs: dict = {"pool_pre_ping": True, "echo": False}

if config.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    logger.info("Database: Using SQLite at %s", config.DATABASE_URL)
else:
    _engine_kwargs["pool_size"] = config.DATABASE_POOL_SIZE
    _engine_kwargs["max_overflow"] = config.DATABASE_MAX_OVERFLOW
    logger.info("Database: Using PostgreSQL at %s", config.DATABASE_URL.split("@")[-1])

engine = create_engine(config.DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
