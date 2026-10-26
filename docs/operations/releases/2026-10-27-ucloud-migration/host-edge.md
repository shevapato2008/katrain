# New UCloud host edge preparation — 2026-10-27

Target: SSH alias `ucloud-v100`, hostname gate `10-60-162-188`.
Status: prepared for controller preflight. No public ingress, VPN activation, or receiver write was performed.

## Installed

- nginx `1.24.0-2ubuntu7.18`
- certbot `2.9.0-1`
- python3-certbot-nginx `2.9.0-1`
- wireguard-tools `1.0.20210914-1ubuntu4`
- Apt result: 0 upgraded, 11 newly installed, 0 removed. Docker's start timestamp stayed unchanged.
- Temporary install-only `policy-rc.d` guard was removed/restored exactly to its original state.

## Nginx and certificates

- Restored original `/etc/nginx`, complete `/etc/letsencrypt` tree, and ACME webroot. Certificate/archive bytes, live symlinks, and original modes were checked against the archive.
- Final config remains `/etc/nginx/nginx.conf`, with original public listener addresses. Its systemd service is masked and inactive.
- Preserved the five domains and existing proxy, WebSocket, TLS, gzip, allowlist and denial behavior.
- Six old optional module-loading symlinks pointed to packages absent on the new host. Those unused links were moved to private backup; no old binary modules were copied. Both final and stage configs pass nginx 1.24 `-t`.
- Added only the approved `/media/` proxy for `modelstella.com` and `www.modelstella.com`, with Host, Range, If-Range and streaming preserved. Its upstream now uses a controlled private MinIO bridge target; see the verified media update below. MinIO policy and authentication behavior were not changed.
- Certificate expiration (UTC): modelstella/www 2027-01-02 11:35:28; lobby/ranked 2027-01-17 09:46:37; pitch-api-staging 2027-01-03 12:13:25. No issuance or DNS change occurred.

Independent loopback process is running with:

```sh
sudo nginx -c /var/lib/ucloud-migration-20261027/host-edge/staging/nginx/nginx.conf -e /var/lib/ucloud-migration-20261027/host-edge/logs/stage-start.log
```

Its only listeners are `127.0.0.1` and `::1` ports `18080` and `18443`. Separate PID: `/var/lib/ucloud-migration-20261027/host-edge/staging/nginx.pid` (observed master PID 7306). Independent logs are private under `host-edge/logs`, mode 600.

```sh
# Check final configuration (does not start public ingress)
sudo nginx -t
# Check / reload / stop the loopback process
sudo nginx -t -c /var/lib/ucloud-migration-20261027/host-edge/staging/nginx/nginx.conf
sudo nginx -s reload -c /var/lib/ucloud-migration-20261027/host-edge/staging/nginx/nginx.conf
sudo nginx -s quit -c /var/lib/ucloud-migration-20261027/host-edge/staging/nginx/nginx.conf
# Run on the new host; normal certificate verification is enabled
curl --noproxy '*' --resolve modelstella.com:18443:127.0.0.1 https://modelstella.com:18443/
```

Observed before app containers were started: all five domains completed TLS with curl verify result 0; modelstella/www/pitch root returned 502 (backend preflight pending); lobby/ranked roots and lobby `/docs` returned their expected 404; modelstella HTTP returned 301. `/media/` initially returned 502 before MinIO readiness. The subsequent real MinIO object/Range check passed as recorded below. Web application health remains a separate pending preflight.

## Receiver and gateway authorization

- Created `kifu-receiver`: uid 999, gid 987, home `/home/kifu-receiver`, shell `/bin/sh`, sole group `kifu-receiver`, password locked.
- Wrapper `/usr/local/sbin/kifu-incremental-receive-root` is root:root 755 and archive-identical. It targets original container `katrain-ucloud-katrain-web-1`.
- Sudoers `/etc/sudoers.d/kifu-incremental-receiver` is root:root 440, archive-identical, and passes `visudo -cf`; it permits only the no-argument wrapper.
- Original public authorization is preserved byte-for-byte only in `/home/kifu-receiver/.ssh/authorized_keys.pending`, mode 600. Fingerprint: `SHA256:fR0z2USlsVSX6QGXNPNwu+BI3l13xLzNV4WoSWMlaGY`.
- Active `authorized_keys` is empty, mode 600; `authorized_keys2` is absent. Effective sshd settings have no AuthorizedKeysCommand or TrustedUserCAKeys. No receiver invocation/write was attempted.
- New ubuntu `authorized_keys` contains the exact original restricted gateway public-key authorization, with fingerprint `SHA256:+k7/XSoYEnpIS5VRyrAL/eptSyRFFpSo78D5zWgssZE`. Existing Mac authorization bytes were preserved; private pre-change backup exists. No gateway private key or old sshd/host key was copied.

