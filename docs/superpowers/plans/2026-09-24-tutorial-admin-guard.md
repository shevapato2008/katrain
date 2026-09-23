# 教程写接口与设备列表只许管理员（切片 0）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 堵上三个安全问题：教程的四个写接口未登录也能调用；`GET /board/devices` 把所有盒子的 IP 发给任意登录用户；生产上的 `admin/admin` 还能登录。同时让教程页只对管理员显示编辑控件。

**Architecture:** 后端把 5 个接口的依赖换成现成的 `get_current_admin_user`（`katrain/web/api/v1/endpoints/auth.py:155`）。前端在 `AuthContext` 的 User 类型里声明 `is_admin`（`/auth/me` 一直在返回这个字段），`TutorialFigurePage` 根据它决定是否渲染编辑控件。`admin/admin` 怎么处置由 Fan 决定，按他的决定改生产库。

**Tech Stack:** FastAPI + SQLAlchemy + pytest（httpx ASGITransport）；React 19 + MUI 7 + vitest + Playwright（vite dev）。

**Spec:** `docs/superpowers/specs/2026-09-24-admin-console-design.md` §4

## Global Constraints

- 顺序：**先测试机 home-ubuntu（go.sailorvoyage.top），再生产 ucloud-v100（modelstella.com）**（Fan 2026-08-31）。
- 目标视口 1440×900。
- 布局相关的结论只认真实浏览器量出来的数，不写 jsdom 几何断言。
- 新文件名不许以 `log` 开头（根 `.gitignore:16` 的 `log*` 加上 `core.ignorecase=true` 会静默吞掉）。
- 不在共享的主工作树 `~/Repositories/katrain` 里切分支或提交；所有工作都在 worktree `~/Repositories/katrain-admin-console`（分支 `feature/admin-console`）里做。
- 任何写生产库、推送、部署的动作，**执行当下都要 Fan 点头**（本计划获批不算）。
- 提交信息末尾加 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`。

## Review Focus

- 已登录但不是管理员的用户打开教程页：应该看到讲解、音频、原书页，**一个编辑按钮都没有**，而不是按钮都在、点了才报 403 → Task 3 的「非管理员只读」用例。
- 未登录用户（`user` 为空）打开教程页，应与非管理员一样只读 → Task 3 的「未登录只读」用例。
- 管理员仍能看到并使用全部编辑控件（别把管理员也藏了）→ Task 3 的「管理员看得到编辑控件」用例。
- 盒子用普通账号上报心跳，必须照旧成功（只收紧列表，不收紧心跳）→ Task 2 的 `test_real_user_can_heartbeat_but_not_list_devices`。
- 管理员写入棋盘后，历史记录里的 `changed_by` 应该是管理员用户名，不再是 `"anonymous"` → Task 1 的 `test_tutorial_writer_admin_2xx`。

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `katrain/web/api/v1/endpoints/tutorials.py` | 改 | 四个写接口改成只许管理员 |
| `katrain/web/api/v1/endpoints/board.py` | 改 | `GET /devices` 改成只许管理员 |
| `tests/web_ui/test_guest_write_block.py` | 改 | 原来「未登录可写」的锁换成「未登录 401 / 非管理员 403 / 管理员 200」；拆分设备列表的用例 |
| `tests/web_ui/test_tutorial_db_api.py` | 改 | 夹具里的 `testadmin` 设为真管理员，再加一条「非管理员 403」 |
| `katrain/web/ui/src/context/AuthContext.tsx` | 改 | User 类型声明 `is_admin?: boolean` |
| `katrain/web/ui/src/galaxy/pages/tutorials/TutorialFigurePage.tsx` | 改 | 编辑控件只给管理员 |
| `katrain/web/ui/src/galaxy/pages/tutorials/TutorialFigurePage.test.tsx` | 改 | 覆盖管理员、非管理员、未登录三种情况 |
| `superpowers/tracks/admin-console/slice0/` | 新建 | 截图和承重实测记录（证据，不是代码） |

---

### Task 0: 准备 worktree 环境并记录测试基线

**Files:**
- 无代码改动；基线文件写到 `/Users/fan/Repositories/katrain-admin-console/.superpowers/baseline/`（`.superpowers/` 已被 git 忽略；如果没被忽略，就改放 scratchpad）

**Interfaces:**
- Produces：`.superpowers/baseline/web_ui_failed_before.txt`（基线里失败用例的**名字**，一行一个，已排序）

- [ ] **Step 1：装 Python 依赖**（worktree 里是空的；只跑 `uv sync` 不会装 fastapi）

Run: `cd /Users/fan/Repositories/katrain-admin-console && uv sync --extra web`
Expected：以 `Installed`/`Audited` 结尾，没有报错。

- [ ] **Step 2：装前端依赖**

Run: `cd /Users/fan/Repositories/katrain-admin-console/katrain/web/ui && npm ci`
Expected：`added N packages`，没有 `ERR!`。

- [ ] **Step 3：确认 `.superpowers/` 被 git 忽略**

Run: `cd /Users/fan/Repositories/katrain-admin-console && git check-ignore -v .superpowers/baseline/x.txt`
Expected：输出里有一条匹配的忽略规则。**如果没有输出**，就把下面所有 `.superpowers/baseline/` 换成 `/private/tmp/claude-501/admin-guard-baseline/`。

- [ ] **Step 4：跑 web_ui 基线，只记失败用例的名字**

```bash
cd /Users/fan/Repositories/katrain-admin-console
mkdir -p .superpowers/baseline
CI=true uv run pytest tests/web_ui -q -p no:cacheprovider --continue-on-collection-errors -rfE 2>&1 \
  | grep -E '^(FAILED|ERROR) ' | sed -E 's/ - .*//' | sort -u > .superpowers/baseline/web_ui_failed_before.txt
wc -l .superpowers/baseline/web_ui_failed_before.txt
git status --short
```
Expected：`wc -l` 输出一个数（可以是 0）。`git status --short` 应该为空。**如果 `katrain/config.json` 出现在输出里**（有的测试会改写这个已提交的文件），执行 `git checkout -- katrain/config.json` 还原。

---

### Task 1: 教程的四个写接口只许管理员

**Files:**
- Modify: `katrain/web/api/v1/endpoints/tutorials.py`（第 15–18 行的 import；第 150–262 行的四个写接口）
- Test: `tests/web_ui/test_guest_write_block.py`（模块 docstring 第 8–9 行；第 130–150 行附近加辅助函数；第 268–305 行的两条教程用例）
- Test: `tests/web_ui/test_tutorial_db_api.py`（`client_with_auth` 夹具；在文件末尾新增一条用例）

**Interfaces:**
- Consumes：`get_current_admin_user(request, token) -> katrain.web.models.User`（`auth.py:155`；只认 `Authorization: Bearer`；未登录 401，非管理员 403，detail 为 `"Admin privileges required"`）
- Produces：`tests/web_ui/test_guest_write_block.py` 里的 `_create_admin_and_login(app, username="tutorial-admin") -> (headers, user_id, unique_name)`，Task 2 会复用

- [ ] **Step 1：把 `test_guest_write_block.py` 里锁定旧行为的用例改成新的期望**

1a. 模块 docstring 第 8–9 行，把：
```python
  - The four optional-auth tutorial-authoring writers guest-only reject
    (anonymous stays allowed).
