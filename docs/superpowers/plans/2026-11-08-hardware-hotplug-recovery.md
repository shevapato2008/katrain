# Camera and Board Hotplug Recovery Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 摄像头重新被 Linux 枚举后立即启动自动重连，标定页自动恢复新画面；围棋棋盘 Type-C/Board B USB 断开再接入后恢复诚实状态和当前有效指示，不重启整机，不执行过期灯光命令。

**Architecture:** 摄像头使用可选的 processed-udev 事件监听唤醒现有唯一恢复线程，并以低频轻量检查兜底；不新增守护服务、Python依赖或USB复位逻辑。Board A Type-C 不产生 Linux 设备事件，保留既有 LINK 查询；补齐 Board B 静默失联、过期批次和当前指示恢复。标定预览失败时隐藏旧图、降低失败重试频率，成功后恢复正常取图。

**Tech Stack:** Python 3.11, threading/subprocess/selectors, installed Linux udevadm, OpenCV, pyserial, FastAPI, React/Vitest, existing Docker/native-systemd deployment tooling.

---

## Chunk 1: Evidence, implementation, verification and release

### Confirmed scope and investigation

- 用户要求先用 writing-plans 写可执行计划；独立 `gpt-6-astra` / `max` 审核计划最多两轮并修改；通过后 subagent-driven-development 并行开发；新的独立 Astra Max 代码审核、修改直至通过；按四步流程发布 TEST、PROD、RK3562。用户将在收到完成通知后亲自进行物理拔插验证，不把尚未执行的物理验收写成通过。
- 当前工作区是已隔离的 `/Users/fan/Repositories/katrain-kiosk-debug`、`fix/kiosk-ui-debug`。开始调查时基线为 `237e6d62952b58dea5da675b937f7333440106a9`；计划审核期间已先快进到最新 develop `954a374bdd0cf5661a9e7e556af7f699928edfbe`，未编辑产品代码。上游新增 appearance/preferences 已纳入后续发布的实际运行时差量。复用此专用 worktree；Git 集成和父仓发布用上次建立的干净独立 worktree，不动其他开发 worktree。
- 基线聚焦检查：`.venv/bin/python -m pytest tests/test_camera_hub.py tests/test_vision/test_camera_recovery.py tests/test_led_service.py tests/test_led_api.py -q` → **109 passed**。
- 设备为 `rk3562-local` → `192.168.0.104`、hostname `gzpeite`。调查起点 Go target/KaTrain active、用户在标定页；只读状态无 bound game，geometry `required`，camera false、model true、LED true。后续唯一 CDP page 已变为 `/kiosk/baipu/session/kifu_25047`。发布前必须重新读取，不能假定仍停在标定页。
- 当前摄像头 `0ac8:0346` / HBV HD CAMERA 不在 lsusb、sysfs 或 `/dev/smartbox-cam`。内核17:08记录 descriptor read `-71`、unable to enumerate。只能确认枚举失败，尚不能断言线材、接口、供电、摄像头或 hub 中哪一个是根因。原 udev 规则正确且已安装。
- 相机与 ESP 是同一个 `1a40:0101` hub 的 port4 / port3；hub 实测为 **ganged power switching**，无可用安全独立断电接口。不得自动 reset hub/controller、切授权、重载驱动或改电源策略，以免影响棋盘或掩盖实体故障。
- `CameraHub` 和 `CameraManager` 都已有5秒恢复/冷却；当前日志证明一直在重试。只唤醒 Hub 无法绕过 Manager 冷却。设备节点不存在时仍反复打开 OpenCV，增加无效工作和日志。
- 棋盘分两层：Board B ESP32-S3 `303a:1001`，`/dev/smartbox-led → ttyACM0`；Board A Type-C 连接由固件 LINK 检测。Board A 拔插不能靠 Linux udev 通知。当前 LINK=UP、ACK=OK、transport connected。
- 实际复现的 LED 缺口：无 ACK 但不抛异常时，serial handle 可一直保留、transport仍显示true；CLEAR/SHOW最多读取16秒，而strict调用者5秒就退出，旧命令可能继续执行。重连前已出队的旧批次没有代际保护；Board A 回来后稳态指示可能受前端去重/围棋240秒重发间隔影响。
- 当前围棋链路及共用 CameraHub/LedService 为范围。无固件更新、标定自动提交、自动落子、数据库迁移、其他棋类独立 readiness 改造或云端设备配置变更。父仓五子棋另有独立 readiness 判断，列入回执限制，不借此扩张本次变更。

