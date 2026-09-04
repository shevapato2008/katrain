"""额度桶：惰性开桶、原子消费、周期到点自动换桶（无 cron 重置任务）。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def db_user(db):
    u = models_db.User(username="u1", hashed_password="x")
    db.add(u); db.commit(); db.refresh(u)
    return db, u


def test_quota_bucket_table_exists():
    assert hasattr(models_db, "QuotaBucket")


def test_bucket_is_unique_per_user_kind_period(db_user):
    db, u = db_user
    mk = lambda: models_db.QuotaBucket(
        user_id=u.id, kind="free_report", period_key="W:2026-W36", allowance=1, used=0
    )
    db.add(mk()); db.commit()
    db.add(mk())
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_quota_buckets_is_protected_from_drift_rebuild():
    """重建这张表 = 给所有人重置额度，必须进保护名单。"""
    from katrain.web.core import migrations
    assert "quota_buckets" in migrations.PROTECTED_TABLES
