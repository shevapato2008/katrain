"""Run the dedicated admin ASGI service behind a loopback-only host port."""

import uvicorn


if __name__ == "__main__":
    uvicorn.run("katrain.web.admin.app:create_admin_app", factory=True, host="0.0.0.0", port=8010)