### Behavioral contract and proportionality

1. **Camera:** processed udev matching arrival should wake recovery within 500ms after receipt; allow one immediate attempt even within the preceding5秒冷却。有效帧到达后才 ready；曝光稳定和原 warmup 时间单独计量，不承诺物理插入瞬间已有画面。
2. **Identity/lifecycle:** only operate on the configured camera path/its recorded capture node; ignore unrelated cameras and metadata nodes, coalesce duplicate arrivals。保持单 lease/单 reader；blocked old reader 未退出不得开第二个；断开时旧帧失效、旧 reader 不得晚发布。
3. **Absent/event unavailable:** Linux absolute alias missing时不调用 OpenCV；存在性/身份检查用 stat。保留5秒恢复兜底；监视器不可用/退出时不使服务退出、不忙循环、不不断spawn进程。事件到达但udev alias尚未可见时，兜底仍可恢复。
4. **Board A:** LINK 有有效 UP 才 true、DOWN/CABLE_ONLY 为 false、失败/过期为 None。保持2秒正常检测，每次完整 LED 批次之间检查到期 LINK，不能被持续队列无限推迟，也不插入 CLEAR/SETI/SHOW 事务内部。完整无响应或持续非法帧连续3次（每次总读取预算200ms、下次2秒）后关闭并重连；有效 legacy `ERR cmd` 说明串口仍活着，保持 transport、Board A unknown 和原10秒退避，不反复重开。
5. **Board B:** USB消失/ACK超时关闭旧serial并自动恢复；固件明确ERR与传输无ACK区分。串口open/BRIGHT握手成功不等于Board A在线。配置绝对路径消失时只做廉价检查，重新出现时允许及时握手，避免再等完整5秒。
6. **Commands:** strict 批次以提交时单调时钟 deadline 为权威（现有5秒总预算，包含排队和 I/O）。超时/取消/断开代际后的剩余命令不得继续发送，strict 等待者及时拿到失败。**写入、ACK、boot/握手均须有界**：默认 serial 设置有限 `write_timeout`，每次普通命令、LINK、清空、BRIGHT 的写入预算不超过200ms及剩余总预算；写入超时按传输失败处理。boot 等待最多 `handshake_timeout`，清空和 BRIGHT 共享另一个 `handshake_timeout` 总预算；读取限制行长/剩余时间，持续无换行不能延长总预算。不能取消的 native open 继续由现有 lease 保护，禁止第二 worker 越过它。重连不执行断开前排队的捕获/标定批次。
7. **Guidance:** 恢复只重建当前仍有效的非 strict 整帧 guidance，不重放历史命令序列或严格采集图案。新 set_points/clear/set_rgb_points 必须使旧恢复意图失效；clear、取消/离局后不恢复旧灯。Board A 返回/Board B 重连后，在下一有效 LINK 和当前状态下恢复最新有效 guidance。**握手先 CLEAR→有效 ACK→SHOW→有效 ACK，再 BRIGHT→有效 ACK**：实际固件 BRIGHT 会立即显示保留缓冲，不能把 BRIGHT 放在清空前。清空未确认则保持 disconnected；旧 ACK 不得认证新握手。
8. **Preview:** 错误后隐藏旧canvas和几何overlay；仅新成功图像才恢复；失败取图退到1秒一次，正常5fps不变。保持单一in-flight、abort/unmount与对象释放，无CSS/视觉重构。
9. **Honesty:** USB仍枚举失败时部署验收记录设备missing；不能因为事件代码/模拟测试通过就宣称当前物理摄像头已恢复。最终用户物理拔插验收单列 pending。

### Stable interfaces and parallel ownership

