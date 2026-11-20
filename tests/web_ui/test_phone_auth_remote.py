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
@pytest.mark.parametrize("operation", ["status", "bind_challenge", "bind", "password"])
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
        method = getattr(
            remote,
            {
                "status": "phone_status",
                "bind_challenge": "phone_challenge",
                "bind": "phone_bind",
                "password": "phone_password",
            }[operation],
            None,
        )
        assert callable(method), "identity-bound phone adapter is missing"
        if operation == "status":
            pending = asyncio.create_task(method(expected_user_id=7))
        elif operation == "bind_challenge":
            pending = asyncio.create_task(
                method({"phone": "13800138000", "purpose": "bind", "flow_id": "f" * 32}, expected_user_id=7)
            )
        else:
            pending = asyncio.create_task(
                method(
                    {
                        "challenge_id": "a" * 48,
                        "code": "123456",
                        "flow_id": "f" * 32,
                        "current_password": "private-password",
                    },
                    expected_user_id=7,
                )
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


@pytest.mark.asyncio
async def test_continue_candidate_preserves_grant_and_confirms_canonical_me():
    seen = []
    payload = {
        "challenge_id": "a" * 48,
        "flow_id": "f" * 32,
        "code": "123456",
        "public_username": "棋手",
        "current_password": None,
    }

    async def handler(request):
        seen.append(request)
        if request.url.path.endswith("/phone/continue"):
            assert json.loads(request.content) == payload and "authorization" not in request.headers
            return httpx.Response(200, json={"access_token": "candidate", "signup_grant_credits": 5000})
        assert request.headers["authorization"] == "Bearer candidate"
        return httpx.Response(200, json={"id": 17, "username": "u_" + "a" * 20, "public_username": "棋手"})

    remote = await client_with_handler(handler)
    remote.set_tokens("installed-a", "refresh-a", user_id=7)
    try:
        assert callable(getattr(remote, "phone_continue", None)), "continuation cloud adapter is missing"
        candidate = await remote.phone_continue(payload)
        assert candidate.tokens["signup_grant_credits"] == 5000 and candidate.user["public_username"] == "棋手"
        assert remote._access_token == "installed-a" and remote.cloud_session_is(7)
        assert len(seen) == 2
    finally:
        await remote.close()


@pytest.mark.asyncio
async def test_password_204_keeps_installed_identity_without_json_or_token_install():
    seen = []

    async def handler(request):
        seen.append(request)
        assert (
            request.url.path == "/api/v1/auth/phone/password"
            and request.headers["authorization"] == "Bearer installed-a"
        )
        assert json.loads(request.content)["new_password"] == "private-new-password"
        return httpx.Response(204)

    remote = await client_with_handler(handler)
    remote.set_tokens("installed-a", "refresh-a", user_id=7)
    generation = remote._identity_generation
    try:
        assert callable(getattr(remote, "phone_password", None)), "password cloud adapter is missing"
        result = await remote.phone_password(
            {"challenge_id": "a" * 48, "flow_id": "f" * 32, "code": "123456", "new_password": "private-new-password"},
            expected_user_id=7,
        )
        assert result is None and len(seen) == 1
        assert remote._access_token == "installed-a" and remote.cloud_session_is(7)
        assert remote._identity_generation == generation
    finally:
        await remote.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("password", [None, "wrong-private-password"])
async def test_bind_password_refusal_spends_one_attempt_without_refresh_or_replay(password):
    seen = []

    async def handle(request):
        seen.append(request)
        if request.url.path.endswith("/refresh"):
            return httpx.Response(200, json={"access_token": "refreshed-a"})
        return httpx.Response(401, json={"detail": {"code": "bind_reauth_failed"}})

    remote = await client_with_handler(handle)
    remote.set_tokens("token-a", "refresh-a", user_id=7)
    payload = {"challenge_id": "a" * 48, "code": "123456", "flow_id": "f" * 32}
    if password is not None:
        payload["current_password"] = password
    try:
        with pytest.raises(httpx.HTTPStatusError) as caught:
            await remote.phone_bind(payload, expected_user_id=7)
        assert caught.value.response.json() == {"detail": {"code": "bind_reauth_failed"}}
        assert len(seen) == 1 and seen[0].url.path == "/api/v1/auth/phone/bind"
        assert remote.cloud_session_is(7) and not remote.auth_required
        assert remote._access_token == "token-a"
    finally:
        await remote.close()


@pytest.mark.asyncio
async def test_bind_expired_bearer_still_refreshes_once_with_original_identity():
    seen = []

    async def handle(request):
        seen.append(request)
        if request.url.path.endswith("/refresh"):
            assert json.loads(request.content) == {"refresh_token": "refresh-a"}
            return httpx.Response(200, json={"access_token": "refreshed-a"})
        if request.headers["authorization"] == "Bearer token-a":
            return httpx.Response(401, json={"detail": {"code": "authentication_required"}})
        assert request.headers["authorization"] == "Bearer refreshed-a"
        return httpx.Response(200, json={"bound": True, "masked_phone": "+86 138****8000"})

    remote = await client_with_handler(handle)
    remote.set_tokens("token-a", "refresh-a", user_id=7)
    try:
        result = await remote.phone_bind(
            {"challenge_id": "a" * 48, "code": "123456", "flow_id": "f" * 32, "current_password": "private-password"},
            expected_user_id=7,
        )
        assert result == {"bound": True, "masked_phone": "+86 138****8000"}
        assert [request.url.path for request in seen] == [
            "/api/v1/auth/phone/bind",
            "/api/v1/auth/refresh",
            "/api/v1/auth/phone/bind",
        ]
        assert remote.cloud_session_is(7) and not remote.auth_required
    finally:
        await remote.close()


@pytest.mark.asyncio
async def test_phone_profile_required_never_refreshes_or_installs():
    seen = []

    async def handler(request):
        seen.append(request)
        return httpx.Response(409, json={"detail": {"code": "profile_required", "mode": "register"}})

    remote = await client_with_handler(handler)
    remote.set_tokens("old-a", "old-refresh", user_id=7)
    try:
        with pytest.raises(httpx.HTTPStatusError):
            await remote.phone_login({"challenge_id": "opaque", "code": "123456", "flow_id": "f" * 32})
        assert len(seen) == 1 and not seen[0].url.query
        assert remote.cloud_session_is(7) and remote._access_token == "old-a"
    finally:
        await remote.close()


@pytest.mark.asyncio
async def test_registration_candidate_retains_grant_and_public_name_before_install():
    seen = []

    async def handler(request):
        seen.append(request)
        if request.url.path.endswith("/phone/register"):
            assert json.loads(request.content)["password"] == "Unicode密码也可以登录很好"
            return httpx.Response(
                200, json={"access_token": "new-a", "refresh_token": "new-r", "signup_grant_credits": 5000}
            )
        assert request.headers["authorization"] == "Bearer new-a"
        return httpx.Response(200, json={"id": 17, "username": "u_" + "a" * 20, "public_username": "新棋手"})

    remote = await client_with_handler(handler)
    try:
        candidate = await remote.phone_register(
            {
                "challenge_id": "opaque",
                "code": "123456",
                "flow_id": "f" * 32,
                "public_username": "新棋手",
                "password": "Unicode密码也可以登录很好",
            }
        )
        assert candidate.tokens["signup_grant_credits"] == 5000
        assert candidate.user["public_username"] == "新棋手" and not remote.is_authenticated
        remote.begin_login_attempt()
        with pytest.raises(CloudIdentityChangedError):
            remote.install_login_candidate(candidate, user_id=7)
        assert not remote.is_authenticated and len(seen) == 2
    finally:
        await remote.close()
