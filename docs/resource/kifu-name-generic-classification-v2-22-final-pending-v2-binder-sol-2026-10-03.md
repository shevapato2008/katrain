# classification-v2 22 格：create allowlist 修订，最终候选仍 PENDING

绑定者 `/root/generic_v2_22_binder_sol`，运行时 GPT-6，任务名不认证具体子型号。原 create 多余字段是本次包错误，已在新受控目录 `/Users/fan/.local/share/kifu-name-audit/2026-10-03/generic-classification-v2-22-final-pending-v2-binder-sol` 修正；旧 producer、binder 和独立已签/HOLD 工件未修改。

两项 `create.parser_version` 已删除，create 恰为 `raw_value/category`；候选 `generation_rule_version=classification-v2`、22 个精确字面值、source author/model/produced_at 和 source_candidate hashes 保留。owner_set 和 bundle hash 重新计算，完整 scope/member/link hashes 实际重算；scope 仍段位赛901/个人赛638，与历史独立核对完全一致。历史类别/模板签署只作依赖，未移植旧最终候选批准，22 条最终仍 pending。

校验固定于独立 worktree `.worktrees/generic-v2-22-binder-b0cdbdcf`，HEAD `b0cdbdcfacda23391cf39273c42e067f3fc11b79`；三个协议实现文件与 `e8110c24` 完全相同，模块字节 hash 在 binding-result 中。只连接隔离克隆 `127.0.0.1:55433/kifu_raw31_clone_20261003`，强制 `REPEATABLE READ READ ONLY`；最新 capture `2026-10-02T23:14:00.440023+00:00`，重新绑定 `2026-10-02T23:14:00.726247+00:00`，两精确 owner 仍不存在，十一语名称均 NULL。inventory/catalog hash 不变，不冒称新生产快照。

固定版本实际 importer `_check_owner_manifest` 和 `_check_name_preimages` 均 PASS：两个 create 字段被接受，22 条真实前像一致。未运行完整 importer dry-run，因为 pending 需独立签署先行。既有 CLI 实际 exit1，`pending=22, approved=0, missing=0, rejected=0, write_errors=[]`；四个错误仅为两 owner 的完整十一语批准/对应批准 display 门槛，`ready=false/write_ready=false`。

修订 bundle 规范 hash `4fa682951e001cdc16e37024e04140df9dc21f1a29e0337801e275d3e038f98f`，字节 hash `410b20a3b71d124f871f32ad8ef877a98ea32e28e92d1718f913c55affd7d26d`；capture 字节 hash `6089bc08ae50d157900cc13abd7fc8a750e00cb29b04016c8c585e48b55760c1`。独立 Sol 须重新核对当前 create 修订、scope/capture/hash/时序并签署全部22条；reviewed_at 不得早于新 bound_at。若继续采用原 template_review，reviewer须与 `/root/generic_v2_22_source_review_sol` 的真实签署标识/模型一致，或另作实际模板签署。之后再走既有 validator 和隔离完整 dry-run/授权演练。

隔离 clone 已停止；本次数据库写入0，生产/现役测试库连接0，应用代码修改0、提交0。未扩张 importer allowlist。旧最终22签署的 PASS/dry-run HOLD 历史保留，不能充当本修订批准。