- A owns camera lifecycle + one small Linux event adapter; B owns LED service; C owns preview。无共同编辑文件。用户明确要求并行，覆盖技能默认串行实现建议；控制器串行commit/index/build/push。
- 事件适配器建议 `UdevDeviceMonitor(device_path, callback)` with `start()/stop()`；callback仅传目标设备的 `added/removed` 事件（重复事件合并）。实现可保持叶子模块；不建全局device registry。`udevadm monitor --udev --subsystem-match=video4linux --property` 仅启动一次，固定argv、无shell，bounded parsing，先订阅再初始reconcile。stop只终止自己的child并join自己的thread。
- Hub callback只登记事件并唤醒自己的recovery owner，不在回调/OpenCV reader中抢开设备。Manager增加明确的hotplug通知/立即尝试入口，在其已有lifecycle锁内验证并更新状态，不能由Hub写其私有cooldown字段。失败保持原重试预算；真实断开后同路径设备返回可触发新一次立即尝试。
- B可在原worker中用configured-path stat身份变化解除重连冷却，不依赖A新模块；保留 fake serial 与非Linux适配器测试接缝。

### Task 0 — Plan review gate (controller)

**Files:** this plan; `docs/superpowers/reviews/2026-11-08-hardware-hotplug-plan-astra-max.md`.

- [x] Dispatch isolated `gpt-6-astra`, `max`, `fork_turns=none` with user requirements, repo path, plan path and investigation facts only. Ask for actual-code review of feasibility, camera lifecycle, BoardA/B distinction, strict deadlines/stale commands, safe deployment, and physical-acceptance honesty.
- [x] Revise and re-review at most two rounds. If still blocking after round2, stop code stage and report findings; do not create round3. Save final review verdict.
- [x] Commit approved plan. User already authorized execution; no repeat approval question.

### Task 1 — Camera event-driven recovery (fresh worker A)

**Files owned:**
- Create `katrain/vision/device_events.py`, `tests/test_vision/test_device_events.py`.
- Modify `katrain/vision/camera.py`, `katrain/web/core/camera_hub.py`.
- Extend `tests/test_vision/test_camera_recovery.py`, `tests/test_camera_hub.py`.

- [ ] Write failing tests for exact matching processed add/remove, unrelated/metadata/duplicate events, bounded parser/child failure, startup race/stop and unsupported-platform fallback. Inject fake process/event source; no realdevice/service interaction.
- [ ] Write failing integration cases: arrival within cooldown opens immediately once; absence avoids capture open; removal clears cached frame; samealiasnewdevice returns; lost-event timer recovers; blocked old reader never overlaps; stop during event cannot reopen. Preserve existing no-consumer recovery tests.
- [ ] Run `.venv/bin/python -m pytest tests/test_vision/test_device_events.py tests/test_vision/test_camera_recovery.py tests/test_camera_hub.py -q` and record expected RED.
- [ ] Implement the smallest adapter and event-aware recovery per contract. All platform-specific behavior optional; no third-party install, udev rule change or reset. Avoid changing capture/vision caller APIs except the explicit manager entry used byHub.
- [ ] Run same tests plus `tests/test_vision/test_camera_status_is_honest.py` and `tests/web_ui/test_board_lifespan_camera_degraded.py`; baseline unrelated failures must be distinguished, not fixed by broad refactors.
- [ ] Report own-file diff/RED/GREEN, lifecycle limits and measured fake-event latency. No gitcommit/index/release; controller commits `recover camera on device arrival`.

### Task 2 — Board Type-C/serial recovery and current LED output (fresh worker B)

**Files owned:** `katrain/web/core/led_service.py`, `tests/test_led_service.py`, `tests/test_led_api.py`.

