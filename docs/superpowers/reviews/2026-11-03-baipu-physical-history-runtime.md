# Physical replay and account-history runtime verification

Candidate built with `npm run build:kiosk-2d`; TypeScript, production build and no-three.js boundary guard passed. Tests used genuine candidate API routers and dedicated disposable SQLite accounts, never production user history.

- Desktop1024×600: loaded the exact140859 SGF through authoritative API, reloaded history URL, resumed at225. Entry acknowledgement and pre-removal did not change persisted225; only completing replacement placement committed226/revision2. Full-step backend total347 retained.
- Actual RK3562 at1024×600, temporary SSH-forwarded candidate production build: Wu search previews rendered; recent tab retrieved three account-backed rows, including226 saved from the other browser. Selected118394 through recent→reloadable history URL→resume190→authoritative entry→pre-removal C9. Status/actions fit the existing page geometry.
- Camera device `/dev/smartbox-cam` absent. Camera recognition, physical LED output and real camera captures are not claimed verified. Deterministic reducer/hook/capture fakes cover these contracts separately.
- Isolated runtime deliberately had no engine/hardware services; its header engine-not-ready state and missing-logo asset were not part of the product changes. Hardware endpoint404s were expected in this harness; do not interpret them as clean full-network coverage.
- RK original `http://127.0.0.1:8081/kiosk/kifu` restored, temporary-origin test credential removed, browser detached, SSH forwards closed. Original account storage/cookies and deployed files were preserved.

Representative actual RK screenshots are in `evidence/2026-11-03-baipu-physical-history/`. No production deployment or production DB writes occurred.
