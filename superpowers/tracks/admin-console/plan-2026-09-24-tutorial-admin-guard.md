# 教程写接口与设备列表只许管理员（切片 0）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 堵上三个安全问题：教程的四个写接口未登录也能调用；`GET /board/devices` 把所有盒子的 IP 发给任意登录用户；生产上的 `admin/admin` 还能登录。评审又发现第四个：有效期 90 天的 refresh token 能直接当 Bearer 用（Task 3，Fan 2026-09-24 定保留）。同时让教程页只对管理员显示编辑控件。

**Architecture:** 后端把 5 个接口的依赖换成现成的 `get_current_admin_user`（`katrain/web/api/v1/endpoints/auth.py:155`）。前端在 `AuthContext` 的 User 类型里声明 `is_admin`（`/auth/me` 一直在返回这个字段），`TutorialFigurePage` 根据它决定是否渲染编辑控件。`admin/admin` 怎么处置由 Fan 决定，按他的决定改生产库。

**Tech Stack:** FastAPI + SQLAlchemy + pytest（httpx ASGITransport）；React 19 + MUI 7 + vitest + Playwright（vite dev）。

**Spec:** `superpowers/tracks/admin-console/spec-2026-09-24-admin-console.md` §4

## Global Constraints

- 顺序：**先测试机 home-ubuntu（go.sailorvoyage.top），再生产 ucloud-v100（modelstella.com）**（Fan 2026-08-31）。
- 目标视口 1440×900。
- 布局相关的结论只认真实浏览器量出来的数，不写 jsdom 几何断言。
- 新文件名不许以 `log` 开头（根 `.gitignore:16` 的 `log*` 加上 `core.ignorecase=true` 会静默吞掉）。
- 不在共享的主工作树 `~/Repositories/katrain` 里切分支或提交；所有工作都在 worktree `~/Repositories/katrain-admin-console`（分支 `feature/admin-console`）里做。
- 任何写生产库、推送、部署的动作，**执行当下都要 Fan 点头**（本计划获批不算）。
- 提交信息末尾加 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`。
- 带管道的检查命令先写 `set -o pipefail`，否则退出码是 `tail` 的，失败也显示成功（release runbook 2026-09-23 记过 `git clone … | tail` 把失败显示成了成功）。生产上的发布命令一律不接管道。
- 本机 shell 是 zsh：不做词分割（`set -- $p` 拆不开「方法 路径」）；`$VAR:t…` 会被当成路径修饰符，要写成 `${VAR}:…`。
- 执行者每次调用 Bash、每次 `ssh` 都是新 shell，变量留不到下一步。跨步骤要用的值（端口、PID、SHA、镜像 ID、时间戳）写进文件，或者在每条命令里写成字面量。
- 已有测试文件里有基线就红的用例（例如 `test_tutorial_db_api.py` 里 3 条 monkeypatch 已不存在的 `ASSET_BASE` 的用例）。判断「有没有弄坏」一律用 Task 1 Step 2 写的 `newfail.sh` 按用例名字和基线比，不要求整个文件全绿。
- 跑测试之前 `katrain/config.json` 必须是干净的（Task 1 Step 1 核对）：测试会改写这个已提交的文件，事后要还原，而还原会连带冲掉测试之前就有的改动。

## Review Focus

- 已登录但不是管理员的用户打开教程页：应该看到讲解、音频、原书页，**一个编辑按钮都没有**，而不是按钮都在、点了才报 403 → Task 4 的「非管理员只读」用例。
- 未登录用户（`user` 为空）打开一个还没有棋盘的图，也不能出现「初始化空棋盘」→ Task 4 的「未登录只读」用例。
- 拿 refresh token（90 天）当 Bearer 调接口：必须 401，不能因为签名对就放行，更不能拿到管理员权限 → Task 3 的 `test_refresh_token_is_not_a_bearer_credential`。
- 盒子用普通账号上报心跳，必须照旧成功（只收紧列表，不收紧心跳）→ Task 2 的 `test_real_user_can_heartbeat_but_not_list_devices`。
- 管理员写入棋盘后，历史记录里的 `changed_by` 应该是管理员用户名，不再是 `"anonymous"` → Task 1 的 `test_tutorial_writer_admin_2xx`。

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `katrain/web/api/v1/endpoints/tutorials.py` | 改 | 四个写接口改成只许管理员 |
| `katrain/web/api/v1/endpoints/board.py` | 改 | `GET /devices` 改成只许管理员 |
| `katrain/web/api/v1/endpoints/auth.py` | 改 | `get_user_from_token` 只收 access token |
| `tests/web_ui/test_auth_api.py` | 改 | refresh token 当 Bearer 必须 401 |
| `tests/web_ui/test_guest_write_block.py` | 改 | 原来「未登录可写」的锁换成「未登录 401 / 非管理员 403 / 管理员 200」；拆分设备列表的用例 |
| `tests/web_ui/test_tutorial_db_api.py` | 改 | 夹具里的 `testadmin` 设为真管理员，再加一条「非管理员 403」 |
| `katrain/web/ui/src/context/AuthContext.tsx` | 改 | User 类型声明 `is_admin?: boolean` |
| `katrain/web/ui/src/galaxy/pages/tutorials/TutorialFigurePage.tsx` | 改 | 编辑控件只给管理员 |
| `katrain/web/ui/src/galaxy/pages/tutorials/TutorialFigurePage.test.tsx` | 改 | 覆盖管理员、非管理员、未登录三种情况 |
| `superpowers/tracks/admin-console/slice0/` | 新建 | 截图和承重实测记录（证据，不是代码） |

---

### Task 1: 教程的四个写接口只许管理员

**Files:**
- Modify: `katrain/web/api/v1/endpoints/tutorials.py`（第 15–18 行的 import；第 150–262 行的四个写接口）
- Test: `tests/web_ui/test_guest_write_block.py`（模块 docstring 第 8–9 行；第 130–150 行附近加辅助函数；第 268–305 行的两条教程用例）
- Test: `tests/web_ui/test_tutorial_db_api.py`（`client_with_auth` 夹具；在文件末尾新增一条用例）
- 不提交：`.superpowers/baseline/web_ui_failed_before.txt`（Step 2 生成；`.superpowers/` 被根目录 `.gitignore:208` 忽略）

**Interfaces:**
- Consumes：`get_current_admin_user(request, token) -> katrain.web.models.User`（`auth.py:155`；server 模式下只认显式的 `Authorization: Bearer`，strict Box 模式另收绑定 generation 的 SSO cookie；未登录 401 `"Not authenticated"`，非管理员 403 `"Admin privileges required"`）
- Produces：`tests/web_ui/test_guest_write_block.py` 里的 `_create_admin_and_login(app, username="tutorial-admin") -> (headers, user_id, unique_name)`，Task 2 会复用
- Produces：`.superpowers/baseline/web_ui_failed_before.txt`（改动前 `tests/web_ui` 失败用例的**名字**，一行一个，已排序）和 `.superpowers/baseline/newfail.sh`（跑 pytest，只报基线里没有的失败）。后面每一次「有没有弄坏」都用它们

- [ ] **Step 1：装 Python 依赖，确认基线目录被 git 忽略**（worktree 里是空的；只跑 `uv sync` 不会装 fastapi）

```bash
cd /Users/fan/Repositories/katrain-admin-console
uv sync --extra web
git check-ignore -v .superpowers/baseline/x.txt
git diff --quiet -- katrain/config.json && echo config-clean
```
Expected：`uv sync` 以 `Installed` 或 `Audited` 结尾，没有报错；`git check-ignore` 打印 `.gitignore:208:.superpowers/	.superpowers/baseline/x.txt`；最后打印 `config-clean`。**没打印 `config-clean` 就停**：`katrain/config.json` 在跑测试之前就有未提交的改动，先弄清楚是谁的，否则后面「还原被测试改写的 config.json」会把它一起冲掉。

- [ ] **Step 2：改任何代码之前，记录 web_ui 基线（只记失败用例的名字），写好「只报新增失败」的小脚本**

```bash
cd /Users/fan/Repositories/katrain-admin-console
B=.superpowers/baseline; mkdir -p $B
CI=true uv run pytest tests/web_ui -q -p no:cacheprovider --continue-on-collection-errors -rfE > $B/web_ui_before.log 2>&1; echo "pytest exit=$?"
tail -1 $B/web_ui_before.log
grep -E '^(FAILED|ERROR) ' $B/web_ui_before.log | sed -E 's/ - .*//' | sort -u > $B/web_ui_failed_before.txt
wc -l < $B/web_ui_failed_before.txt
cat > $B/newfail.sh <<'SH'
#!/usr/bin/env bash
# 用法（在 worktree 根目录）：bash .superpowers/baseline/newfail.sh <基线文件> <pytest 参数…>
# 跑 pytest，只报基线里没有的失败。有新增失败 → 退出码 1；pytest 本身没跑成（中断、内部错误、用法错误、
# 一条都没收集到，或者没跑到 summary）→ 退出码 2。
set -uo pipefail
base="$1"; shift
log=$(mktemp)
CI=true uv run pytest "$@" -q -p no:cacheprovider -rfE > "$log" 2>&1
rc=$?
tail -1 "$log"
[ "$rc" -le 1 ] || { echo "!! pytest 退出码 $rc，日志在 $log"; exit 2; }
tail -1 "$log" | grep -qE '[0-9]+ (passed|failed|errors?)' || { echo "!! pytest 没有跑到 summary，日志在 $log"; exit 2; }
new=$(grep -E '^(FAILED|ERROR) ' "$log" | sed -E 's/ - .*//' | sort -u | comm -13 "$base" -)
[ -z "$new" ] && exit 0
echo "!! 新增失败："; echo "$new"; exit 1
SH
git status --short
```
Expected：先打印 `pytest exit=0` 或 `1`（2–5 说明 pytest 本身没跑成，基线作废）；下一行是 pytest 的 summary（形如 `3 failed, 1234 passed, … in 95.1s`），**不是**报错或空行；`wc -l` 输出一个数（可以是 0）；`git status --short` 为空。`katrain/config.json` 如果出现在输出里（有的测试会改写这个已提交的文件），执行 `git checkout -- katrain/config.json` 还原。不要把还不存在的测试文件当参数传给 pytest：pytest 会以用法错误直接退出，基线就会**静默为空**。

- [ ] **Step 3：把 `test_guest_write_block.py` 里锁定旧行为的用例改成新的期望**

3a. 模块 docstring 第 8–9 行，把：
```python
  - The four optional-auth tutorial-authoring writers guest-only reject
    (anonymous stays allowed).