- [ ] Add fake-clock failing tests for BoardA DOWN→UP/CABLE_ONLY→UP with BoardBserialunchanged, missing/invalid LINK retainsNone, queue-pressure still probes between batches, BoardBdisappearance/reappearance, noACKclose/reconnect and fresh handshake.
- [ ] Add failing strict cases: submit deadline covers queue wait, writes and reads; caller timeout cancels remaining commands; no ACK stops the batch before later SETI/SHOW; old batches waiting across reconnection fail and cannot replay; no ACK cannot leave transport true. Test write timeout, continuous unterminated boot/handshake input, and MCU retaining an old strict pattern: CLEAR/SHOW must be acknowledged before BRIGHT. Firmware ERR remains distinct from transport failure.
- [ ] Add an idle-only silent LINK test with device path still present and no business commands: after3 missing/invalid responses, close and retry. Add a legacy `ERR cmd` control proving the healthy transport is retained without repeated opens.
- [ ] Add guidance cases: recovery uses latest active nonstrict frame only; newer frame/clear wins during reconnect; strictRGB/calibration patterns never replay; BoardAreturn afterdarkbuffer restores currentframe once; teardown keepsleaseuntilworker stops. No publicgame/sessionmutation.
- [ ] Run `.venv/bin/python -m pytest tests/test_led_service.py tests/test_led_api.py -q`, record RED, then implement bounded serial writes and reads, boot/handshake total budgets, batch deadline/cancel/generation and current-output reconciliation in the existing single worker. Preserve LINK partial-line framing and stale-ACK defenses.
- [ ] Keep normalLINK2s/200msreadbudget; servicelease/stop behavior andlegacyfirmwareunknownstate must remain. Any rate/backoff tuning limited to actual disconnected/errorpaths, no new generalqueueframework.
- [ ] Run same tests plus `tests/test_led_geometry_calibrator.py tests/test_geometry_calibration_service.py tests/web_ui/test_led_brightness_loop.py` to verifystrictcapturecompatibility. Reportownfilesandtests; controller commits `recover board link without replaying expired commands`.

### Task 3 — Calibration preview recovery (fresh worker C)

**Files owned:** `katrain/web/ui/src/kiosk/components/vision/GeometryVideoPanel.tsx`; create `katrain/web/ui/src/kiosk/__tests__/GeometryVideoPanel.test.tsx`.

- [ ] Use fake timers/fetch/bitmap/canvas to demonstrate: success→disconnect hidesstaleimage/overlay; repeated503backsoff; validnewframeautomaticallyreappears; switching src/unmount aborts and neverpublishesoldresponse; onlyoneinflight andbitmapclosed.
- [ ] Run from `katrain/web/ui`: `npm test -- src/kiosk/__tests__/GeometryVideoPanel.test.tsx`, recordRED.
- [ ] Minimal implementation: use failure retry interval1000ms vsnormal200ms, setreadyfalseonfailure, gateoverlayoncurrentready/nonerror. Keepinitial/recoverycopyandexistinglayoutunlessanactualreadinessbugrequiresit.
- [ ] Run newtest plus `src/kiosk/__tests__/GeometryCalibrationScreen.test.tsx`. No screenshotbaselineupdates; controltakesoneactualRKpreviewofnewstateafterdeployment. Report; controller commits `resume calibration preview with bounded retries`.

### Task 4 — Bounded publication preparation (controller, independent from A/B/C)

**Files:** one-off tools/evidence in ignored `output/releases/hardware-hotplug-20261108/`; tracked receipt `docs/operations/hardware-hotplug-release-2026-11-08.md`.

