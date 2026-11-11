"""Phone/password candidates never install a shared board identity before /me + CAS."""

import asyncio
import json

import httpx
import pytest

from katrain.web.core.remote_client import CloudIdentityChangedError, RemoteAPIClient


async def client_with_handler(handler):
    client = RemoteAPIClient("http://cloud.test", "otp-box")
    await client._client.aclose()
    client._client = httpx.AsyncClient(base_url="http://cloud.test", transport=httpx.MockTransport(handler))
    return client


@pytest.mark.asyncio
async def test_password_candidate_uses_canonical_me_before_install():
    seen = []

    async def handler(request):
        seen.append(request)
        if request.url.path.endswith("/login"):
            return httpx.Response(200, json={"access_token": "candidate-a", "refresh_token": "refresh-a"})
        assert request.headers["authorization"] == "Bearer candidate-a"
        return httpx.Response(200, json={"id": 17, "username": "canonical-a", "uuid": "a" * 32})

    remote = await client_with_handler(handler)
    try:
        candidate = await remote.login("input-alias", "private-password")
        assert not remote.is_authenticated
        assert candidate.user["username"] == "canonical-a"
        remote.install_login_candidate(candidate, user_id=7)
        assert remote.cloud_session_is(7)
        assert remote._access_token == "candidate-a"
        assert [request.url.path for request in seen] == ["/api/v1/auth/login", "/api/v1/auth/me"]
    finally:
        await remote.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["switch", "logout", "new_login"])
async def test_pending_candidate_cannot_install_after_identity_changes(action):
    entered, release = asyncio.Event(), asyncio.Event()

    async def handler(request):
        if request.url.path.endswith("/login"):
            return httpx.Response(200, json={"access_token": "candidate-a", "refresh_token": "refresh-a"})
        entered.set()
        await release.wait()
        return httpx.Response(200, json={"id": 17, "username": "canonical-a"})

    remote = await client_with_handler(handler)
    pending = asyncio.create_task(remote.login("account-a", "private-password"))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        if action == "switch":
            remote.set_tokens("token-b", "refresh-b", user_id=8)
        elif action == "logout":
            remote.clear_tokens()
        else:
            remote.begin_login_attempt()
        release.set()
        with pytest.raises(CloudIdentityChangedError):
            await pending
        assert remote._access_token == ("token-b" if action == "switch" else None)
    finally:
        release.set()
        await asyncio.gather(pending, return_exceptions=True)
        await remote.close()


@pytest.mark.asyncio
async def test_phone_candidate_posts_only_opaque_challenge_and_confirms_me():
    seen = []

    async def handler(request):
        seen.append(request)
        if request.url.path.endswith("/phone/login"):
            assert json.loads(request.content) == {"challenge_id": "opaque", "code": "123456", "flow_id": "f" * 32}
            assert not request.url.query
            return httpx.Response(200, json={"access_token": "otp-a", "refresh_token": "otp-refresh"})
        assert request.headers["authorization"] == "Bearer otp-a"
        return httpx.Response(200, json={"id": 19, "username": "u_canonical", "uuid": "b" * 32})

    remote = await client_with_handler(handler)
    try:
        method = getattr(remote, "phone_login", None)
        assert callable(method), "phone login candidate adapter is missing"
        candidate = await method({"challenge_id": "opaque", "code": "123456", "flow_id": "f" * 32})
        assert candidate.user["username"] == "u_canonical" and not remote.is_authenticated
        assert len(seen) == 2
    finally:
        await remote.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["status", "bind_challenge"])
async def test_private_phone_request_never_changes_to_new_users_bearer(operation):
    entered, release = asyncio.Event(), asyncio.Event()
    seen = []

    async def handler(request):
        seen.append(request)
        entered.set()
        await release.wait()
        return httpx.Response(401, json={"detail": {"code": "authentication_required"}})

    remote = await client_with_handler(handler)
    remote.set_tokens("token-a", "refresh-a", user_id=7)
    try:
        method = getattr(remote, "phone_status" if operation == "status" else "phone_challenge", None)
        assert callable(method), "identity-bound phone adapter is missing"
        if operation == "status":
            pending = asyncio.create_task(method(expected_user_id=7))
        else:
            pending = asyncio.create_task(
                method({"phone": "13800138000", "purpose": "bind", "flow_id": "f" * 32}, expected_user_id=7)
            )
        await asyncio.wait_for(entered.wait(), 2)
        remote.set_tokens("token-b", "refresh-b", user_id=8)
        release.set()
        with pytest.raises(CloudIdentityChangedError):
            await pending
        assert len(seen) == 1 and seen[0].headers["authorization"] == "Bearer token-a"
        assert remote.cloud_session_is(8)
    finally:
        release.set()
        await remote.close()
