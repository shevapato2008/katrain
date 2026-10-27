import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess

os.umask(0o077)
assert os.geteuid() == 0
assert socket.gethostname() == "10-60-162-188"
earliest = datetime.datetime.fromisoformat("2026-10-27T02:52:17.072462+00:00")
assert datetime.datetime.now(datetime.timezone.utc) >= earliest, "Full authoritative TTL has not elapsed"
base = Path("/var/lib/ucloud-migration-20261027/dns-cutover")
base.mkdir(mode=0o700, exist_ok=True)
finish = base / "acme-handoff-finish.private.json"
assert not finish.exists(), "Preserve the existing execution receipt; do not replay blindly"
names = ("modelstella.com", "smartbox-platform", "pitch-api-staging.modelstella.com")
assert sorted(p.stem for p in Path("/etc/letsencrypt/renewal").glob("*.conf")) == sorted(names)


def certificate_hashes():
    return {
        name: hashlib.sha256(
            (Path("/etc/letsencrypt/live") / name / "fullchain.pem").read_bytes()
        ).hexdigest()
        for name in names
    }


before = certificate_hashes()
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
command = [
    "certbot", "renew", "--dry-run", "--non-interactive", "--no-random-sleep-on-renew"
]
# The installed 2.9 CLI source explicitly supports the hidden no-random-sleep flag.
# Existing authenticators are retained; no --force-renewal or deploy hook is used.
with (base / "acme-handoff-output.private.log").open("xb") as log:
    result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
after = certificate_hashes()
record = {
    "AuthoritativeTTLNotBeforeUTC": earliest.isoformat(),
    "StartedUTC": started,
    "FinishedUTC": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "ExitCode": result.returncode,
    "BeforeCertificateSHA256": before,
    "AfterCertificateSHA256": after,
    "LiveCertificatesUnchanged": before == after,
    "Success": result.returncode == 0 and before == after,
}
finish.write_text(json.dumps(record, indent=2, sort_keys=True))
assert record["Success"], "Read the preserved output; do not enable the timer on failed proof"