## WireGuard and gates

- Restored original `/etc/wireguard/wg0.conf`, archive-identical, root:root 600; directory root:root 700.
- No WireGuard interface exists. `wg-quick@wg0.service` is masked and inactive.
- `nginx.service`, `certbot.timer`, and `certbot.service` are also masked and inactive; no port 80/443 listener exists.
- Verified: `PublicIngressDisabled=true`, `ReceiversDisabled=true`, `VPNDisabled=true`, `DockerNotRestarted=true`.

## Controller-only activation work remaining

1. Complete real application and receiver dry-readiness preflight; preserve no-write fences until handoff. After every MinIO recreation, refresh its private upstream and repeat the proven object/Range check below before cutover.
2. At the approved cutover point, stop loopback nginx if desired, recheck final `nginx -t`, then unmask and enable/start `nginx.service`.
3. Only after the old VPN identity is down, unmask and enable/start `wg-quick@wg0.service`; never run both hosts as 10.8.0.3.
4. At the receiver/writer handoff, atomically replace active authorized_keys with the exact pending file (600, kifu-receiver ownership), then conduct the controller-authorized receive/producer checks. Never start a second producer.
5. After public ingress is active and verified, unmask certbot service/timer and enable/start only `certbot.timer`.

No activation command above has been executed. Controller owns cutover, public ingress, VPN and writer activation.

Private remote backups, full logs and generated stage tree: `/var/lib/ucloud-migration-20261027/host-edge` (root-only parent directories; full logs mode 600). No secret content was copied into this report or Git.


## Verified media bridge update

Docker 29 reports MinIO ports `9000/tcp` and `9001/tcp` as null with the original `katrain-ucloud_backend` network `Internal=true`; the manifest's intended loopback/VPN publications are ineffective. `127.0.0.1:9000` refuses connections. The host can reach the existing private backend bridge address. No external Docker network, public port, bucket policy change, auth bypass or runtime-manifest change was introduced.

Final and stage modelstella media locations now proxy through named upstream `katrain_minio_media`. Both read the one generated include `/etc/nginx/snippets/minio-media-upstream.conf` (current inspected target `172.19.0.2:9000`).

The root-owned executable `/usr/local/sbin/refresh-minio-upstream.py` reads only container `katrain-ucloud-minio-1` and network `katrain-ucloud_backend`. It refuses the wrong host, non-root execution, a stopped container, a missing backend, an address outside `172.19.0.0/16`, or a network that is not internal. It atomically updates the include and tests both final and stage nginx configurations, restoring the previous include on validation failure. It never reloads nginx or starts public ingress.

**Required after every MinIO recreation, including controller recreate-final:**

```sh
sudo /usr/local/sbin/refresh-minio-upstream.py
# During the current migration stage, reload only the independent loopback process:
sudo nginx -s reload -c /var/lib/ucloud-migration-20261027/host-edge/staging/nginx/nginx.conf
# After final public nginx is activated, the controller instead reloads that final process:
# sudo nginx -s reload -c /etc/nginx/nginx.conf
```

Then repeat the same known public object Range check. This explicit refresh is required because the container bridge IP is dynamic; there is no automatic container lifecycle hook.

Verified object: `tutorial_assets/曹薰铉布局技巧-上册-曹薰铉-1997/pages/page_011.png`.

- TLS URL: `https://modelstella.com:18443/media/<object-key>`, with curl SNI/resolve to `127.0.0.1` and `Range: bytes=0-1023`.
- HTTP `206`; TLS verify `0`; Content-Type `image/png`; Content-Length `1024`; Accept-Ranges `bytes`; Content-Range `bytes 0-1023/64338`.
- Exact returned bytes: `1024` (PNG signature checked).
- SHA256: `68f53c831803a81cd42b6a09be11c09030c4ee07f7a2774028c6882081650ad4`.
- Direct MinIO request for this same object/range returned `206` and identical bytes. No bucket enumeration or data write occurred.
- Only stage nginx was reloaded. Final nginx remains masked/inactive, with no port 80/443 listeners.

Private range headers, bodies and result metadata: `/var/lib/ucloud-migration-20261027/host-edge/logs/media-range-1024.*` (mode 600). Refresh validation logs: `host-edge/logs/refresh-minio-upstream.log` (mode 600).