```
改成：
```python
  - The four tutorial-authoring writers are ADMIN-ONLY since 2026-09-24:
    anonymous 401, non-admin and guest 403 ("Admin privileges required").
    They used to be guest-only reject with anonymous allowed (R3-F1); see
    superpowers/tracks/admin-console/spec-2026-09-24-admin-console.md §4.
```

3b. 在 `_seed_tutorial_figure` 函数之后（它以 `return figure.id` 结尾），插入这两个辅助函数：
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

3c. 在 `test_tutorial_writer_guest_403` 里，把：
```python
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Guest is read-only"}
```
改成：
```python
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Admin privileges required"}
```

3d. 把**整个** `test_tutorial_writer_anonymous_still_2xx` 函数（从它上面的 `@pytest.mark.asyncio` 装饰器开始，到 `assert resp.status_code == 200, resp.text` 结束）替换成下面三条：
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

- [ ] **Step 4：改 `test_tutorial_db_api.py`**

4a. 在 `client_with_auth` 夹具里，把：
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

4b. 在文件末尾新增：
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

- [ ] **Step 5：跑测试，确认它们失败，而且失败原因是对的**

Run：
```bash
set -o pipefail
cd /Users/fan/Repositories/katrain-admin-console
CI=true uv run pytest tests/web_ui/test_guest_write_block.py tests/web_ui/test_tutorial_db_api.py -q -p no:cacheprovider -k "tutorial_writer or update_board" 2>&1 | tail -15
```
Expected：FAIL。
- `test_tutorial_writer_anonymous_401[*]` 失败，是因为拿到了 200；
- `test_tutorial_writer_non_admin_403[*]` 失败，是因为拿到了 200；
- `test_tutorial_writer_guest_403[*]` 失败，是因为 detail 还是 `Guest is read-only`；
- `test_update_board_non_admin_forbidden` 失败，是因为拿到了 200；
- `test_tutorial_writer_admin_2xx[*]` 和 `test_update_board_authenticated_success` 此刻**会通过**（旧代码本来就放行），这是正常的。

- [ ] **Step 6：改 `tutorials.py`**

6a. 第 15–18 行，把：
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
等 6b–6e 全部改完，再确认旧的名字已经没人用了：
Run：`grep -nE "get_current_user_optional|is_guest_user" katrain/web/api/v1/endpoints/tutorials.py; grep -nw "User" katrain/web/api/v1/endpoints/tutorials.py`
Expected：第一条 grep 没有输出；第二条只命中 `from katrain.web.models import User as AuthUser` 这一行。如果还有别处在用 ORM 的 `User`，就把原来的 `from katrain.web.core.models_db import User` 加回来。

6b. `update_figure_board`：把签名里的
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

6c. `generate_audio_for_figure`：把
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

6d. `update_figure_narration`：把
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

6e. `verify_figure`：把
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

- [ ] **Step 7：跑测试，按名字和基线比**

```bash
cd /Users/fan/Repositories/katrain-admin-console
bash .superpowers/baseline/newfail.sh .superpowers/baseline/web_ui_failed_before.txt tests/web_ui/test_guest_write_block.py tests/web_ui/test_tutorial_db_api.py; echo "newfail exit=$?"
git status --short
```
Expected：`newfail exit=0`。`test_tutorial_db_api.py` 里那 3 条 monkeypatch `ASSET_BASE` 的用例在基线里就是红的，不算新增。另外 `test_update_board_requires_auth` 在基线里也是红的（改之前匿名能写），这一步改完它会变绿（2026-09-24 实跑基线：这个文件红的正好是这 4 条）。`git status` 只列出本任务改动的三个文件（`katrain/config.json` 如果也出现了，执行 `git checkout -- katrain/config.json` 还原）。

- [ ] **Step 8：提交**

```bash
set -o pipefail
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
- Consumes：Task 1 的 `_create_admin_and_login(app, username)`；Task 1 Step 2 的 `newfail.sh` 和基线文件

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

- [ ] **Step 4：跑整个文件，按名字和基线比**

Run：`cd /Users/fan/Repositories/katrain-admin-console && bash .superpowers/baseline/newfail.sh .superpowers/baseline/web_ui_failed_before.txt tests/web_ui/test_guest_write_block.py; echo "newfail exit=$?"`
Expected：`newfail exit=0`。其中 `test_guest_403_on_all_write_routes[GET:/api/v1/board/devices]` 仍然是 403，只是现在由管理员闸拦下。

- [ ] **Step 5：提交**

```bash
set -o pipefail
git add katrain/web/api/v1/endpoints/board.py tests/web_ui/test_guest_write_block.py
git commit -m "fix(board): 设备列表只许管理员 —— 它带着每台盒子的 IP；心跳不变

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git show --stat HEAD | tail -4
```

---

### Task 3: Bearer 只认 access token