- [ ] Copy prior reviewed cloud wrapper/native helper and RK KaTrain-only operator from `output/releases/galaxy-root-20261108/` into new release directory; never overwrite old evidence. Read actual source/test contracts before adapting. Freeze new operator hashes for final Astra review.
- [ ] Cloud runtime allowlist includes the final reviewed hotplug Python modules and complete full static. Compare each live baseline with the published source: if upstream appearance changes are not already deployed, also include `katrain/web/api/v1/endpoints/kiosk_preferences.py` and `katrain/web/core/kiosk_preferences.py`, with their upstream tests. Do not copy a frontend requiring newer API behavior without its runtime changes. Native helper remains pinned `98e816acbe780baf95e8f8168073ba2894efe852bb0bd3c0b454264e89027108`; retain configuration/CAS/private-env/non-Web checks.
- [ ] RK finite manifest covers same changedPython files + completefull/strictstatic. Use fresh-inodebeforefilesandatomicreplace, two staticdirectoryrenames, eMMC1GiBreserve, ownedlock/currentRuntime/oneexistingCDPpage restoration. No `.git`/fulltreerevisionclaim, firmware/udev/powerwrite, broadparentdeploy or database work.
- [ ] Old `.smartbox-release.json` and prior `.katrain-routing-release.json` remain intact; new `.katrain-hardware-release.json` records exactdiffsourceSHA,parentSHA,module/assethashes. Extend operator tests forbeforehashrefusal,newfileabsence/rollback and markerrestore. Preserveoldbackups/journals.
- [ ] Camera enumeration may remain failed as the established external condition. Set this narrow, recorded offline-camera policy on the Runtime instance **before the maintenance transaction**, including old-mode ready/restoration and all early-failure paths; not only inside candidate verification. Record actual false/missing values and monitor state without resetting USB. If hardware enumerates during acceptance, require fresh JPEG/ready and record it. Board A/B current UP/transport health remains required; no waiver for unexplained new regressions.
- [ ] Extend the old operator's original-Go guard and rollback logic explicitly; do not merely delete its refusal. A fresh Go maintenance gate requires: the same single CDP page on `/kiosk/vision/setup` with calibration DOM, or the exact `/kiosk/baipu/session/kifu_<id>` route **only while its guard renders `[data-testid="calib-screen"]`**, with inactive geometry calibration. Baipu itself is not read-only: reject a mounted `[data-testid="baipu-board"]`/active BaipuSessionPage, and require `GET /api/v1/baipu/mode` to report `collect=false`. Also require no game/resume dialog, vision `bound_session_id=null` and `sync_state=unbound`, loopback-only 8081 listener and no established client other than that CDP browser/identified read-only probes. Unknown routes, game routes, another client, bound vision or active calibration refuse maintenance. These combined signals bound the local interactive activity; unbound vision alone is insufficient. Recheck all signals after acquiring the launcher lock, then immediately blank the same page before stopping Go.
- [ ] After this proven original Go is stopped, the new acceptance Go is an owned fresh start even when `original_mode == 'go'`. Under the same lock and untouched about:blank page, a startup API failure may safely stop that newly started target and roll back; never generalize this exception to an unknown preexisting process. Add offline-camera original-Go success/exact-page restoration, API-unreachable startup rollback, apply-before-start failure, unsafe-page/client refusal and lock-loss tests. Do not add an unauthenticated all-session endpoint or treat the strict central multiplayer API as local idle proof.

### Task 5 — Integration, spec check and final independent review (controller)

**Files:** workers' exactdiff; `docs/superpowers/reviews/2026-11-08-hardware-hotplug-code-astra-max.md`.

- [ ] Checkeachownedfilediffandseriallycommit; no gitindexmutationsfromworkers. Run unionofaffectedtests onceintegrationstabilizes, and`git diff --check`.
- [ ] Run full and strictKioskbuildsequentially fromclean publishedcandidatecheckout/immutablearchivewithlockfiledependencies. Retain strictmodule/no-three/live/tokenguards, rootGalaxyURLs andold404behavior. No fullpytest/allscreenshotmatrix.
- [ ] IndependentfreshspecreviewerchecksTask1–3actualcodeandbehavior; fixmaterialgapsbeforequalityreview.
- [ ] NEW independent `gpt-6-astra` / `max` (`fork_turns=none`) reviews base/headproductdiff, finaloperatorhashes, testsandactualfailureboundaries. RequiresAPPROVEDwithoutblocking/importantfindings; fixesreturntoownersandgetrecheckeduntilapproved. Thiscodereviewloopisnotlimitedtotwoplanrounds.
- [ ] Verifyevent/noACKhandlingwithdeterministicfakehardware andsameidentity/stalecommandsnegativecontrols. Reviewresourcecostandboundedstop: nohelperrestartloop/noextraOpenCVopenwhilenodeabsent; sampleactualmonitorprocess/thread/CPUonRKwithoutstartingasecondrenderer.

### Task 6 — Required four-step publication and device acceptance (controller only)

