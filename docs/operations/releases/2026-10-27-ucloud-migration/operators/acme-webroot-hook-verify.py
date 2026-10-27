import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time

os.umask(0o077)
assert os.geteuid() == 0 and socket.gethostname() == "10-60-162-188"
base = Path("/var/lib/ucloud-migration-20261027/dns-cutover")
finish = base / "acme-webroot-hook-finish.private.json"
assert not finish.exists()
hook = Path("/etc/letsencrypt/renewal-hooks/deploy/20-reload-nginx-webroot")
assert hook.stat().st_uid == 0 and hook.stat().st_gid == 0
assert hook.stat().st_mode & 0o777 == 0o755
names = ("modelstella.com", "smartbox-platform", "pitch-api-staging.modelstella.com")


def hashes():
    return {
        n: hashlib.sha256((Path("/etc/letsencrypt/live") / n / "fullchain.pem").read_bytes()).hexdigest()
        for n in names
    }


def show(name):
    return subprocess.check_output(["systemctl", "show", "nginx", "-p", name, "--value"], text=True).strip()


before = hashes()
pid = show("MainPID")
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
since = int(time.time())
logpath = base / "acme-webroot-hook-output.private.log"
with logpath.open("xb") as log:
    result = subprocess.run([
        "certbot", "renew", "--cert-name", "smartbox-platform", "--dry-run",
        "--run-deploy-hooks", "--non-interactive", "--no-random-sleep-on-renew", "-v",
    ], stdout=log, stderr=subprocess.STDOUT, check=False)
after = hashes()
marker = "nginx reload completed for /etc/letsencrypt/live/smartbox-platform"
journal = subprocess.check_output([
    "journalctl", "-u", "nginx.service", "--since", "@" + str(since), "--no-pager", "-o", "json",
], text=True)
messages = [json.loads(line).get("MESSAGE", "") for line in journal.splitlines() if line]
reloads = [message for message in messages if "Reloaded " in message]
record = {
    "StartedUTC": started,
    "FinishedUTC": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "ExitCode": result.returncode,
    "HookSHA256": hashlib.sha256(hook.read_bytes()).hexdigest(),
    "HookSuccessMarkerPresent": marker in logpath.read_text(),
    "NginxReloadSuccessJournal": reloads,
    "BeforeCertificateSHA256": before,
    "AfterCertificateSHA256": after,
    "LiveCertificatesUnchanged": before == after,
    "BeforeNginxMainPID": pid,
    "AfterNginxMainPID": show("MainPID"),
    "NginxActive": show("ActiveState") == "active",
}
record["Success"] = (
    result.returncode == 0 and record["HookSuccessMarkerPresent"] and bool(reloads)
    and before == after and record["NginxActive"]
    and pid != "0" and pid == record["AfterNginxMainPID"]
)
finish.write_text(json.dumps(record, indent=2, sort_keys=True))
assert record["Success"], "Inspect the preserved hook/output/journal; do not infer hook success from certbot exit alone"
