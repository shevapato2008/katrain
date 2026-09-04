"""新账号的赠额必须是 0：不能再从列默认值/pydantic 默认值里白拿 10000。

真实的注册赠额（如果将来要发）走 `settings.BILLING_SIGNUP_GRANT` + `billing.grant`，
是一条走账本的、可审计的路径，而不是一个谁都读得到的列默认值。
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def test_orm_default_is_zero(db):
    u = models_db.User(username="newbie", hashed_password="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    assert u.credits == 0


def test_pydantic_default_is_zero():
    from katrain.web.models import User

    u = User(username="newbie")
    assert u.credits == 0


def test_signup_grant_default_is_zero():
    from katrain.web.core.config import settings

    assert settings.BILLING_SIGNUP_GRANT == 0