- [ ] **1 Feature:** `git fetch origin`, mergefresh`origin/develop`intocurrentbranch, resolveconflictsaccordingcontract, runaffectedchecks/reviewifnewruntimechanges, commitandpush`fix/kiosk-ui-debug`, noforce.
- [ ] **2 Develop:** inclean`/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/galaxy-root-integration-20261108`, fetch/mergefreshdevelopthenfeature, verifycleanandpushdevelop. Preserveotherdevelopworktrees.
- [ ] **3 Parent:** readparentAGENTS/status/remote; cleanparentreleaseworktree`/Users/fan/.config/superpowers/worktrees/smartbox-software/galaxy-root-release-20261108` mustfirstfastforwardfreshmain. Updateonly`vendor/katrain`gitlinktopublishedsoftwarecommit, commitandpushmain. Original`/Users/fan/Repositories/smartbox-software`preexistingdirtysubmoduleisuntouched.
- [ ] BuildfinalartifactsfrompublishedsoftwareSHAwithcleanlockdependencies; sourceandassetmanifests/finaloperatorsfrozen. IfpublishedSHAchangesonlydocs, clearlyseparateruntimesoftwarefrompostdeployreceiptcommit.
- [ ] **4 TEST→PROD→RK:** follow server-deploy skill's actualconfigpreservation. Reusepinnednativehelperprepare/applyaspriorrelease; freshliveimmutablebaseID, beforeimageandallnonwebsnapshots, same6privateallowlistedroleenvvalues, explicitartifactSHA; verifyprivatepreparedmanifest/CASbeforeapply. Refreshhumanactivitygateandgraceful180sstop. TESTpassbeforePROD; sameNginx,noengine/DB/Cron/MinIOrestart. Checkhealth,rootGalaxy/deeplink/old404/kioskandentryassethashes; keepoldbackupforrollback.
- [ ] RK preflight reloads hostname/service paths/Python, parent Runtime hash, all before hashes, actual mode, unique page ID/exact URL, setup state, game/calibration state, clients and disk/memory. Use Task4's combined gate for original Go, or the prior proven idle-launcher gate for Hermes/idle. Any active/uncertain game or calibration allows staging only; never cancel human work. Do not reuse an earlier snapshot.
- [ ] Run the newly reviewed KaTrain-only operator with immutable manifest and fresh CAS. Restore the original mode and exact original page on success and rollback. For original Go, stop the safely gated old Go once and start upgraded Go through the target; restore the exact original non-game URL, including baipu if that was captured. No browser recreation or other game startup. Apply the recorded offline-camera policy throughout restoration, including failures before verification begins.
- [ ] Actualdeviceacceptance: unchangedPIDafterpostdeployobservation(noongoinghotplugrequiresrestart),configuredalias/udevmonitorstatus,LEDtransport+BoardAUP,geometrycapabilities,rawsnapshotstatus(freshJPEGifcameraavailable; explicit503ifOSmissing),calibrationpageactualrenderandnooldfakeframe. NoLEDflashpattern/automaticcalibration/phantommoveoperationsforacceptance.
- [ ] Observequietmonitor/resourcecostandjournalno5sOpenCVfailurefloodwhilecameraaliasabsent. Recordnewmodule/assetmarkerhashesandoriginalmode/page/lockrestoration. Retainnewandoldbackups; noDocker/devicehistorypruning.
- [ ] PublishconciseChinesecompletionmessageinsessionwithsoftware/parentSHAs,deployedtargets,test/reviewoutcomeandhonestremainingUSBfault. Providephysicalchecksteps:cameraUSBunplug/replug→kernelnode→newframe;BoardATypeC→false/UPandcurrentvalidlights;BoardBUSB→newhandshake/UP;repeatwithoutmanualrefresh/reboot. Physicalresultremainspendinguntiluserconfirms.

### Acceptance checklist

- [ ] Planreview≤2rounds;specandfinalindependentAstraMaxAPPROVED.
- [ ] Matchingcameraarrivalbypassescooldown;absencenocaptureopen;fallbackandstop/lifecyclehonest.
- [ ] BoardA/Bstatesdistinguished;silenttransportfailurecausesboundedreconnect;expired/stalebatchesneverreplay;currentguidancecanrecover.
- [ ] Previewautomaticallyrecoverswithnewframe;nooldimage/overlayduringfailure;failedrequestsbounded.
- [ ] Four-stepGit/releaseflowcomplete;TEST/PROD/RKactualrolloutevidenceandoriginalRKmode/pagepreserved.
- [ ] PhysicalUSBfaultandunexecutedmanualtestsrecordedtruthfully,usernotifiedfortheironsiteverification.
