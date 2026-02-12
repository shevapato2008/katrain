# Manual Testing Guide: Board-Mode Auth Forwarding

> Covers design sections 5.1-5.4: auth endpoint forwarding, dual-layer token, shadow user, logout cleanup.

## Prerequisites

- Remote server running with at least one registered user account
- RK3588 board (or any machine) with this branch checked out
- `curl` or similar HTTP client
- `sqlite3` CLI for inspecting local database

## 1. Start Board-Mode Server

```bash
# Set environment variables
export KATRAIN_MODE=board
export KATRAIN_REMOTE_URL=https://<remote-server-ip>:8001  # your remote server (http:// or https://)
export KATRAIN_DEVICE_ID=test-board-001                    # stable device ID for testing
export KATRAIN_DATABASE_URL=sqlite:///./board_test.db      # force local SQLite (see note below)

# Start
python -m katrain --ui web --port 8001
```

> **Note:** Must use `KATRAIN_DATABASE_URL` (not `KATRAIN_DATABASE_PATH`).
> If `~/.katrain/config.json` contains a `server.database_url` (e.g. PostgreSQL),
> it takes precedence over `KATRAIN_DATABASE_PATH`. Setting `KATRAIN_DATABASE_URL`
> explicitly is the only way to override it.

Verify startup log shows:
```
Database: Using SQLite at ./board_test.db
Starting in BOARD mode (device=test-boa..., remote=https://...)
```

## 2. Test Login (Design 5.1 + 5.2 + 5.3)

### 2.1 Successful login

```bash
curl -s -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "<remote_user>", "password": "<remote_pass>"}' | python -m json.tool
```

**Expected response:**
```json
{
    "access_token": "<local_jwt>",
    "token_type": "bearer",
    "refresh_token": "<local_refresh_jwt>"
}
```

**Verify checklist:**

- [ ] Response 200 with both tokens
- [ ] `access_token` is a local JWT (decode with local SECRET_KEY):
  ```bash
  python -c "
  from jose import jwt
  token = '<paste access_token>'
  print(jwt.decode(token, 'katrain-secret-key-change-this-in-production', algorithms=['HS256']))
  "
  ```
  Should show `{"sub": "<username>", "exp": ..., "type": "access"}`
- [ ] Shadow user created in local SQLite:
  ```bash
  sqlite3 board_test.db "SELECT id, username, hashed_password FROM users;"
  ```
  Should show a row with `hashed_password = SHADOW_USER_NO_LOCAL_AUTH`
- [ ] Remote refresh_token persisted to encrypted file:
  ```bash
  ls ~/.katrain/credentials/
  ```
  Should contain a `cred_*.enc` file

### 2.2 Wrong credentials

```bash
curl -s -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "wrong", "password": "wrong"}'
```

- [ ] Response 401 with `"Incorrect username or password"`
- [ ] No new row in `sqlite3 board_test.db "SELECT * FROM users WHERE username='wrong';"`

### 2.3 Repeat login (shadow user reuse)

```bash
# Login again with same user
curl -s -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "<remote_user>", "password": "<remote_pass>"}'
```

- [ ] Response 200
- [ ] Still only ONE row for that username: `sqlite3 board_test.db "SELECT count(*) FROM users WHERE username='<remote_user>';"`

## 3. Test /me (get_current_user with shadow user)

```bash
TOKEN="<paste access_token from step 2.1>"

curl -s http://localhost:8001/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

- [ ] Response 200 with `"username": "<remote_user>"`
- [ ] `id` field is the local shadow user ID (integer)

## 4. Test Register (Design 5.1)

```bash
curl -s -X POST http://localhost:8001/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "newuser_test", "password": "testpass123"}'
```

- [ ] Response 200 with user data from remote server
- [ ] User created on remote: verify by logging into remote server directly
- [ ] No local shadow user created yet (register doesn't create shadow — login does)

### 4.1 Duplicate registration

```bash
curl -s -X POST http://localhost:8001/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "<existing_remote_user>", "password": "pass"}'
```

- [ ] Response 400 with `"User already exists"` (or similar from remote)

## 5. Test Refresh (Design 5.1 + 5.2)

```bash
REFRESH="<paste refresh_token from step 2.1>"

curl -s -X POST http://localhost:8001/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH\"}" | python -m json.tool
```

- [ ] Response 200 with new `access_token`
- [ ] New token is valid: use it with `/me` endpoint
- [ ] Old access_token still works (until it expires naturally)

### 5.1 Invalid refresh token

```bash
curl -s -X POST http://localhost:8001/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "garbage"}'
```

- [ ] Response 401 with `"Invalid or expired refresh token"`

## 6. Test Logout (Design 5.4)

```bash
TOKEN="<paste a valid access_token>"

curl -s -X POST http://localhost:8001/api/v1/auth/logout \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

- [ ] Response 200 with `"Logged out successfully"`
- [ ] Credential file deleted: `ls ~/.katrain/credentials/` should be empty (or file gone)
- [ ] Remote tokens cleared: subsequent API calls through RemoteAPIClient should require re-login

### 6.1 Verify logout invalidates remote session

```bash
# After logout, try login again — should work (remote server still has the account)
curl -s -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "<remote_user>", "password": "<remote_pass>"}'
```

- [ ] Response 200 (fresh login succeeds)
- [ ] New credential file created in `~/.katrain/credentials/`

## 7. Test Error Cases

### 7.1 Remote server down

```bash
# Stop the remote server, then try login
curl -s -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user", "password": "pass"}'
```

- [ ] Response 503 with `"Cannot connect to remote server"`

### 7.2 Register with remote down

```bash
curl -s -X POST http://localhost:8001/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "u", "password": "p"}'
```

- [ ] Response 503

## 8. Server-Mode Regression Check

```bash
# Restart WITHOUT board mode
unset KATRAIN_MODE
unset KATRAIN_REMOTE_URL
export KATRAIN_DATABASE_PATH=server_test.db

python -m katrain --ui web --port 8001
```

```bash
# Register + login locally (no remote)
curl -s -X POST http://localhost:8001/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "localuser", "password": "localpass"}'

curl -s -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "localuser", "password": "localpass"}'
```

- [ ] Both work with local DB only (no remote calls)
- [ ] `hashed_password` in DB is a proper bcrypt hash (NOT `SHADOW_USER_NO_LOCAL_AUTH`)

## 9. Frontend Integration (Browser)

1. Open `http://localhost:8001` in browser (board mode running)
2. Use the login form with remote credentials
3. Verify:
   - [ ] Login succeeds, UI transitions to authenticated state
   - [ ] Token stored in `localStorage` (DevTools > Application > Local Storage)
   - [ ] Page refresh maintains auth (token persists)
   - [ ] Logout clears token and returns to login screen

## Cleanup

```bash
rm -f board_test.db server_test.db
rm -rf ~/.katrain/credentials/
```
