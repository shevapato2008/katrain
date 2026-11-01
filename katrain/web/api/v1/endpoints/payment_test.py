"""Routes registered solely for explicit isolated TEST mock deployments."""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from katrain.web.api.v1.endpoints.auth import get_current_admin_user
from katrain.web.core import models_db as m, payment_mock, payments
from katrain.web.core.db import get_db


def _now():
    return datetime.now(timezone.utc)


class MockEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: str = Field(min_length=1, max_length=64)
    owner_id: int = Field(gt=0)
    environment: Literal["test", "development"]
    amount_fen: int = Field(gt=0, strict=True)
    provider_tx_id: str = Field(min_length=1, max_length=128)
    status: Literal["paid", "failed"]
    deliver: bool = True


class MockRefund(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_id: int = Field(gt=0)
    environment: Literal["test", "development"]
    amount_fen: int = Field(gt=0, strict=True)
    provider_tx_id: str = Field(min_length=1, max_length=128)
    refund_ref: str = Field(min_length=1, max_length=160)


def _error(db, exc):
    db.rollback()
    raise HTTPException(
        exc.status_code, detail={"code": exc.code, "message": exc.detail}, headers={"Cache-Control": "no-store"}
    ) from None


def register_test_payment_routes(parent, *, runtime_settings):
    """Never exposes a success button/callback on ordinary production applications."""
    if runtime_settings.KATRAIN_ENVIRONMENT not in {"test", "development"} or runtime_settings.PAYMENTS_MODE != "mock":
        return
    from katrain.web.api.v1.endpoints.billing import NoStoreBillingRoute

    router = APIRouter(route_class=NoStoreBillingRoute)

    @router.post("/events")
    async def provider_event(
        body: MockEvent,
        response: Response,
        signature: str | None = Header(default=None, alias="X-Mock-Signature"),
        admin=Depends(get_current_admin_user),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "no-store"
        try:
            payload = body.model_dump(exclude={"deliver"})
            now = _now()
            order = payment_mock.record_event_in_transaction(
                db,
                event=payload,
                signature=signature,
                admin_user_id=admin.id,
                now=now,
                settings=runtime_settings,
                deliver=body.deliver,
            )
            db.commit()
            return payments.order_receipt(db, order, now=now, payments_mode=runtime_settings.PAYMENTS_MODE)
        except payments.PaymentError as exc:
            _error(db, exc)
        except IntegrityError:
            _error(db, payments.PaymentError("provider_transaction_conflict", 409))

    @router.post("/orders/{order_id}/refund")
    async def refund_order(
        order_id: str,
        body: MockRefund,
        response: Response,
        signature: str | None = Header(default=None, alias="X-Mock-Signature"),
        admin=Depends(get_current_admin_user),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "no-store"
        try:
            payments.require_mock_database(db, runtime_settings)
            payment_mock.verify_event(
                {"order_id": order_id, **body.model_dump()},
                signature=signature,
                secret=runtime_settings.PAYMENT_MOCK_EVENT_SECRET,
            )
            if not db.query(m.User.id).filter_by(id=admin.id, is_admin=True).first():
                raise payments.PaymentError("test_admin_required", 403)
            # Validate the original payment identity and full amount before any asset mutation.
            payments._user(db, body.owner_id)
            order = payments._order(db, body.owner_id, order_id)
            payments.validate_event_binding(
                order, {"order_id": order_id, "status": "paid", **body.model_dump()}, runtime_settings
            )
            now = _now()
            order = payments.refund_order_in_transaction(
                db,
                user_id=body.owner_id,
                order_id=order_id,
                refund_ref=body.refund_ref,
                now=now,
                settings=runtime_settings,
            )
            db.commit()
            return payments.order_receipt(db, order, now=now, payments_mode=runtime_settings.PAYMENTS_MODE)
        except payments.PaymentError as exc:
            _error(db, exc)
        except IntegrityError:
            _error(db, payments.PaymentError("refund_key_conflict", 409))

    parent.include_router(router, prefix="/payments/test", tags=["test-payments"])
