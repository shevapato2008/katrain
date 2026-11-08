"""Public cloud-only WeChat callback; raw bounded bytes authenticate the fact."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from katrain.web.api.v1.endpoints.billing import NoStoreBillingRoute
from katrain.web.core.config import settings
from katrain.web.core.db import get_db
from katrain.web.core import payments, wechat_payments

router = APIRouter(route_class=NoStoreBillingRoute)
MAX_NOTIFICATION_BYTES = 64 * 1024


def _accept(db, headers, body):
    from katrain.web.core.wechat_native import WechatNativeClient, WechatNativeError

    try:
        client = WechatNativeClient.from_settings(settings)
        transaction = client.decode_notification(headers, body)
        if transaction.get("trade_state") != "SUCCESS":
            raise WechatNativeError("invalid_payload")
        # Only the verified transaction selects the owner/order. No user auth or
        # unverified body fields enter fulfillment, and commit precedes the 204.
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SET LOCAL lock_timeout = '1500ms'"))
            db.execute(text("SET LOCAL statement_timeout = '2500ms'"))
        wechat_payments.apply_transaction_in_transaction(
            db, transaction=transaction, now=datetime.now(timezone.utc), settings=settings
        )
        db.commit()
    except WechatNativeError:
        db.rollback()
        raise HTTPException(400, detail={"code": "invalid_payment_notification"}) from None
    except payments.PaymentError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, detail={"code": exc.code}) from None
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail={"code": "payment_conflict"}) from None
    except DBAPIError:
        db.rollback()
        raise HTTPException(503, detail={"code": "payment_notification_retry"}) from None
    except Exception:
        db.rollback()
        raise HTTPException(503, detail={"code": "payment_notification_retry"}) from None


@router.post("/notify", status_code=204)
async def notify(request: Request, db: Session = Depends(get_db)):
    if settings.KATRAIN_MODE != "server":
        raise HTTPException(404, detail={"code": "not_found"})
    declared = request.headers.get("content-length")
    if declared:
        try:
            size = int(declared)
        except ValueError:
            raise HTTPException(400, detail={"code": "invalid_payment_notification"}) from None
        if size < 0 or size > MAX_NOTIFICATION_BYTES:
            raise HTTPException(413, detail={"code": "payment_notification_too_large"})
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > MAX_NOTIFICATION_BYTES:
            raise HTTPException(413, detail={"code": "payment_notification_too_large"})
        raw.extend(chunk)
    await run_in_threadpool(_accept, db, dict(request.headers), bytes(raw))
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