```
改成：
```python
  - The four tutorial-authoring writers are ADMIN-ONLY since 2026-09-24:
    anonymous 401, non-admin and guest 403 ("Admin privileges required").
    They used to be guest-only reject with anonymous allowed (R3-F1); see
    docs/superpowers/specs/2026-09-24-admin-console-design.md §4.
```

1b. 在 `_seed_tutorial_figure` 函数之后（它以 `return figure.id` 结尾），插入这两个辅助函数：
```python
async def _create_admin_and_login(app, username="tutorial-admin"):
    """Same as `_create_user_and_login`, then flip is_admin (the test_billing_api idiom)."""
    headers, user_id, unique_name = await _create_user_and_login(app, username)
    with _db(app)() as db:
        db.query(models_db.User).filter(models_db.User.id == user_id).update({"is_admin": True})
        db.commit()
    return headers, user_id, unique_name


def _fake_tts(monkeypatch):
    """generate-audio must not run the real TTS pipeline in a unit test -- only the auth boundary is under test."""

    async def _fake_generate_figure_audio(db, figure, narration):
        figure.narration = narration
        figure.audio_asset = "fake-audio.mp3"
        return figure

    monkeypatch.setattr(
        "katrain.web.api.v1.endpoints.tutorials.generate_figure_audio",
        _fake_generate_figure_audio,
    )
```

1c. 在 `test_tutorial_writer_guest_403` 里，把：
```python
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Guest is read-only"}
```
改成：
```python
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Admin privileges required"}
```

1d. 把**整个** `test_tutorial_writer_anonymous_still_2xx` 函数（从它上面的 `@pytest.mark.asyncio` 装饰器开始，到 `assert resp.status_code == 200, resp.text` 结束）替换成下面三条：
```python
@pytest.mark.asyncio
@pytest.mark.parametrize("method,action,body", TUTORIAL_WRITE_ROUTES, ids=[r[1] for r in TUTORIAL_WRITE_ROUTES])
async def test_tutorial_writer_anonymous_401(full_app, method, action, body, monkeypatch):
    """Admin-only since 2026-09-24: no token at all is 401 (it used to be allowed, R3-F1)."""
    _fake_tts(monkeypatch)
    figure_id = _seed_tutorial_figure(full_app)
    url = f"/api/v1/tutorials/figures/{figure_id}/{action}"
    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await _req(ac, method, url, body=body)
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize("method,action,body", TUTORIAL_WRITE_ROUTES, ids=[r[1] for r in TUTORIAL_WRITE_ROUTES])
async def test_tutorial_writer_non_admin_403(full_app, method, action, body, monkeypatch):
    _fake_tts(monkeypatch)
    headers, _, _ = await _create_user_and_login(full_app, "tutorial-reader")
    figure_id = _seed_tutorial_figure(full_app)
    url = f"/api/v1/tutorials/figures/{figure_id}/{action}"
    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await _req(ac, method, url, headers=headers, body=body)
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Admin privileges required"}


@pytest.mark.asyncio
@pytest.mark.parametrize("method,action,body", TUTORIAL_WRITE_ROUTES, ids=[r[1] for r in TUTORIAL_WRITE_ROUTES])
async def test_tutorial_writer_admin_2xx(full_app, method, action, body, monkeypatch):
    _fake_tts(monkeypatch)
    headers, _, admin_name = await _create_admin_and_login(full_app)
    figure_id = _seed_tutorial_figure(full_app)
    url = f"/api/v1/tutorials/figures/{figure_id}/{action}"
    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        resp = await _req(ac, method, url, headers=headers, body=body)
    assert resp.status_code == 200, resp.text
    if action == "board":
        # The audit trail names the admin, never "anonymous".
        with _db(full_app)() as db:
            history = (
                db.query(models_db.BoardPayloadHistory)
                .filter(models_db.BoardPayloadHistory.figure_id == figure_id)
                .all()
            )
        assert [h.changed_by for h in history] == [admin_name]
```

- [ ] **Step 2：改 `test_tutorial_db_api.py`**

2a. 在 `client_with_auth` 夹具里，把：
```python
    # Create a test user
    user = models_db.User(
        username="testadmin",
        hashed_password="fakehash",
    )
    session.add(user)
```
改成：
```python
    # Create a real admin (tutorial writes are admin-only since 2026-09-24) and a plain user.
    user = models_db.User(
        username="testadmin",
        hashed_password="fakehash",
        is_admin=True,
    )
    session.add(user)
    session.add(models_db.User(username="plainuser", hashed_password="fakehash"))