2026-09-24 评审时发现：`get_user_from_token`（`katrain/web/api/v1/endpoints/auth.py:118`）只验签名和 `sub`，不看 `type`。所以有效期 90 天的 refresh token 能直接当 Bearer 用，也能调 Task 1、2 刚收紧的管理员接口；access token 的有效期只有 7 天。仓里签发 JWT 的只有两处（`katrain/web/core/auth.py:34,47`）：`create_access_token` 写 `type: "access"`（2026-02-12 起就有），`create_refresh_token` 写 `type: "refresh"`。前端从不使用 refresh token；本机回环登录的 SSO cookie 里放的也是 access token（`auth.py:467`）；Python 侧只有 `remote_client` 用 refresh token，走的是 `/auth/refresh`，那里本来就要求 `type == "refresh"`。所以只收 access token 不会误伤现有调用方。**这一项是评审新增的，不在 spec §4 原来的三个问题里；Fan 2026-09-24 定：保留。**

**Files:**
- Modify: `katrain/web/api/v1/endpoints/auth.py:125-129`（`get_user_from_token` 的解码段）
- Test: `tests/web_ui/test_auth_api.py`（末尾追加两条，沿用文件里的 `app` 夹具）

**Interfaces:**
- Consumes：`create_access_token(data)`、`create_refresh_token(data)`（`katrain/web/core/auth.py`）；Task 1 Step 2 的 `newfail.sh` 和基线文件
- Produces：`get_user_from_token(token, repo, box_sso=None)` 签名不变；`type` 不是 `"access"` 的令牌一律 401

- [ ] **Step 1：写测试**（追加到 `tests/web_ui/test_auth_api.py` 末尾）

```python
async def _me_with(app, token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})


def _make_user(app, username):
    from passlib.context import CryptContext

    try:
        app.state.user_repo.create_user(username, CryptContext(schemes=["bcrypt"], deprecated="auto").hash("pw"))
    except ValueError:
        pass


@pytest.mark.asyncio
async def test_refresh_token_is_not_a_bearer_credential(app):
    """A refresh token lives 90 days and only /auth/refresh may accept it. As a Bearer it is 401."""
    from katrain.web.core.auth import create_refresh_token

    _make_user(app, "rt_user")
    resp = await _me_with(app, create_refresh_token(data={"sub": "rt_user"}))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_access_token_is_still_a_bearer_credential(app):
    from katrain.web.core.auth import create_access_token

    _make_user(app, "at_user")
    resp = await _me_with(app, create_access_token(data={"sub": "at_user"}))
    assert resp.status_code == 200 and resp.json()["username"] == "at_user"
```

- [ ] **Step 2：跑测试，确认失败**

Run：`cd /Users/fan/Repositories/katrain-admin-console && CI=true uv run pytest tests/web_ui/test_auth_api.py -q -p no:cacheprovider -k "bearer_credential" 2>&1 | tail -6`
Expected：`test_refresh_token_is_not_a_bearer_credential` FAIL（拿到了 200）；`test_access_token_is_still_a_bearer_credential` PASS。

- [ ] **Step 3：改 `get_user_from_token`**。把
```python
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
```
改成：
```python
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        # Only access tokens are Bearer credentials (2026-09-24). A refresh token lives 90 days and is for
        # /auth/refresh alone; before this check it also unlocked every endpoint, admin-only ones included.
        if payload.get("type") != "access":
            raise credentials_exception
```

- [ ] **Step 4：跑鉴权相关的测试文件，按名字和基线比**

Run：`bash .superpowers/baseline/newfail.sh .superpowers/baseline/web_ui_failed_before.txt tests/web_ui/test_auth_api.py tests/web_ui/test_board_auth.py tests/web_ui/test_auth_persistence.py tests/web_ui/test_guest_write_block.py; echo "newfail exit=$?"`
Expected：`newfail exit=0`。

- [ ] **Step 5：三处后端改动都完成了，跑 web_ui 全量，按名字和基线比**

Run：`bash .superpowers/baseline/newfail.sh .superpowers/baseline/web_ui_failed_before.txt tests/web_ui --continue-on-collection-errors; echo "newfail exit=$?"; git status --short`
Expected：`newfail exit=0`，即没有新增的失败，基线里本来就红的用例不算。`git status --short` 只列出本任务的两个文件（`katrain/config.json` 若被改动就执行 `git checkout -- katrain/config.json` 还原）。列出了新增失败时逐条看：是本切片造成的就修，不是的就在提交信息里写明。

- [ ] **Step 6：提交**

```bash
set -o pipefail
git add katrain/web/api/v1/endpoints/auth.py tests/web_ui/test_auth_api.py
git commit -m "fix(auth): Bearer 只认 access token —— refresh token（90 天）不能再直接调接口

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git show --stat HEAD | tail -4
```

---

### Task 4: 教程页只对管理员显示编辑控件

**Files:**
- Modify: `katrain/web/ui/src/context/AuthContext.tsx:6-17`（`interface User`）
- Modify: `katrain/web/ui/src/galaxy/pages/tutorials/TutorialFigurePage.tsx`：第 39 行（`useAuth`）、第 51–53 行之后（新增 `canEdit`）、第 465–507 行（讲解区）、第 531–535 行（识别调试面板）、第 538–567 行（actions）
- Test: `katrain/web/ui/src/galaxy/pages/tutorials/TutorialFigurePage.test.tsx`
- 不提交：`.superpowers/baseline/vitestnewfail.sh`、`vitest_failed_before.txt`（Step 1 生成）

**Interfaces:**
- Consumes：`useAuth()` 返回的 `user?: User | null`，其中 `User.is_admin?: boolean`（本任务新增声明）
- Produces：`canEdit: boolean`，页面内部使用

- [ ] **Step 1：装前端依赖；改前端之前按用例名字记录 vitest 基线，写好「只报新增失败」的 vitest 小脚本**

```bash
cd /Users/fan/Repositories/katrain-admin-console/katrain/web/ui && npm ci
cd /Users/fan/Repositories/katrain-admin-console
cat > .superpowers/baseline/vitestnewfail.sh <<'SH'
#!/usr/bin/env bash
# 用法（在 worktree 根目录）：
#   bash .superpowers/baseline/vitestnewfail.sh --record <基线文件>   记下当前失败的用例名（改前端之前跑一次）
#   bash .superpowers/baseline/vitestnewfail.sh <基线文件>            只报基线里没有的失败：有 → 退出码 1
# vitest 本身没跑成（退出码不是 0/1、没生成报告、报告里一条用例都没有）→ 退出码 2。
# 报告每次写进新的临时文件，不会读到上一次留下的。
set -uo pipefail
record=0; [ "${1:-}" = "--record" ] && { record=1; shift; }
base="$1"
out="$(mktemp)"; rm -f "$out"; out="$out.json"
(cd katrain/web/ui && npx vitest run --reporter=json --outputFile="$out" > /dev/null 2>&1); rc=$?
[ "$rc" -le 1 ] || { echo "!! vitest 退出码 $rc"; exit 2; }
[ -s "$out" ] || { echo "!! vitest 没有生成报告"; exit 2; }
names="$(python3 - "$out" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
if not d.get("numTotalTests"):
    sys.exit(3)
names = set()
for f in d["testResults"]:
    file = f["name"].split("/katrain/web/ui/")[-1]
    if f.get("status") == "failed" and not f["assertionResults"]:
        names.add(f"{file} :: <文件本身没跑起来>")
    names |= {f"{file} :: {a['fullName']}" for a in f["assertionResults"] if a["status"] == "failed"}
print(f"# {d['numTotalTests']} tests, {len(names)} failed", file=sys.stderr)
print("\n".join(sorted(names)))
PY
)" || { echo "!! vitest 报告里一条用例都没有"; exit 2; }
if [ "$record" = 1 ]; then printf '%s\n' "$names" | grep . | sort -u > "$base"; exit 0; fi
new="$(printf '%s\n' "$names" | grep . | sort -u | comm -13 "$base" -)"
[ -z "$new" ] && exit 0
echo "!! 新增失败："; echo "$new"; exit 1
SH
bash .superpowers/baseline/vitestnewfail.sh --record .superpowers/baseline/vitest_failed_before.txt; echo "record exit=$?"
```
Expected：`npm ci` 打印 `added N packages`，没有 `ERR!`；脚本打印 `# N tests, M failed`（M 可以不为 0，记下即可），然后 `record exit=0`。

