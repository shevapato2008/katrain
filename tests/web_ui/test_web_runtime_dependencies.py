import os
from pathlib import Path
import subprocess
import sys


def test_web_api_starts_without_optional_xiangqi_runtime_packages():
    root = Path(__file__).parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from katrain.web.api.v1.api import api_router; "
            "print(any(route.path.startswith('/xiangqi-ranked') for route in api_router.routes))",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.rstrip().endswith("False")
