#!/usr/bin/env python3
"""Fetch explicitly locked plugin archives, then verify checksum and descriptor.

Without --download this only verifies local files. No image/service is started.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
MAX_PLUGIN_BYTES = 50 * 1024 * 1024


def verify_plugin(path, plugin, version):
    digest = hashlib.sha512()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != plugin["sha512"]:
        raise ValueError("plugin checksum mismatch: " + plugin["name"])
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.endswith("plugin-descriptor.properties")]
        if len(names) != 1 or archive.getinfo(names[0]).file_size > 65536:
            raise ValueError("invalid plugin descriptor")
        descriptor = {}
        for line in archive.read(names[0]).decode("utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith(("#", "!")):
                key, value = line.split("=", 1)
                descriptor[key.strip()] = value.strip()
    if (
        descriptor.get("name") != plugin["name"]
        or descriptor.get("elasticsearch.version") != version
        or descriptor.get("version") != version
    ):
        raise ValueError("plugin name/Elasticsearch patch mismatch: " + plugin["name"])
    return {
        key: descriptor.get(key) for key in ("name", "version", "elasticsearch.version", "java.version", "classname")
    }


def prepare(destination, download=False):
    lock = json.loads((ROOT / "versions.lock.json").read_text())
    destination.mkdir(parents=True, exist_ok=True)
    verified = []
    for plugin in lock["plugins"]:
        path = destination / plugin["filename"]
        if download and not path.exists():
            with tempfile.NamedTemporaryFile(dir=destination, suffix=".part", delete=False) as stream:
                temporary = Path(stream.name)
                try:
                    request = urllib.request.Request(plugin["url"], headers={"User-Agent": "kifu-es-pinned-build/1"})
                    with urllib.request.urlopen(request, timeout=30) as response:
                        total = 0
                        while block := response.read(1024 * 1024):
                            total += len(block)
                            if total > MAX_PLUGIN_BYTES:
                                raise ValueError("plugin archive exceeds 50 MiB limit")
                            stream.write(block)
                    stream.flush()
                    verify_plugin(temporary, plugin, lock["elasticsearch_version"])
                    temporary.replace(path)
                    path.chmod(0o644)
                finally:
                    temporary.unlink(missing_ok=True)
        verified.append(verify_plugin(path, plugin, lock["elasticsearch_version"]))
    (destination / "plugins.sha512").write_text(
        "".join(plugin["sha512"] + "  " + plugin["filename"] + "\n" for plugin in lock["plugins"])
    )
    return {"base_image": lock["base_image"], "platform": lock["platform"], "plugins": verified}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--directory", type=Path, default=ROOT / ".plugins")
    args = parser.parse_args()
    print(json.dumps(prepare(args.directory, args.download), sort_keys=True))