- [ ] **Step 2：写测试**。在 `TutorialFigurePage.test.tsx` 里：

2a. 把 `beforeEach` 里的
```tsx
    (useAuth as Mock).mockReturnValue({ token: 'fake-token' });
```
改成（原有两条用例从此以管理员身份运行）：
```tsx
    (useAuth as Mock).mockReturnValue({ token: 'fake-token', user: { is_admin: true } });
```

2b. 在 `describe('TutorialFigurePage', () => {` 之前加一个渲染辅助函数：
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

// 只列阅读态下管理员看得到的入口按钮。「生成语音并保存」「保存文字」只在讲解编辑态出现，而进入编辑态的
// 唯一入口「编辑讲解」已经在这里：把它们也列进来，只会多出两条永远成立的断言。
const EDIT_BUTTONS = [/编辑讲解/, /确认审核/, /逻辑检查/, /^编辑$/, /初始化空棋盘/];
```

2c. 在 `describe` 块里、最后一条 `it` 之后，加上：
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

- [ ] **Step 3：跑测试，确认失败**

Run：`cd /Users/fan/Repositories/katrain-admin-console/katrain/web/ui && npx vitest run src/galaxy/pages/tutorials/TutorialFigurePage.test.tsx 2>&1 | tail -15`
Expected：「非管理员只读」和「未登录」两条 FAIL，因为按钮还在；「管理员看得到编辑控件」和原有两条 PASS。

- [ ] **Step 4：改 `AuthContext.tsx`**。在 `interface User` 里的 `avatar_url?: string;` 之后加：
```ts
    // Admin flag. `/auth/me` has always returned it (katrain/web/models.py User.is_admin);
    // the client never declared it before 2026-09-24. Only decides which editing controls
    // render — the real gate is the backend (get_current_admin_user).
    is_admin?: boolean;
```

- [ ] **Step 5：改 `TutorialFigurePage.tsx`**

5a. 第 39 行 `const { token } = useAuth();` 改成：
```tsx
  const { token, user } = useAuth();
```

5b. 在 `const showCompare = isWide && compareOpen;` 之后加一行（前面带注释）：
```tsx
  /* 编辑控件只给管理员（2026-09-24）。后端四个写接口已改成 get_current_admin_user，
     不藏的话普通用户点下去只会拿到 403。未登录（user 为空）同样只读。 */
  const canEdit = user?.is_admin === true;
