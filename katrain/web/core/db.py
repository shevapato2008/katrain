from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from katrain.web.core.config import settings
import logging

logger = logging.getLogger("katrain_web")

# 1. Create SQLAlchemy Engine
# The engine is the starting point for any SQLAlchemy application.
# It's "home base" for the actual database and its DBAPI.
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite specific: allow multi-threaded access for dev convenience
    connect_args["check_same_thread"] = False
    logger.info(f"Database: Using SQLite at {settings.DATABASE_URL}")
else:
    logger.info(
        f"Database: Using PostgreSQL/External DB at {settings.DATABASE_URL.split('@')[-1]}"
    )  # Log safe part of URL

_pool_kwargs = {}
if not settings.DATABASE_URL.startswith("sqlite"):
    _pool_kwargs["pool_size"] = 20
    _pool_kwargs["max_overflow"] = 40

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,  # Auto-reconnect if connection is lost
    echo=False,  # Set to True to see raw SQL queries
    **_pool_kwargs,
)


def enable_sqlite_foreign_keys(target_engine) -> None:
    """Make SQLite enforce the same declared foreign keys as PostgreSQL."""
    if target_engine.dialect.name != "sqlite":
        return

    @event.listens_for(target_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


enable_sqlite_foreign_keys(engine)

# 2. Create SessionLocal Class
# Each instance of the SessionLocal class will be a database session.
# The class itself is not a database session yet.
# But once we create an instance of the SessionLocal class, this instance will be the actual database session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. Create Base Class
# Later we will inherit from this class to create each of the database models or classes (the ORM models)
Base = declarative_base()


# Dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
