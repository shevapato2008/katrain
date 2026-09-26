"""Run the dedicated admin ASGI service behind a loopback-only host port."""

import uvicorn

from katrain.web.admin.app import create_admin_app
from katrain.web.admin.settings import local_vision_requested


def main() -> None:
    host = "127.0.0.1" if local_vision_requested() else "0.0.0.0"
    app = create_admin_app(bind_host=host)
    uvicorn.run(app, host=host, port=8010)


if __name__ == "__main__":
    main()