```

5c. 讲解区的标题行：把「编辑讲解」这个 `<Button …>…</Button>` 整个包进 `{canEdit && ( … )}`，改完是：
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

5d. 把 `{isEditingNarration ? (` 改成 `{canEdit && isEditingNarration ? (`。再把没有讲解文本时显示的那段文字
```tsx
                暂无讲解文本。点击“编辑讲解”后可直接填写并生成语音。
```
改成：
```tsx
                {canEdit ? '暂无讲解文本。点击“编辑讲解”后可直接填写并生成语音。' : '暂无讲解文本。'}
```

5e. 识别调试面板：把 `{currentFigure?.recognition_debug && (` 改成 `{canEdit && currentFigure?.recognition_debug && (`。

5f. actions：把 `actions={(` 改成 `actions={canEdit ? (`，再把 actions 整个 JSX 末尾的 `)}`（紧挨在 `/>` 之前、结束 `<Box sx={{ py: 1.5, borderTop: …`）改成 `) : null}`。改完末尾是这样：
```tsx
          )}
        </Box>
      ) : null}
    />
  );
}
```

- [ ] **Step 6：跑测试、真正的类型检查和 lint**

Run：
```bash
cd /Users/fan/Repositories/katrain-admin-console/katrain/web/ui
set -euo pipefail
npx vitest run src/galaxy/pages/tutorials/TutorialFigurePage.test.tsx 2>&1 | tail -6
npx tsc -b 2>&1 | tail -5
npx eslint src/galaxy/pages/tutorials/TutorialFigurePage.tsx src/context/AuthContext.tsx
echo gates-ok
```
Expected：vitest 全部 PASS；`tsc -b` 没有输出（注意别用 `tsc --noEmit`，那个一个文件都不检查）；eslint 没有输出；最后打印 `gates-ok`（`set -e` 下，前面任何一步失败都走不到这一行）。

- [ ] **Step 7：前端全量单测按名字和基线比；两套构建都要过**（`AuthContext.tsx` 属于共享区，kiosk 包也会用到）

```bash
cd /Users/fan/Repositories/katrain-admin-console
bash .superpowers/baseline/vitestnewfail.sh .superpowers/baseline/vitest_failed_before.txt; echo "vitest-newfail exit=$?"
```
Expected：`vitest-newfail exit=0`。退出码 1 时它会列出新增的失败；2 说明 vitest 本身没跑成。（不要用 `git stash` 回到改动前去复跑：katrain 的十个 worktree 共用一条 stash 栈，pop 可能弹出别人的在制品。基线在 Step 1 已经记好了。）

```bash
cd /Users/fan/Repositories/katrain-admin-console/katrain/web/ui
set -euo pipefail
npm run build 2>&1 | tail -3
npm run build:kiosk-2d 2>&1 | tail -3
echo builds-ok
```
Expected：两个构建都以 `built in` 结尾，kiosk 那个还打印 `✅ kiosk boundary clean`，最后打印 `builds-ok`。

- [ ] **Step 8：提交**

```bash
set -o pipefail
cd /Users/fan/Repositories/katrain-admin-console
git add katrain/web/ui/src/context/AuthContext.tsx katrain/web/ui/src/galaxy/pages/tutorials/TutorialFigurePage.tsx katrain/web/ui/src/galaxy/pages/tutorials/TutorialFigurePage.test.tsx
git commit -m "feat(tutorial): 编辑控件只给管理员；前端声明 User.is_admin

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git show --stat HEAD | tail -5
```

---

### Task 5: 真实浏览器实测右栏承重结构 + 截图，给 Fan 确认

触发理由：非管理员看到的 `board-rail-actions` 变成空的，`board-rail-scroll` 的高度来源就变了（`BoardPageShell.tsx:163-188`）。
这里应该滚动的是 **`board-rail-scroll`**：它既不是 `board-right-rail`，也不是 `board-page-shell`。

**Files:**
- Create（临时，不提交，除非量出了错误数值）：`katrain/web/ui/tests/tutorial-rail-readonly.measure.spec.ts`
- Create：`superpowers/tracks/admin-console/slice0/measurements.md`，以及同目录下的 3 张 png

**Interfaces:**
- Consumes：Task 4 的 `canEdit` 门控；`BoardPageShell.tsx` 已有的 data-testid：`board-page-shell`、`board-right-rail`、`board-rail-module`、`board-rail-scroll`、`board-rail-actions`
- Produces：`slice0/measurements.md` 和 3 张截图，交给 Fan 确认

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

端口和 PID 写进文件：执行者每次调用 Bash 都是新 shell，变量留不到 Step 4。直接起 `node_modules/.bin/vite`，记下的 PID 才是 vite 自己，不是 npm 的外壳。
```bash
cd /Users/fan/Repositories/katrain-admin-console/katrain/web/ui
V=/private/tmp/claude-501/admin-guard-vite; mkdir -p $V ../../../superpowers/tracks/admin-console/slice0
PORT=5183; while lsof -iTCP:$PORT -sTCP:LISTEN >/dev/null; do PORT=$((PORT+1)); done; echo $PORT > $V/port
./node_modules/.bin/vite --port $PORT --strictPort > $V/vite.log 2>&1 & echo $! > $V/pid
for i in $(seq 1 60); do curl -sf http://127.0.0.1:$PORT >/dev/null && break; sleep 1; done
set -o pipefail
MEASURE_BASE=http://127.0.0.1:$PORT npx playwright test --config=playwright.vite.config.ts tests/tutorial-rail-readonly.measure.spec.ts --reporter=line 2>&1 | tail -30
```
Expected：3 passed，并打印出三行 JSON 数字。

- [ ] **Step 3：处理测量结果**
  - 全部通过：删掉 spec（`rm tests/tutorial-rail-readonly.measure.spec.ts`），把三行 JSON 和 R1–R4 逐条的判定写进 `superpowers/tracks/admin-console/slice0/measurements.md`。这里的像素值只做记录，判定看的是关系式。
  - 有一条**量出了错误数值**：先修布局，重跑直到通过。然后按 vertical-slice 的规定，**保留**这个 spec，改名为 `tests/tutorial-rail-readonly.spec.ts` 作为几何闸，和修复放在同一个提交里。

- [ ] **Step 4：停掉 Step 2 起的 vite**。只杀记下的那个 PID，而且先核对它确实是 vite（端口上可能已经是别的会话的服务）：
```bash
V=/private/tmp/claude-501/admin-guard-vite
ps -o command= -p "$(cat $V/pid)" | grep -q vite && kill "$(cat $V/pid)"
lsof -iTCP:"$(cat $V/port)" -sTCP:LISTEN || echo "port free"
```
Expected：打印 `port free`。

- [ ] **Step 5：提交证据**

```bash
cd /Users/fan/Repositories/katrain-admin-console
git add superpowers/tracks/admin-console/slice0/
git commit -m "test(tutorial): 只读右栏承重实测（1440×900，溢出/最空/管理员对照）

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 6：🛑 停，请 Fan 看这三张截图和测量结果，明确确认后才能进入 Task 6。**

---

### Task 6: 🛑 发布前清点各环境的管理员账号（需要 Fan 决策）

**Files:** 无代码改动。Step 1 只读；之后每一条改库的命令，执行前都要 Fan 再点一次头。

**Interfaces:**
- Produces：每个环境至少一个**实测能登录**的 `is_admin = true` 账号，以及 Fan 对生产 `admin`（id=1）的处置。Task 7 的发布以它为前提：发布以后只有管理员能编辑教程。

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
  2. 确认生产上的 `admin`（id=1）按下面的办法停用：
     - 撤掉 `is_admin`，口令改成一个谁也不知道的随机值，相当于停用。撤权即时生效：管理员接口每次请求都按用户名重新查 `is_admin`，此前签发给 `admin` 的令牌（包括拿旧 refresh token 去 `/auth/refresh` 新换出来的）从下一次请求起就没有管理员权限了。
     - **本计划不提供「保留管理员身份、只改强口令」**：改口令不会让已经签发出去的令牌失效，旧 refresh token 还能去 `/auth/refresh` 换出新的 access token（Task 3 只挡住了「refresh token 直接当 Bearer」）。Fan 如果要保留 `admin` 这个账号当管理员，得先轮换 `KATRAIN_SECRET_KEY`，全部用户和盒子都要重新登录一次；那是另一件事，要单独出计划，不在本任务里做。

- [ ] **Step 3：给 Fan 指定的账号授权**，每个环境一条命令。用 Step 1 清单里的**数字 id**，不要把用户名拼进 SQL 或 shell：注册接口不限制用户名里的字符，单引号、`$()` 都可能出现（把 `<数字id>` 换成 Fan 从清单里选定的那一个）：
```bash
ssh ucloud-v100 "sudo docker exec katrain-ucloud-postgres-1 psql -U katrain_user -d katrain_prod_20260725 -At -c 'UPDATE users SET is_admin = true WHERE id = <数字id> RETURNING id, username, is_admin;'"
```
测试机和 Mac 本机用 Step 1 里对应的那条 `docker exec … psql` 前缀，执行同样的 `UPDATE`。
Expected：**恰好一行** `<数字id>|<Fan 说的那个用户名>|t`。一行都没有，或者用户名对不上，就停下和 Fan 核对，不要进 Step 4。

- [ ] **Step 4：请 Fan 用这个账号在测试机和生产上各真实登录一次**，证明口令可用、`is_admin` 已经生效。由 Fan 自己执行，口令只在他那边输入（`<站点>` 分别换成 `https://go.sailorvoyage.top` 和 `https://modelstella.com`）。下面这行开头的 `! ` 是 Claude Code 输入框的「由用户在本会话里执行」前缀；在普通终端里执行时去掉它（在 shell 里 `!` 是取反，会把成功显示成失败）：
```
! bash -c 'read -r -p "用户名: " U; read -r -s -p "密码: " P; echo; T=$(U="$U" P="$P" python3 -c "import json,os; print(json.dumps({\"username\": os.environ[\"U\"], \"password\": os.environ[\"P\"]}))" | curl -s -X POST <站点>/api/v1/auth/login -H "Content-Type: application/json" --data @- | python3 -c "import json,sys; print(json.load(sys.stdin).get(\"access_token\", \"\"))"); curl -s -H "Authorization: Bearer $T" <站点>/api/v1/auth/me | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get(\"username\"), \"is_admin=\", d.get(\"is_admin\"))"'
```
Expected：打印 `<用户名> is_admin= True`。**两台线上机器都验过，才能进 Step 5。** Mac 本机的库只在做教程时用，下次在本机编辑教程时自然会验到。

- [ ] **Step 5：停用生产上的 `admin`**（执行前再得到他一次点头）
```bash
ssh ucloud-v100 "sudo docker exec -i katrain-ucloud-katrain-web-1 python3 -" <<'PY'
import secrets
from katrain.web.core import models_db
from katrain.web.core.auth import get_password_hash
from katrain.web.core.db import SessionLocal

with SessionLocal() as s:
    u = s.query(models_db.User).filter(models_db.User.id == 1).one()
    assert u.username == "admin", u.username
    u.hashed_password = get_password_hash(secrets.token_urlsafe(32))  # nobody ever sees it
    u.is_admin = False
    s.commit()
    print(u.id, u.username, u.is_admin)
PY
```
Expected：打印 `1 admin False`。**容器名以 Step 1 实际查到的为准**。

- [ ] **Step 6：复查**
  - 重新跑 Step 1 的三条查询，确认结果和 Fan 的决定一致；
  - 公开过的旧口令已经登不进去（`admin` 不是保留用户名，只有 `guest` 是）：
```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://modelstella.com/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin"}'
```
Expected：`401`；
  - Fan 用新管理员账号在生产上重跑一次 Step 4，仍然打印 `is_admin= True`。

---

### Task 7: 🛑 发布：先测试机，再生产（每一步推送或部署前都要 Fan 点头）

**Files:**
- Modify（release 分支，在 Step 4 建的临时 worktree `/private/tmp/claude-501/rel-admin-guard` 里）：`docs/operations/ucloud-migration-runbook.md`（追加一条发布记录）

**Interfaces:**
- Consumes：Task 1–4 的提交；Task 6 在各环境实测过能登录的管理员账号；Task 1 Step 2 的 `newfail.sh` 和基线文件

- [ ] **Step 1：跟上 develop，然后快进推送**（不碰共享的主工作树）

```bash
cd /Users/fan/Repositories/katrain-admin-console
git fetch origin
git merge --no-edit origin/develop
bash .superpowers/baseline/newfail.sh .superpowers/baseline/web_ui_failed_before.txt tests/web_ui/test_guest_write_block.py tests/web_ui/test_tutorial_db_api.py tests/web_ui/test_auth_api.py; echo "newfail exit=$?"
```
Expected：`newfail exit=0`（develop 带进来的新失败也会列出来，先弄清楚再推）。🛑 Fan 点头后执行 `git push origin HEAD:develop`。push 是快进；如果被拒（develop 又前进了），重新执行 fetch、merge、newfail、push。

- [ ] **Step 2：部署测试机**（develop 的 `.claude/skills/server-deploy`，这次只改了 web）

```bash
ssh home-ubuntu "cd ~/Repositories/katrain && git pull --ff-only && docker compose up -d --build katrain-web"
ssh home-ubuntu "docker ps --format '{{.Names}}\t{{.Status}}'; for i in \$(seq 1 30); do curl -fsS http://127.0.0.1:8001/api/v1/health && exit 0; sleep 2; done; exit 1"; echo "health exit=$?"
```
Expected：`katrain-web  Up …`（develop 的 compose 没给 katrain-web 配 healthcheck，不会出现 `(healthy)`，别等它），然后打印健康检查的 JSON，`health exit=0`。

- [ ] **Step 3：验证测试机**（用不存在的 id 探测：不会写任何东西；401 说明闸在查库之前就生效了）

```bash
B=https://go.sailorvoyage.top
for spec in "PUT /api/v1/tutorials/figures/999999/board" "POST /api/v1/tutorials/figures/999999/generate-audio" \
            "PUT /api/v1/tutorials/figures/999999/narration" "PUT /api/v1/tutorials/figures/999999/verify" \
            "GET /api/v1/board/devices"; do
  m=${spec%% *}; u=${spec#* }
  printf '%s %s -> ' "$m" "$u"
  curl -s -o /dev/null -w '%{http_code}\n' -X "$m" -H 'Content-Type: application/json' -d '{}' "$B$u"
done
```
（用参数展开拆「方法 路径」，bash 和 zsh 行为一致；不要写 `set -- $spec`，zsh 不做词分割。）
Expected：五行都是 `401`（改之前前四行是 404 或 422）。然后请 Fan 用他的管理员账号在测试机上改一条讲解，确认编辑流程正常。

- [ ] **Step 4：合并到 release 分支，在合并结果上跑 release 自己的闸**

先让 Fan 知道这次还会带上哪些别人的提交：发布是把整个 develop 合进 release，会连带自上次发布以来 develop 上的**全部**提交，不只是本切片。
```bash
git -C /Users/fan/Repositories/katrain fetch origin
git -C /Users/fan/Repositories/katrain log --oneline --no-merges origin/release/ucloud-20260805..origin/develop
```
把这份列表交给 Fan，🛑 **他同意整批发布后**再继续。

```bash
git -C /Users/fan/Repositories/katrain worktree add /private/tmp/claude-501/rel-admin-guard -b release-merge-admin-guard origin/release/ucloud-20260805
cd /private/tmp/claude-501/rel-admin-guard && git merge --no-edit origin/develop; echo "merge exit=$?"
git -C /private/tmp/claude-501/rel-admin-guard diff --name-only HEAD~1 HEAD -- katrain/cron/
```
Expected：`merge exit=0`。有冲突就逐个解决，release 一侧的 `PREVIEW_MODE` 守卫一律保留；`Dockerfile.web` 有冲突时保留 release 的版本（`git checkout --ours Dockerfile.web && git add Dockerfile.web`）。合并提交之后执行 `grep -c '^FROM' /private/tmp/claude-501/rel-admin-guard/Dockerfile.web`，必须是 `4`（release 自己那份 4 阶段构建；develop 那份只有 1 个 `FROM`）。最后一条列出 develop 带进来的 cron 改动：**非空就说明这次 `CRON_IMAGE` 也要重建**，记进 `/private/tmp/claude-501/rel-admin-guard.cron-changed`（写 `yes` / `no`），Step 5 要用。

合并报「无冲突」也不等于守卫还在：git 不会把一侧新加的代码收进另一侧新加的 `if`。release 上有一条专门的闸：preview 模式下，结算、回收预扣、补账、周期结算、直播、平台初始化这 7 个会写生产的动作一个都不许跑。在合并结果上跑它，连同 release 的部署闸和本切片的新测试：
```bash
cd /private/tmp/claude-501/rel-admin-guard && uv sync --extra web
set -o pipefail
CI=true uv run pytest tests/deploy "tests/web_ui/test_backend_setup.py::test_preview_mode_keeps_local_app_without_production_effects" -q -p no:cacheprovider 2>&1 | tail -3; echo "gate exit=$?"
CI=true uv run pytest tests/web_ui/test_guest_write_block.py tests/web_ui/test_tutorial_db_api.py tests/web_ui/test_auth_api.py -q -p no:cacheprovider -k "tutorial_writer or list_devices or update_board_non_admin or bearer_credential" 2>&1 | tail -3; echo "slice exit=$?"
```
Expected：`gate exit=0`、`slice exit=0`。任何一个不是 0 都不许推 release。🛑 Fan 点头后执行 `git -C /private/tmp/claude-501/rel-admin-guard push origin HEAD:release/ucloud-20260805`，再用 `git -C /private/tmp/claude-501/rel-admin-guard rev-parse --short HEAD` 取得下面的 `<SHA>`。

- [ ] **Step 5：在 ucloud-v100 上发布**（每一条执行前都要 Fan 点头）

每次 `ssh` 都是新 shell：`<SHA>`、`<TS>`、`<WEB_ID>`、`<CRON_ID>` 在每条命令里写成字面量；要跨步骤留住的回滚锚点写进服务器上的 `/opt/katrain/backups/anchors-<SHA>.txt`。容器名和库名以 Task 6 Step 1 实际查到的为准。

5a. **先看盘，再动手**。取代码、构建镜像、pg_dump、恢复验证库都要占盘，峰值约 5–6 GB：
```bash
ssh ucloud-v100 "df -B1 -P /; ls -1 /opt/katrain/releases; readlink /opt/katrain/current"
```
Expected：可用空间（`df` 第 4 列）≥ 10 GB 才继续。不够就停下，把 `releases/` 清单和 `current` 的指向交给 Fan，由他决定回收哪几个旧 release 目录。**`current` 指向的那个目录不能删，那是回滚锚点。**

5b. **记下回滚锚点**（镜像 ID 不是密钥；env 里其他行一律不打印）：
```bash
ssh ucloud-v100 'sudo bash -s' <<'SH'
set -euo pipefail
A=/opt/katrain/backups/anchors-<SHA>.txt
OLD=$(readlink /opt/katrain/current)
W=$(grep '^WEB_IMAGE=' /etc/katrain/ucloud.env | cut -d= -f2)
C=$(grep '^CRON_IMAGE=' /etc/katrain/ucloud.env | cut -d= -f2)
docker image inspect --format '{{.Id}}' "$W" "$C" > /dev/null
printf 'OLD_RELEASE=%s\nOLD_WEB_IMAGE=%s\nOLD_CRON_IMAGE=%s\n' "$OLD" "$W" "$C" | tee "$A"
SH
```
Expected：打印三行 `OLD_RELEASE=/opt/katrain/releases/…`、`OLD_WEB_IMAGE=sha256:…`、`OLD_CRON_IMAGE=sha256:…`，没有报错，即两个旧镜像都还在（回滚要用）。

5c. **取代码**（不接管道。runbook 2026-09-23：`clone --depth 1` 连败两次，那次是靠旧目录增量 fetch 再 archive 发出去的）：
```bash
ssh ucloud-v100 "sudo git clone --depth 1 --branch release/ucloud-20260805 https://github.com/shevapato2008/katrain.git /opt/katrain/releases/<SHA>; echo clone-exit=\$?; sudo git -C /opt/katrain/releases/<SHA> rev-parse --short HEAD"
```
Expected：`clone-exit=0`，下一行等于 `<SHA>`。**失败时的兜底**：先 `ssh ucloud-v100 "ls -d /opt/katrain/releases/*/.git"` 找一个带 `.git` 的旧目录（下面叫 `<GITDIR>`，写它所在的目录），然后：
```bash
ssh ucloud-v100 "sudo git -C <GITDIR> fetch --depth 1 origin release/ucloud-20260805 && sudo git -C <GITDIR> rev-parse --short FETCH_HEAD"
ssh ucloud-v100 "set -o pipefail; sudo mkdir /opt/katrain/releases/<SHA> && sudo git -C <GITDIR> archive <SHA> | sudo tar -x -C /opt/katrain/releases/<SHA>; echo archive-exit=\$?"
```
Expected：第一条打印的正好是 `<SHA>`；第二条 `archive-exit=0`。`mkdir` 报「已存在」时停下，先看清那个目录是怎么来的，**不要 `rm -rf` 带占位符的路径**。

5d. **构建镜像**（日志写文件，只看结果行，退出码不被管道吞掉）：
```bash
ssh ucloud-v100 "cd /opt/katrain/releases/<SHA> && sudo deploy/ucloud/scripts/build-web.sh katrain-web:<SHA> > /tmp/build-web-<SHA>.log 2>&1; echo build-exit=\$?; grep -E 'image_id=|size_bytes=' /tmp/build-web-<SHA>.log"
```
Expected：`build-exit=0`，打印出 `image_id=sha256:…`，下面叫 `<WEB_ID>`。Step 4 记的是 `yes`（develop 带进来了 cron 改动）时，再构建 cron：
```bash
ssh ucloud-v100 "cd /opt/katrain/releases/<SHA> && sudo docker build --pull=false -f Dockerfile.cron -t katrain-cron:<SHA> . > /tmp/build-cron-<SHA>.log 2>&1; echo build-exit=\$?; sudo docker image inspect --format '{{.Id}}' katrain-cron:<SHA>"
```
记下打印出的 ID，下面叫 `<CRON_ID>`。

5e. **备份，并实际恢复验证一次**（没有 DDL 也不省）：
```bash
ssh ucloud-v100 'sudo bash -s' <<'SH'
set -euo pipefail
TS=<TS>   # 例如 20260925-1030；写成字面量，发布记录也要用
PG=katrain-ucloud-postgres-1; DB=katrain_prod_20260725; V=katrain_restore_verify_$TS; W=/tmp/restore-verify-$TS
mkdir -p "$W"
TABLES=$(docker exec "$PG" psql -U katrain_user -d "$DB" -At -c "select tablename from pg_tables where schemaname='public' order by 1")
N=$(printf '%s\n' "$TABLES" | grep -c . || true)
[ "$N" -gt 0 ] || { echo "!! 表清单是空的：什么都没比较，不能算通过"; exit 1; }
counts() { for t in $TABLES; do printf '%s %s\n' "$t" "$(docker exec "$PG" psql -U katrain_user -d "$1" -At -c "select count(*) from \"$t\"")"; done; }
counts "$DB" > "$W/before"
docker exec "$PG" pg_dump -U katrain_user -Fc "$DB" > /opt/katrain/backups/prod-$TS.dump
counts "$DB" > "$W/after"
echo "DUMP=/opt/katrain/backups/prod-$TS.dump" >> /opt/katrain/backups/anchors-<SHA>.txt
docker exec "$PG" createdb -U katrain_user "$V"
docker exec -i "$PG" pg_restore -U katrain_user -d "$V" < /opt/katrain/backups/prod-$TS.dump
echo "pg_restore exit=0"
counts "$V" > "$W/restored"
# dump 拿的是它开始那一刻的快照：dump 前后行数没变的表，恢复出来必须一模一样；dump 期间有写入的表，
# 恢复出来的行数必须落在前后两个数之间。其余一律算对不上。
BAD=0
paste "$W/before" "$W/after" "$W/restored" | awk '{ b=$2; a=$4; r=$6; lo=(b<a?b:a); hi=(b>a?b:a); if (r<lo || r>hi) { print "MISMATCH", $1, "before=" b, "after=" a, "restored=" r; bad=1 } } END { exit bad }' || BAD=1
docker exec "$PG" dropdb -U katrain_user "$V"
[ "$BAD" = 0 ] || { echo "!! 行数对不上，见上面的 MISMATCH"; exit 1; }
echo "row-count check passed: $N tables"
SH
```
Expected：打印 `pg_restore exit=0` 和 `row-count check passed: <N> tables`（N 是生产库的表数，几十张，不是 0），ssh 退出码 0。有 `MISMATCH` 时脚本以非 0 退出：停下，把输出交给 Fan。脚本因为别的原因中途退出时，手工 `dropdb katrain_restore_verify_<TS>` 清掉验证库。

5f. **生成候选 env**（正在用的 env 这一步不动；只打印改动的行数，不打印内容，env 里有密钥）：
```bash
ssh ucloud-v100 'sudo bash -s' <<'SH'
set -euo pipefail
C=/etc/katrain/ucloud.env.candidate-<SHA>
install -m 600 -o root -g root /etc/katrain/ucloud.env "$C"
sed -i "s|^WEB_IMAGE=.*|WEB_IMAGE=<WEB_ID>|" "$C"
# 只有 5d 也构建了 cron 时，再执行这一行：
# sed -i "s|^CRON_IMAGE=.*|CRON_IMAGE=<CRON_ID>|" "$C"
echo "changed lines: $(diff /etc/katrain/ucloud.env "$C" | grep -c '^[<>]' || true)"
stat -c '%U:%G %a' "$C"
SH
```
Expected：`changed lines: 2`（cron 也改了是 `4`）；`root:root 600`。

5g. **用候选 env 跑预检**：
```bash
ssh ucloud-v100 "cd /opt/katrain/releases/<SHA> && sudo deploy/ucloud/scripts/preflight.sh --phase full --env-file /etc/katrain/ucloud.env.candidate-<SHA>; echo preflight-exit=\$?"
```
Expected：全绿。**容量闸红了，不要自己越过**：runbook 的规矩是任何一道预检红了就停。把输出里的 `available_bytes` 和 5a 的盘面交给 Fan，由他当场决定是先回收空间，还是这一次越过。最近几次发布的记录都写着「同因越过」（那道闸按迁移的峰值 38.5 GB 设，不是普通发布的峰值），但越不越过由 Fan 当场决定，本计划不预先授权。其他任何一道闸红了都停。决定不发了：`ssh ucloud-v100 "sudo rm /etc/katrain/ucloud.env.candidate-<SHA>"`，正在用的 env 从头到尾没动过。

5h. **启用候选 env、切换 `current`、dry-run**：
```bash
ssh ucloud-v100 'sudo bash -s' <<'SH'
set -euo pipefail
BAK=/opt/katrain/backups/ucloud.env.$(date +%Y%m%dT%H%M%S).bak
cp -p /etc/katrain/ucloud.env "$BAK"
echo "ENV_BACKUP=$BAK" >> /opt/katrain/backups/anchors-<SHA>.txt
mv /etc/katrain/ucloud.env.candidate-<SHA> /etc/katrain/ucloud.env
ln -sfn /opt/katrain/releases/<SHA> /opt/katrain/current
cd /opt/katrain/current
docker compose --env-file /etc/katrain/ucloud.env -f deploy/ucloud/compose.yml -f deploy/ucloud/compose.production.yml --profile production up -d --dry-run katrain-web
SH
```
Expected：只重建 `katrain-web`；`katago-*` 和 `postgres` 只出现 `Waiting` / `Healthy`。5d 也构建了 cron 时，命令末尾加上 `katrain-cron`，dry-run 里也只多它一个。不对就执行 5j。Fan 点头后再真正起服务：
```bash
ssh ucloud-v100 "cd /opt/katrain/current && sudo docker compose --env-file /etc/katrain/ucloud.env -f deploy/ucloud/compose.yml -f deploy/ucloud/compose.production.yml --profile production up -d katrain-web"
```
（5d 也构建了 cron 时，末尾同样加上 `katrain-cron`。）

5i. **等健康，再从外网探一遍**：
```bash
ssh ucloud-v100 'for i in $(seq 1 60); do s=$(sudo docker inspect -f "{{.State.Health.Status}}" katrain-ucloud-katrain-web-1); [ "$s" = healthy ] && break; sleep 5; done; echo "katrain-web=$s"; [ "$s" = healthy ]'
# 只有 5d 也构建了 cron 时，再等 cron（它的 healthcheck 是 kill -0 1）：
# ssh ucloud-v100 'for i in $(seq 1 60); do s=$(sudo docker inspect -f "{{.State.Health.Status}}" katrain-ucloud-katrain-cron-1); [ "$s" = healthy ] && break; sleep 5; done; echo "katrain-cron=$s"; [ "$s" = healthy ]'
for u in / /galaxy /api/v1/health; do printf '%s -> ' "$u"; curl -s -o /dev/null -w '%{http_code}\n' "https://modelstella.com$u"; done
```
Expected：5 分钟内打印 `katrain-web=healthy`（重建了 cron 时还有 `katrain-cron=healthy`），这几条 ssh 的退出码都是 0；三行都是 `200`。**任何一项不对就执行 5j**，不要在生产上现场排查。

5j. **回滚**（只在 5h / 5i 失败时执行；执行前 Fan 点头）：
```bash
ssh ucloud-v100 'sudo bash -s' <<'SH'
set -euo pipefail
. /opt/katrain/backups/anchors-<SHA>.txt
cp "$ENV_BACKUP" /etc/katrain/ucloud.env
ln -sfn "$OLD_RELEASE" /opt/katrain/current
cd /opt/katrain/current
docker compose --env-file /etc/katrain/ucloud.env -f deploy/ucloud/compose.yml -f deploy/ucloud/compose.production.yml --profile production up -d katrain-web katrain-cron
SH
```
然后重跑 5i：web 和 cron 都要回到 healthy，探针 200。数据库不用回滚：本切片没有 DDL。

- [ ] **Step 6：验证生产**：Step 3 的循环把 `B` 换成 `https://modelstella.com`，要求五行都是 `401`。再请 Fan 用管理员账号改一条讲解，确认可以改。

- [ ] **Step 7：发布记录**：在 `/private/tmp/claude-501/rel-admin-guard/docs/operations/ucloud-migration-runbook.md` 里按 2026-09-23 那条的格式补一条：镜像 ID、备份文件、恢复验证结果、回滚锚点（`anchors-<SHA>.txt` 的内容）、发布前后的探针、`admin` 的处置结果、代码是 clone 来的还是走了兜底、预检容量闸的处理。提交并推送 release 分支（🛑 需要 Fan 点头）。然后删临时 worktree：先执行 `git -C /private/tmp/claude-501/rel-admin-guard status --ignored`，确认里面没有需要保留的东西，再执行 `git -C /Users/fan/Repositories/katrain worktree remove /private/tmp/claude-501/rel-admin-guard`。

---

## Self-Review 记录

- 对照 spec 的覆盖：§4 的三个问题分别落在 Task 1、Task 2、Task 6；前端只读落在 Task 4；承重实测落在 Task 5；「会改变谁能编辑教程」落在 Task 6；「先测试机再生产」落在 Task 7。Task 3（Bearer 只认 access token）是评审新增的，Fan 2026-09-24 定保留，对应 spec §4 表格的第四行。
- 占位符：`<用户名>`、`<站点>`、`<SHA>`、`<TS>`、`<WEB_ID>`、`<CRON_ID>`、`<GITDIR>` 都是**运行时才知道的输入**，每一个都写明了从哪一步、哪条命令的输出取得，不属于没写完的内容。
- 名字一致：`_create_admin_and_login`、`_fake_tts`、`canEdit`、`AuthUser`、`newfail.sh`、`anchors-<SHA>.txt` 在各任务之间用法一致。
- 2026-09-24 按 writing-plans 模板复核：原来单独的「准备环境 + 记录基线」（旧 Task 0）和「回归验证 + 两套构建」（旧 Task 5）并进了用到它们的任务；每个任务都有 Interfaces；「有失败就 `git stash` 回去复跑」改成了事先按用例名字记 vitest 基线（katrain 的十个 worktree 共用一条 stash 栈）。
- 2026-09-24 Codex 第一轮对抗评审（12 条）之后的修订：
  - 采纳：选项 B 单独改口令撤不掉已签发的令牌，并据此新增 Task 3；发布前先看盘，容量闸红了由 Fan 当场决定，不预先授权；在合并结果上跑 release 的 PREVIEW 守卫测试；记回滚锚点、等健康、写明回滚命令；`test_tutorial_db_api.py` 里 3 条基线就红的用例让「整文件全绿」不可能，改用 `newfail.sh` 按名字比；探针循环不再依赖词分割；门禁命令加 `pipefail`；撤旧管理员之前，先让新管理员真实登录一次；`clone --depth 1` 失败时的兜底；vite 只杀自己记下的 PID；接口说明补上 strict Box 例外。
  - 部分采纳：前端测试删掉两条永远成立的断言（「生成语音并保存」「保存文字」只在讲解编辑态出现）。
  - 不采纳：「管理员编辑到一半失去权限」的状态转换测试，以及给 `BoardEditToolbar` 再加一层 `canEdit`。进入编辑态的唯一入口「编辑」按钮已经门控；真正的闸在后端；编辑中途被登出只会卡在编辑态，刷新即恢复，不是安全问题。
  - 同形状排查：这一轮顺带发现，发布步骤原来在 cron 镜像也重建时仍只 `up -d katrain-web`，已改成 dry-run 和 `up -d` 都带上 `katrain-cron`。
  - 同形状补齐（来自 cron 切片那一轮）：跑测试之前先确认 `katrain/config.json` 干净；pytest 退出码只接受 0/1；备份比对时表清单不许为空；env 改成候选文件先过预检、再原子替换；合并后核对 `Dockerfile.web` 仍是 release 那份 4 阶段构建。
- 2026-09-24 Codex 第二轮（6 条）之后的修订，全部采纳：删掉「保留 admin 管理员身份、只改口令」的选项（旧 refresh token 还能去 `/auth/refresh` 换新令牌，要保留就得另做密钥轮换，单独出计划）；授权用数字 id，不把用户名拼进 SQL/shell；测试机 katrain-web 没有 healthcheck，改用 curl 健康端点；生产等健康显式失败、重建 cron 时也等 cron；前端门禁改用 `vitestnewfail.sh`（只接受退出码 0/1、报告必须新生成且非空），门禁代码块用 `set -euo pipefail`；写明 `! ` 前缀只在 Claude Code 输入框里用。另外把 cron 切片那一轮指出的备份比对问题一并改了：dump 前后各数一遍，恢复出来的行数必须落在两数之间，对不上就非零退出。
- 2026-09-24 实跑验证：Task 3 按原文改进导出的代码树。`tests/web_ui` 全量（约 1360 条）改前 / 改后按用例名字比较，唯一的差别是新写的 `test_refresh_token_is_not_a_bearer_credential`：改前红、改后绿。其余失败名单一模一样，都是这个环境里原本就红的。