```

2b. 在文件末尾新增：
```python
def test_update_board_non_admin_forbidden(client_with_auth):
    """Tutorial writes are admin-only (2026-09-24): logged in but not admin => 403."""
    client, _ = client_with_auth
    plain_token = create_access_token(data={"sub": "plainuser"})
    resp = client.put(
        "/api/v1/tutorials/figures/1/board",
        json={"board_payload": {"size": 19, "stones": {"B": [], "W": []}}},
        headers={"Authorization": f"Bearer {plain_token}"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 3：跑测试，确认它们失败，而且失败原因是对的**

Run：
```bash
cd /Users/fan/Repositories/katrain-admin-console
CI=true uv run pytest tests/web_ui/test_guest_write_block.py tests/web_ui/test_tutorial_db_api.py -q -p no:cacheprovider -k "tutorial_writer or update_board" 2>&1 | tail -15
```
Expected：FAIL。
- `test_tutorial_writer_anonymous_401[*]` 失败，是因为拿到了 200；
- `test_tutorial_writer_non_admin_403[*]` 失败，是因为拿到了 200；
- `test_tutorial_writer_guest_403[*]` 失败，是因为 detail 还是 `Guest is read-only`；
- `test_update_board_non_admin_forbidden` 失败，是因为拿到了 200；
- `test_tutorial_writer_admin_2xx[*]` 和 `test_update_board_authenticated_success` 此刻**会通过**（旧代码本来就放行），这是正常的。

- [ ] **Step 4：改 `tutorials.py`**

4a. 第 15–18 行，把：
```python
from katrain.web.api.v1.endpoints.auth import get_current_user_optional
from katrain.web.core.box_sso import is_guest_user
from katrain.web.core.db import get_db
from katrain.web.core.models_db import User
```
改成：
```python
from katrain.web.api.v1.endpoints.auth import get_current_admin_user
from katrain.web.core.db import get_db
from katrain.web.models import User as AuthUser
```
等 Step 4b–4e 全部改完，再确认旧的名字已经没人用了：
Run：`grep -nE "get_current_user_optional|is_guest_user" katrain/web/api/v1/endpoints/tutorials.py; grep -nw "User" katrain/web/api/v1/endpoints/tutorials.py`
Expected：第一条 grep 没有输出；第二条只命中 `from katrain.web.models import User as AuthUser` 这一行。如果还有别处在用 ORM 的 `User`，就把原来的 `from katrain.web.core.models_db import User` 加回来。

4b. `update_figure_board`：把签名里的
```python
    current_user: User | None = Depends(get_current_user_optional),
):
    """Update the board_payload for a figure. Computes viewport server-side.
    Uses optimistic locking via expected_updated_at to prevent silent overwrites."""
    if is_guest_user(current_user):
        raise HTTPException(status_code=403, detail="Guest is read-only")
    figure = db_queries.get_figure(db, figure_id)
```
改成：
```python
    admin: AuthUser = Depends(get_current_admin_user),
):
    """Update the board_payload for a figure. Computes viewport server-side.
    Uses optimistic locking via expected_updated_at to prevent silent overwrites.
    Admin-only since 2026-09-24 (anonymous 401, non-admin/guest 403)."""
    figure = db_queries.get_figure(db, figure_id)
```
再把同一个函数里的
```python
        changed_by=current_user.username if current_user else "anonymous",
        change_type="edit",
```
改成：
```python
        changed_by=admin.username,
        change_type="edit",
```

4c. `generate_audio_for_figure`：把
```python
    current_user: User | None = Depends(get_current_user_optional),
):
    if is_guest_user(current_user):
        raise HTTPException(status_code=403, detail="Guest is read-only")
    figure = db_queries.get_figure(db, figure_id)
```
改成：
```python
    admin: AuthUser = Depends(get_current_admin_user),
):
    figure = db_queries.get_figure(db, figure_id)
```

4d. `update_figure_narration`：把
```python
    current_user: User | None = Depends(get_current_user_optional),
):
    """Update the narration text and optional audio_asset for a figure."""
    if is_guest_user(current_user):
        raise HTTPException(status_code=403, detail="Guest is read-only")
    figure = db_queries.get_figure(db, figure_id)
```
改成：
```python
    admin: AuthUser = Depends(get_current_admin_user),
):
    """Update the narration text and optional audio_asset for a figure. Admin-only."""
    figure = db_queries.get_figure(db, figure_id)
```

4e. `verify_figure`：把
```python
    current_user: User | None = Depends(get_current_user_optional),
):
    """Mark a figure as human-verified. The current board_payload becomes ground truth."""
    import json as _json

    if is_guest_user(current_user):
        raise HTTPException(status_code=403, detail="Guest is read-only")
    figure = db_queries.get_figure(db, figure_id)
```
改成：
```python
    admin: AuthUser = Depends(get_current_admin_user),
):
    """Mark a figure as human-verified. The current board_payload becomes ground truth. Admin-only."""
    import json as _json

    figure = db_queries.get_figure(db, figure_id)
```
再把同一个函数里的
```python
    debug["verified_by"] = current_user.username if current_user else "anonymous"
```
改成：
```python
    debug["verified_by"] = admin.username
```
以及
```python
            changed_by=current_user.username if current_user else "anonymous",
            change_type="verify",
```
改成：
```python
            changed_by=admin.username,
            change_type="verify",
```

- [ ] **Step 5：跑测试，确认通过**

Run：
```bash
CI=true uv run pytest tests/web_ui/test_guest_write_block.py tests/web_ui/test_tutorial_db_api.py -q -p no:cacheprovider 2>&1 | tail -5
git status --short
```
Expected：`passed`，没有 `failed`。`git status` 只列出本任务改动的三个文件（如果 `katrain/config.json` 也出现了，`git checkout -- katrain/config.json` 还原）。

- [ ] **Step 6：提交**

```bash
git add katrain/web/api/v1/endpoints/tutorials.py tests/web_ui/test_guest_write_block.py tests/web_ui/test_tutorial_db_api.py
git commit -m "fix(tutorial): 四个教程写接口只许管理员 —— 此前未登录也能改棋盘/讲解/审核

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git show --stat HEAD | tail -5
```
Expected：`--stat` 里正好是这三个文件。

---

### Task 2: `GET /board/devices` 只许管理员（心跳保持原样）

**Files:**
- Modify: `katrain/web/api/v1/endpoints/board.py:17`（import）、`board.py:84-88`（`list_devices` 的签名）
- Test: `tests/web_ui/test_guest_write_block.py:486-498`（`test_real_user_can_heartbeat_and_list_devices`）

**Interfaces:**
- Consumes：Task 1 的 `_create_admin_and_login(app, username)`

- [ ] **Step 1：拆分用例**。把整个 `test_real_user_can_heartbeat_and_list_devices`（带着它的 `@pytest.mark.asyncio`）替换成：
```python
@pytest.mark.asyncio
async def test_real_user_can_heartbeat_but_not_list_devices(full_app):
    """Heartbeat is the box's own report path: any real user may still write it.
    The device list carries every box's IP: admin-only since 2026-09-24."""
    headers, _, _ = await _create_user_and_login(full_app, "device-user")
    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        beat = await ac.post(
            "/api/v1/board/heartbeat", headers=headers, json={"device_id": "dev-real-1", "queue_depth": 0}
        )
        assert beat.status_code == 200
        assert beat.json()["status"] == "ok"

        listed = await ac.get("/api/v1/board/devices", headers=headers)
        assert listed.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_list_devices(full_app):
    user_headers, _, _ = await _create_user_and_login(full_app, "device-user")
    admin_headers, _, _ = await _create_admin_and_login(full_app, "device-admin")
    async with AsyncClient(transport=ASGITransport(app=full_app), base_url="http://test") as ac:
        beat = await ac.post(
            "/api/v1/board/heartbeat", headers=user_headers, json={"device_id": "dev-real-1", "queue_depth": 0}
        )
        assert beat.status_code == 200

        listed = await ac.get("/api/v1/board/devices", headers=admin_headers)
        assert listed.status_code == 200
        assert any(d["device_id"] == "dev-real-1" for d in listed.json())
```

- [ ] **Step 2：跑测试，确认失败**

Run：`CI=true uv run pytest tests/web_ui/test_guest_write_block.py -q -p no:cacheprovider -k "devices" 2>&1 | tail -6`
Expected：`test_real_user_can_heartbeat_but_not_list_devices` 失败，原因是列表返回了 200 而不是 403；`test_admin_can_list_devices` 通过。

- [ ] **Step 3：改 `board.py`**。第 17 行
```python
from katrain.web.api.v1.endpoints.auth import get_current_user, require_writable_user
```
改成：
```python
from katrain.web.api.v1.endpoints.auth import get_current_admin_user, get_current_user, require_writable_user
```
`list_devices` 的签名
```python
@router.get("/devices")
async def list_devices(
    current_user: User = Depends(require_writable_user),
    db: Session = Depends(get_db),
):
    """List all registered board devices (admin monitoring)."""
```
改成：
```python
@router.get("/devices")
async def list_devices(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """List all registered board devices (admin monitoring). Admin-only since 2026-09-24:
    each row carries the box's IP address."""
```

- [ ] **Step 4：跑整个文件，确认全部通过**

Run：`CI=true uv run pytest tests/web_ui/test_guest_write_block.py -q -p no:cacheprovider 2>&1 | tail -3`
Expected：全部 passed。其中 `test_guest_403_on_all_write_routes[GET:/api/v1/board/devices]` 仍然是 403，只是现在由管理员闸拦下。

- [ ] **Step 5：提交**

```bash
git add katrain/web/api/v1/endpoints/board.py tests/web_ui/test_guest_write_block.py
git commit -m "fix(board): 设备列表只许管理员 —— 它带着每台盒子的 IP；心跳不变

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git show --stat HEAD | tail -4
```

---

### Task 3: 教程页只对管理员显示编辑控件

**Files:**
- Modify: `katrain/web/ui/src/context/AuthContext.tsx:6-17`（`interface User`）
- Modify: `katrain/web/ui/src/galaxy/pages/tutorials/TutorialFigurePage.tsx`：第 39 行（`useAuth`）、第 51–53 行之后（新增 `canEdit`）、第 465–507 行（讲解区）、第 531–535 行（识别调试面板）、第 538–567 行（actions）
- Test: `katrain/web/ui/src/galaxy/pages/tutorials/TutorialFigurePage.test.tsx`

**Interfaces:**
- Consumes：`useAuth()` 返回的 `user?: User | null`，其中 `User.is_admin?: boolean`（本任务新增声明）
- Produces：`canEdit: boolean`，页面内部使用

- [ ] **Step 1：写测试**。在 `TutorialFigurePage.test.tsx` 里：

1a. 把 `beforeEach` 里的
```tsx
    (useAuth as Mock).mockReturnValue({ token: 'fake-token' });
```
改成（原有两条用例从此以管理员身份运行）：
```tsx
    (useAuth as Mock).mockReturnValue({ token: 'fake-token', user: { is_admin: true } });
```

1b. 在 `describe('TutorialFigurePage', () => {` 之前加一个渲染辅助函数：
```tsx
const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/tutorials/sections/1']}>
      <Routes>
        <Route path="/tutorials/sections/:sectionId" element={<TutorialFigurePage />} />
      </Routes>
    </MemoryRouter>
  );

const sectionWithBoard = {
  ...sectionResponse,
  figures: [
    {
      ...sectionResponse.figures[0],
      board_payload: { size: 19, stones: { B: [[3, 3]], W: [] } },
      recognition_debug: { human_verified: false },
    },
  ],
};

const EDIT_BUTTONS = [/编辑讲解/, /生成语音并保存/, /保存文字/, /确认审核/, /逻辑检查/, /^编辑$/, /初始化空棋盘/];
```

1c. 在 `describe` 块里、最后一条 `it` 之后，加上：
```tsx
  it('管理员看得到编辑控件', async () => {
    (TutorialAPI.getSection as Mock).mockResolvedValue(sectionWithBoard);
    renderPage();
    await screen.findByText('旧讲解');
    for (const name of [/编辑讲解/, /确认审核/, /逻辑检查/, /^编辑$/]) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument();
    }
    expect(screen.getByTestId('recognition-debug')).toBeInTheDocument();
  });

  it('非管理员只读：看得到讲解和音频，看不到任何编辑控件', async () => {
    (useAuth as Mock).mockReturnValue({ token: 'fake-token', user: { is_admin: false } });
    (TutorialAPI.getSection as Mock).mockResolvedValue(sectionWithBoard);
    renderPage();
    expect(await screen.findByText('旧讲解')).toBeInTheDocument();
    expect(screen.getByTestId('audio-player')).toHaveTextContent('/assets/tutorial_assets/test-buju/audio/fig_7-old.mp3');
    for (const name of EDIT_BUTTONS) {
      expect(screen.queryByRole('button', { name })).toBeNull();
    }
    expect(screen.queryByTestId('recognition-debug')).toBeNull();
  });

  it('未登录与非管理员一样只读（棋盘为空时也不出现「初始化空棋盘」）', async () => {
    (useAuth as Mock).mockReturnValue({ token: null, user: null });
    renderPage();
    expect(await screen.findByText('旧讲解')).toBeInTheDocument();
    for (const name of EDIT_BUTTONS) {
      expect(screen.queryByRole('button', { name })).toBeNull();
    }
  });
```

- [ ] **Step 2：跑测试，确认失败**

Run：`cd /Users/fan/Repositories/katrain-admin-console/katrain/web/ui && npx vitest run src/galaxy/pages/tutorials/TutorialFigurePage.test.tsx 2>&1 | tail -15`
Expected：「非管理员只读」和「未登录」两条 FAIL，因为按钮还在；「管理员看得到编辑控件」和原有两条 PASS。

- [ ] **Step 3：改 `AuthContext.tsx`**。在 `interface User` 里的 `avatar_url?: string;` 之后加：
```ts
    // Admin flag. `/auth/me` has always returned it (katrain/web/models.py User.is_admin);
    // the client never declared it before 2026-09-24. Only decides which editing controls
    // render — the real gate is the backend (get_current_admin_user).
    is_admin?: boolean;
```

- [ ] **Step 4：改 `TutorialFigurePage.tsx`**

4a. 第 39 行 `const { token } = useAuth();` 改成：
```tsx
  const { token, user } = useAuth();
```

4b. 在 `const showCompare = isWide && compareOpen;` 之后加一行（前面带注释）：
```tsx
  /* 编辑控件只给管理员（2026-09-24）。后端四个写接口已改成 get_current_admin_user，
     不藏的话普通用户点下去只会拿到 403。未登录（user 为空）同样只读。 */
  const canEdit = user?.is_admin === true;
```

4c. 讲解区的标题行：把「编辑讲解」这个 `<Button …>…</Button>` 整个包进 `{canEdit && ( … )}`，改完是：
```tsx
            <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
              <Typography variant="caption" color="text.secondary">语音讲解</Typography>
              {canEdit && (
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<EditIcon />}
                  onClick={() => setIsEditingNarration(v => !v)}
                  aria-label={isEditingNarration ? '收起编辑' : '编辑讲解'}
                >
                  {isEditingNarration ? '收起编辑' : '编辑讲解'}
                </Button>
              )}
            </Box>
```

4d. 把 `{isEditingNarration ? (` 改成 `{canEdit && isEditingNarration ? (`。再把没有讲解文本时显示的那段文字
```tsx
                暂无讲解文本。点击“编辑讲解”后可直接填写并生成语音。
```
改成：
```tsx
                {canEdit ? '暂无讲解文本。点击“编辑讲解”后可直接填写并生成语音。' : '暂无讲解文本。'}
```

4e. 识别调试面板：把 `{currentFigure?.recognition_debug && (` 改成 `{canEdit && currentFigure?.recognition_debug && (`。

4f. actions：把 `actions={(` 改成 `actions={canEdit ? (`，再把 actions 整个 JSX 末尾的 `)}`（紧挨在 `/>` 之前、结束 `<Box sx={{ py: 1.5, borderTop: …`）改成 `) : null}`。改完末尾是这样：
```tsx
          )}
        </Box>
      ) : null}
    />
  );
}
```

- [ ] **Step 5：跑测试、真正的类型检查和 lint**

Run：
```bash
npx vitest run src/galaxy/pages/tutorials/TutorialFigurePage.test.tsx 2>&1 | tail -6
npx tsc -b 2>&1 | tail -5
npx eslint src/galaxy/pages/tutorials/TutorialFigurePage.tsx src/context/AuthContext.tsx
```
Expected：vitest 全部 PASS；`tsc -b` 没有输出（注意别用 `tsc --noEmit`，那个一个文件都不检查）；eslint 没有输出。

- [ ] **Step 6：提交**

```bash
cd /Users/fan/Repositories/katrain-admin-console
git add katrain/web/ui/src/context/AuthContext.tsx katrain/web/ui/src/galaxy/pages/tutorials/TutorialFigurePage.tsx katrain/web/ui/src/galaxy/pages/tutorials/TutorialFigurePage.test.tsx
git commit -m "feat(tutorial): 编辑控件只给管理员；前端声明 User.is_admin

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git show --stat HEAD | tail -5
```

---

### Task 4: 真实浏览器实测右栏承重结构 + 截图，给 Fan 确认

触发理由：非管理员看到的 `board-rail-actions` 变成空的，`board-rail-scroll` 的高度来源就变了（`BoardPageShell.tsx:163-188`）。
这里应该滚动的是 **`board-rail-scroll`**：它既不是 `board-right-rail`，也不是 `board-page-shell`。

**Files:**
- Create（临时，不提交，除非量出了错误数值）：`katrain/web/ui/tests/tutorial-rail-readonly.measure.spec.ts`
- Create：`superpowers/tracks/admin-console/slice0/measurements.md`，以及同目录下的 3 张 png

先把关系式写死（取数之前）：
- R1（所有状态）：`|rail.top − shell.top| ≤ 1` 且 `|rail.bottom − shell.bottom| ≤ 1`（右栏撑满外壳那一行 grid）
- R2（非管理员）：`actions.height == 0`，`|scroll.bottom − rail.bottom| ≤ 1`，`|scroll.top − module.bottom| ≤ 1`（滚动区把让出来的高度全部接住）
- R3（非管理员 + 溢出）：`scroll.scrollHeight > scroll.clientHeight`；写入 `scrollTop = 1e6` 后读回 > 0；滚轮拨一次，`scrollTop` 从 0 变成 > 0
- R4（管理员）：`actions.height > 0`，`|scroll.bottom − actions.top| ≤ 1`
- 「最空」那一态（没有讲解、没有原书文字）同样要满足 R1 和 R2：塌陷类的问题只有在内容最少时才看得出来

- [ ] **Step 1：写测量用例**

```ts
// katrain/web/ui/tests/tutorial-rail-readonly.measure.spec.ts
// 一次性测量：run with `npx playwright test --config=playwright.vite.config.ts tests/tutorial-rail-readonly.measure.spec.ts`
// while `npm run dev` serves :5173. Inputs are faked via page.route; the layout numbers come from the real browser.
import { test, expect, type Page } from '@playwright/test';

const LONG = '这是一段很长的讲解。'.repeat(400);
const EVIDENCE = '../../../superpowers/tracks/admin-console/slice0';
// Empty = use playwright.vite.config.ts's baseURL (:5173). Set MEASURE_BASE when 5173 is taken.
const BASE = process.env.MEASURE_BASE ?? '';

const section = (narration: string | null, bookText: string | null) => ({
  id: 1, chapter_id: 1, section_number: '1', title: '外势和实地', order: 1, figure_count: 1, has_video: false,
  figures: [{
    id: 7, section_id: 1, page: 12, figure_label: '图1', book_text: bookText, page_context_text: null, bbox: null,
    page_image_path: null, board_payload: { size: 19, stones: { B: [[3, 3]], W: [] } }, recognition_debug: null,
    narration, audio_asset: null, video_asset: null, video_duration_ms: null, video_size_bytes: null, order: 1,
    updated_at: '2026-04-10T00:00:00Z',
  }],
});

async function open(page: Page, o: { admin: boolean; narration: string | null; bookText: string | null }) {
  await page.setViewportSize({ width: 1440, height: 900 });
  // Playwright matches the LAST registered route first: catch-all first, specifics after.
  await page.route('**/api/**', (r) => r.fulfill({ status: 404, json: { detail: 'not mocked' } }));
  await page.route('**/api/v1/tutorials/sections/1', (r) => r.fulfill({ json: section(o.narration, o.bookText) }));
  await page.route('**/api/v1/auth/me', (r) =>
    o.admin
      ? r.fulfill({ json: { id: 1, username: 'fan', rank: '1d', credits: 0, is_admin: true } })
      : r.fulfill({ status: 401, json: { detail: 'Not authenticated' } }));
  if (o.admin) await page.addInitScript(() => localStorage.setItem('token', 'fake'));
  await page.goto(`${BASE}/galaxy/tutorials/section/1`);
  // Read back which screen we are on before measuring anything.
  await expect(page).toHaveURL(/\/galaxy\/tutorials\/section\/1$/);
  await expect(page.getByText('1. 外势和实地')).toBeVisible();
}

async function measure(page: Page) {
  return page.evaluate(() => {
    const el = (id: string) => document.querySelector(`[data-testid="${id}"]`) as HTMLElement;
    const r = (id: string) => el(id).getBoundingClientRect();
    const scroll = el('board-rail-scroll');
    return {
      shell: { top: r('board-page-shell').top, bottom: r('board-page-shell').bottom },
      rail: { top: r('board-right-rail').top, bottom: r('board-right-rail').bottom },
      module: { bottom: r('board-rail-module').bottom },
      scroll: { top: r('board-rail-scroll').top, bottom: r('board-rail-scroll').bottom,
                scrollHeight: scroll.scrollHeight, clientHeight: scroll.clientHeight },
      actions: { top: r('board-rail-actions').top, height: r('board-rail-actions').height },
    };
  });
}

const near = (a: number, b: number) => Math.abs(a - b) <= 1;

test('非管理员 + 溢出', async ({ page }) => {
  await open(page, { admin: false, narration: LONG, bookText: LONG });
  const m = await measure(page);
  console.log('nonadmin-overflow', JSON.stringify(m));
  expect(near(m.rail.top, m.shell.top) && near(m.rail.bottom, m.shell.bottom)).toBe(true); // R1
  expect(m.actions.height).toBe(0);                                                          // R2
  expect(near(m.scroll.bottom, m.rail.bottom) && near(m.scroll.top, m.module.bottom)).toBe(true);
  expect(m.scroll.scrollHeight).toBeGreaterThan(m.scroll.clientHeight);                     // R3
  const scroll = page.getByTestId('board-rail-scroll');
  await scroll.evaluate((e) => { e.scrollTop = 1e6; });
  expect(await scroll.evaluate((e) => e.scrollTop)).toBeGreaterThan(0);
  await scroll.evaluate((e) => { e.scrollTop = 0; });
  await scroll.hover();
  await page.mouse.wheel(0, 400);
  await expect.poll(() => scroll.evaluate((e) => e.scrollTop)).toBeGreaterThan(0);
  await scroll.evaluate((e) => { e.scrollTop = 0; });
  await page.screenshot({ path: `${EVIDENCE}/nonadmin-overflow-1440x900.png` });
});

test('非管理员 + 最空', async ({ page }) => {
  await open(page, { admin: false, narration: null, bookText: null });
  const m = await measure(page);
  console.log('nonadmin-minimal', JSON.stringify(m));
  expect(near(m.rail.top, m.shell.top) && near(m.rail.bottom, m.shell.bottom)).toBe(true); // R1
  expect(m.actions.height).toBe(0);                                                          // R2
  expect(near(m.scroll.bottom, m.rail.bottom) && near(m.scroll.top, m.module.bottom)).toBe(true);
  await page.screenshot({ path: `${EVIDENCE}/nonadmin-minimal-1440x900.png` });
});

test('管理员对照', async ({ page }) => {
  await open(page, { admin: true, narration: LONG, bookText: LONG });
  const m = await measure(page);
  console.log('admin-overflow', JSON.stringify(m));
  expect(near(m.rail.top, m.shell.top) && near(m.rail.bottom, m.shell.bottom)).toBe(true); // R1
  expect(m.actions.height).toBeGreaterThan(0);                                               // R4
  expect(near(m.scroll.bottom, m.actions.top)).toBe(true);
  await page.screenshot({ path: `${EVIDENCE}/admin-overflow-1440x900.png` });
});
```

- [ ] **Step 2：起 vite 开发服务器，跑测量**

先确认 5173 端口没有被别的会话占用：`lsof -iTCP:5173 -sTCP:LISTEN`。没有输出，就用 `PORT=5173`；有输出，就换一个空闲端口，例如 `PORT=5183`。

```bash
PORT=5173
mkdir -p /Users/fan/Repositories/katrain-admin-console/superpowers/tracks/admin-console/slice0
cd /Users/fan/Repositories/katrain-admin-console/katrain/web/ui
(npm run dev -- --port $PORT --strictPort > /tmp/admin-guard-vite.log 2>&1 &)
for i in $(seq 1 60); do curl -sf http://127.0.0.1:$PORT >/dev/null && break; sleep 1; done
MEASURE_BASE=$([ "$PORT" = 5173 ] && echo "" || echo "http://127.0.0.1:$PORT") \
  npx playwright test --config=playwright.vite.config.ts tests/tutorial-rail-readonly.measure.spec.ts --reporter=line 2>&1 | tail -30
```
Expected：3 passed，并打印出三行 JSON 数字。

- [ ] **Step 3：处理测量结果**
  - 全部通过：删掉 spec（`rm tests/tutorial-rail-readonly.measure.spec.ts`），把三行 JSON 和 R1–R4 逐条的判定写进 `superpowers/tracks/admin-console/slice0/measurements.md`。这里的像素值只做记录，判定看的是关系式。
  - 有一条**量出了错误数值**：先修布局，重跑直到通过。然后按 vertical-slice 的规定，**保留**这个 spec，改名为 `tests/tutorial-rail-readonly.spec.ts` 作为几何闸，和修复放在同一个提交里。

- [ ] **Step 4：停掉 vite**：`kill $(lsof -tiTCP:$PORT -sTCP:LISTEN) 2>/dev/null || true`，然后用 `lsof -iTCP:$PORT -sTCP:LISTEN` 确认已经没有进程在监听。

- [ ] **Step 5：提交证据**

```bash
cd /Users/fan/Repositories/katrain-admin-console
git add superpowers/tracks/admin-console/slice0/
git commit -m "test(tutorial): 只读右栏承重实测（1440×900，溢出/最空/管理员对照）

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 6：🛑 停，请 Fan 看这三张截图和测量结果，明确确认后才能进入 Task 5。**

---

### Task 5: 回归验证（基线对比）和两套构建

- [ ] **Step 1：跑 web_ui，按名字和基线做差**

```bash
cd /Users/fan/Repositories/katrain-admin-console
CI=true uv run pytest tests/web_ui -q -p no:cacheprovider --continue-on-collection-errors -rfE 2>&1 \
  | grep -E '^(FAILED|ERROR) ' | sed -E 's/ - .*//' | sort -u > .superpowers/baseline/web_ui_failed_after.txt
comm -13 .superpowers/baseline/web_ui_failed_before.txt .superpowers/baseline/web_ui_failed_after.txt
git status --short
```
Expected：`comm` 没有输出（没有新增的失败）；`git status` 为空（`katrain/config.json` 如果被改了就还原）。

- [ ] **Step 2：前端全量单测**

Run：`cd katrain/web/ui && npx vitest run 2>&1 | tail -6`
Expected：和改动前的通过数一致。如果有失败，先在 `git stash` 之前的状态下跑一遍，确认那条失败是不是本来就有。

- [ ] **Step 3：两套构建都要过**（`AuthContext.tsx` 属于共享区，kiosk 也会用到）

Run：`npm run build 2>&1 | tail -3 && npm run build:kiosk-2d 2>&1 | tail -3`
Expected：两个都以 `built in` 结尾，kiosk 那个还要打印 `✅ kiosk boundary clean`。

---

### Task 6: 🛑 发布前清点各环境的管理员账号（需要 Fan 决策）

这一步不改任何数据。改完以后只有 `is_admin` 的账号能编辑教程，所以要先弄清楚每个环境里谁是管理员。

- [ ] **Step 1：只读查询三个环境**

```bash
# Mac 本机（做教程用的库，见 .claude/skills/tutorial-data-sync）
docker exec katrain-postgres psql -U katrain_user -d katrain_db -At \
  -c "SELECT id, username, is_admin FROM users WHERE is_admin OR username = 'admin' ORDER BY id;"
# 测试机
ssh home-ubuntu "docker exec katrain-postgres psql -U katrain_user -d katrain_db -At -c \"SELECT id, username, is_admin FROM users WHERE is_admin OR username = 'admin' ORDER BY id;\""
# 生产：先核对库名和容器名，不要凭记忆
ssh ucloud-v100 "sudo docker ps --format '{{.Names}}' | grep -E 'postgres|katrain-web'"
ssh ucloud-v100 "sudo docker exec katrain-ucloud-postgres-1 psql -U katrain_user -l -At | cut -d'|' -f1"
ssh ucloud-v100 "sudo docker exec katrain-ucloud-postgres-1 psql -U katrain_user -d katrain_prod_20260725 -At -c \"SELECT id, username, is_admin FROM users WHERE is_admin OR username = 'admin' ORDER BY id;\""
```
Expected：三份清单。记下来，一并交给 Fan。

- [ ] **Step 2：🛑 请 Fan 决定**
  1. 在 Mac 本机、测试机、生产上，各自把哪个用户名设成管理员（通常是他自己的账号）。
  2. 生产上的 `admin`（id=1）怎么处理：
     - 选项 A：撤掉 `is_admin`，并把口令改成一个没有任何人知道的随机值，相当于停用。
     - 选项 B：保留管理员身份，改成一个强口令。这个由 Fan 自己执行，口令不经过 Claude。

- [ ] **Step 3：按 Fan 的决定执行**（每条命令执行前，都要再得到他一次点头）

给 Fan 指定的账号授权（把 `<用户名>` 换成他给的值）：
```bash
ssh ucloud-v100 "sudo docker exec katrain-ucloud-postgres-1 psql -U katrain_user -d katrain_prod_20260725 -At -c \"UPDATE users SET is_admin = true WHERE username = '<用户名>' RETURNING id, username, is_admin;\""
```
测试机和 Mac 本机用 Step 1 里对应的那条 `docker exec … psql` 前缀，执行同样的 `UPDATE`。

选项 A（停用 `admin`）：
```bash
ssh ucloud-v100 "sudo docker exec -i katrain-ucloud-katrain-web-1 python3 -" <<'PY'
import secrets
from katrain.web.core import models_db
from katrain.web.core.auth import get_password_hash
from katrain.web.core.db import SessionLocal

with SessionLocal() as s:
    u = s.query(models_db.User).filter(models_db.User.username == "admin").one()
    u.hashed_password = get_password_hash(secrets.token_urlsafe(32))  # nobody ever sees it
    u.is_admin = False
    s.commit()
    print(u.id, u.username, u.is_admin)
PY
```
Expected：打印 `1 admin False`。**容器名以 Step 1 实际查到的为准**。

选项 B（Fan 自己在终端里执行，口令只在他那边输入）：
```
! ssh -t ucloud-v100 "sudo docker exec -it katrain-ucloud-katrain-web-1 python3 -c \"import getpass; from katrain.web.core import models_db; from katrain.web.core.auth import get_password_hash; from katrain.web.core.db import SessionLocal; s=SessionLocal(); u=s.query(models_db.User).filter(models_db.User.username=='admin').one(); u.hashed_password=get_password_hash(getpass.getpass('new admin password: ')); s.commit(); print('ok', u.id)\""
```

- [ ] **Step 4：复查**：重新跑 Step 1 的三条查询，确认结果和 Fan 的决定一致。

---

### Task 7: 🛑 发布：先测试机，再生产（每一步推送或部署前都要 Fan 点头）

- [ ] **Step 1：跟上 develop，然后快进推送**（不碰共享的主工作树）

```bash
cd /Users/fan/Repositories/katrain-admin-console
git fetch origin
git merge --no-edit origin/develop
CI=true uv run pytest tests/web_ui/test_guest_write_block.py tests/web_ui/test_tutorial_db_api.py -q -p no:cacheprovider 2>&1 | tail -2
git push origin HEAD:develop
```
Expected：pytest 全部通过。push 是快进；如果被拒（develop 又前进了），就重新执行 fetch、merge、测试、push。

- [ ] **Step 2：部署测试机**（develop 的 `.claude/skills/server-deploy`，这次只改了 web）

```bash
ssh home-ubuntu "cd ~/Repositories/katrain && git pull --ff-only && docker compose up -d --build katrain-web && docker ps --format '{{.Names}}\t{{.Status}}' | grep katrain-web"
```
Expected：`katrain-web  Up … (healthy)`，或者 `Up` 了几秒。

- [ ] **Step 3：验证测试机**（用不存在的 id 探测：不会写任何东西，401 就证明闸在查库之前生效了）

```bash
for p in "PUT /api/v1/tutorials/figures/999999/board" "POST /api/v1/tutorials/figures/999999/generate-audio" \
         "PUT /api/v1/tutorials/figures/999999/narration" "PUT /api/v1/tutorials/figures/999999/verify" \
         "GET /api/v1/board/devices"; do
  set -- $p; printf '%s %s -> ' "$1" "$2"
  curl -s -o /dev/null -w '%{http_code}\n' -X "$1" -H 'Content-Type: application/json' -d '{}' "https://go.sailorvoyage.top$2"
done
```
Expected：五行都是 `401`（改之前前四行会是 404 或 422）。然后请 Fan 用他的管理员账号在测试机上改一条讲解，确认编辑流程正常。

- [ ] **Step 4：生产**。按 release 分支上 `docs/operations/ucloud-migration-runbook.md` 的常规发布流程走，参照它最近的 2026-09-06 条目。在本机新建一个临时 worktree，不要复用别的会话的：

**先让 Fan 知道这次还会带上别人的哪些提交**：发布是把整个 develop 合进 release，所以会连带自上次发布以来 develop 上的**全部**提交（2026-09-24 时约 54 个），不只是本切片。
```bash
git -C /Users/fan/Repositories/katrain fetch origin
git -C /Users/fan/Repositories/katrain log --oneline --no-merges origin/release/ucloud-20260805..origin/develop
```
把这份列表交给 Fan，🛑 **他同意整批发布后**再继续往下做。

```bash
cd /Users/fan/Repositories/katrain
REL=/private/tmp/claude-501/rel-admin-guard
git fetch origin
git worktree add "$REL" -b release-merge-admin-guard origin/release/ucloud-20260805
cd "$REL" && git merge --no-edit origin/develop
git diff --name-only HEAD~1 HEAD -- katrain/cron/ | head
```
- 合并**报无冲突也要复查**：release 侧在 `server.py` 里有 `if settings.PREVIEW_MODE:` 守卫。确认 develop 新带进来的启动期写库动作都落在守卫之内（`git diff HEAD~1 HEAD -- katrain/web/server.py | head -80`）。
- 在 `$REL` 里执行 `uv sync --extra web`，然后跑 `CI=true uv run pytest tests/deploy tests/web_ui/test_guest_write_block.py tests/web_ui/test_tutorial_db_api.py -q -p no:cacheprovider`，要求全部通过。
- 🛑 Fan 点头后 `git push origin HEAD:release/ucloud-20260805`。

在 ucloud-v100 上（每一行执行前都要 Fan 点头）：
```bash
SHA=<release 分支尖端的 short sha>
sudo git clone --depth 1 --branch release/ucloud-20260805 https://github.com/shevapato2008/katrain.git /opt/katrain/releases/$SHA
sudo git -C /opt/katrain/releases/$SHA rev-parse --short HEAD          # 必须等于 $SHA
cd /opt/katrain/releases/$SHA && sudo deploy/ucloud/scripts/build-web.sh katrain-web:$SHA   # 记下输出的 image_id
# CRON_IMAGE 只有在「上一个 release..$SHA 之间 katrain/cron/ 有改动」时才重建：
#   git diff --name-only <上一个 release sha> $SHA -- katrain/cron/   非空 ⇒
#   sudo docker build --pull=false -f Dockerfile.cron -t katrain-cron:$SHA . ，再记下 image_id
TS=$(date +%Y%m%d-%H%M)
sudo sh -c "docker exec katrain-ucloud-postgres-1 pg_dump -U katrain_user -Fc katrain_prod_20260725 > /opt/katrain/backups/prod-$TS.dump"
sudo docker exec katrain-ucloud-postgres-1 createdb -U katrain_user katrain_restore_verify_$TS
sudo sh -c "docker exec -i katrain-ucloud-postgres-1 pg_restore -U katrain_user -d katrain_restore_verify_$TS < /opt/katrain/backups/prod-$TS.dump"; echo "pg_restore exit=$?"
for t in $(sudo docker exec katrain-ucloud-postgres-1 psql -U katrain_user -d katrain_prod_20260725 -At -c "select tablename from pg_tables where schemaname='public' order by 1"); do
  a=$(sudo docker exec katrain-ucloud-postgres-1 psql -U katrain_user -d katrain_prod_20260725 -At -c "select count(*) from \"$t\"")
  b=$(sudo docker exec katrain-ucloud-postgres-1 psql -U katrain_user -d katrain_restore_verify_$TS -At -c "select count(*) from \"$t\"")
  [ "$a" = "$b" ] || echo "MISMATCH $t $a $b"
done; echo "row-count compare done"
sudo docker exec katrain-ucloud-postgres-1 dropdb -U katrain_user katrain_restore_verify_$TS
sudo cp /etc/katrain/ucloud.env /opt/katrain/backups/ucloud.env.$(date +%Y%m%dT%H%M%S).bak
sudo sed -i "s|^WEB_IMAGE=.*|WEB_IMAGE=<build-web.sh 打出的 image_id>|" /etc/katrain/ucloud.env   # 只有 cron 也重建时才同时改 CRON_IMAGE
sudo stat -c '%U:%G %a' /etc/katrain/ucloud.env                                               # 必须是 root:root 600
sudo deploy/ucloud/scripts/preflight.sh --phase full --env-file /etc/katrain/ucloud.env       # 只有容量闸红属于历次都有的已知情况，要明说
sudo ln -sfn /opt/katrain/releases/$SHA /opt/katrain/current
cd /opt/katrain/current
sudo docker compose --env-file /etc/katrain/ucloud.env -f deploy/ucloud/compose.yml -f deploy/ucloud/compose.production.yml --profile production up -d --dry-run katrain-web
sudo docker compose --env-file /etc/katrain/ucloud.env -f deploy/ucloud/compose.yml -f deploy/ucloud/compose.production.yml --profile production up -d katrain-web
```
Expected：
- `pg_restore exit=0`，且没有任何 `MISMATCH` 行；
- dry-run 的输出里只重建 `katrain-web`，`katago-*` 和 `postgres` 只出现 `Waiting` / `Healthy`；
- `up -d` 后 katrain-web 转为 healthy。

- [ ] **Step 5：验证生产**：把 Step 3 的循环里的域名换成 `https://modelstella.com`，要求五行都是 `401`。再请 Fan 用管理员账号改一条讲解，确认可以改。

- [ ] **Step 6：在 release 分支的 runbook 里补一条发布记录**，格式照 2026-09-06 那条写：包含镜像 ID、备份文件、恢复验证结果、发布前后的探针表，以及 `admin` 的处置结果。提交并推送 release 分支（🛑 需要 Fan 点头）。然后删掉临时 worktree：先执行 `git -C "$REL" status --ignored` 确认里面没有需要保留的东西，再执行 `git worktree remove "$REL"`。

---

## Self-Review 记录

- 对照 spec 的覆盖：§4 的三个问题分别落在 Task 1、Task 2、Task 6；前端只读落在 Task 3；承重实测落在 Task 4；「会改变谁能编辑教程」落在 Task 6；「先测试机再生产」落在 Task 7。
- 占位符：`<用户名>`、`<release 分支尖端的 short sha>`、`<build-web.sh 打出的 image_id>` 都是**运行时才知道的输入**，每一个都写明了从哪一步取得，不属于没写完的内容。
- 名字一致：`_create_admin_and_login`、`_fake_tts`、`canEdit`、`AuthUser` 在各任务之间用法一致。
