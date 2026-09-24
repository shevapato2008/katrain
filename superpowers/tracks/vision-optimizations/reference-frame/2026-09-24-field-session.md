# 参考帧上板实测与三处修复（2026-09-24）

现场：RK3562 `gzpeite`，Fan 连下三局自由对弈。全部结论有日志取证，日志留在板上
`/root/monitor/game.log`，并可从 journal 复查。

## 0. 一句话

参考帧比对（refcheck）**写好之后从未真正生效过**——默认 `shadow`（只记录不拦截），板上从没
配过开关。打开之后又发现它被三条路架空，今天修掉两条半。

## 1. 假阳性其实是两族，判别轴不同

| | **静止类（反光）** | **手/影类** |
|---|---|---|
| 样本 | `(18,12)` 两局复现、`(2,2)` | `(14,1)@0.32` `(12,10)@0.37` `(9,11)@0.38` `(13,13)@0.41` |
| 置信度 | 0.30–0.55 | 0.41–0.59 |
| 偏离交点 | 小 | **≥0.32** |
| 参考帧 zncc | **0.97–1.00（像素没变）** | 低（手真的在那儿） |
| refcheck | ✅ 能拦 | ❌ 结构上够不着 |

真子实测 **19 颗：置信度 0.46–0.88，偏离交点 0.01–0.21**。

**⚠️ 置信度不是可用的判别轴**：`(16,15)W conf=0.46` 是**真子**，比两个假阳性（0.55、0.59）
还低。按 0.60 切会当场杀掉它。Fan 的裁定（不调阈值，"0.50 的假阳性说明模型对反光判别力不够"）
有这条反例支撑。**偏离交点**那根轴在 0.21→0.32 之间有一条空缝（24 个样本无一落入），未使用。

## 2. 今天修掉的三条（参考帧被架空的路径）

1. **默认 shadow**（`d63d99ffb`，smartbox provision）：`reference_check` 默认 `shadow`，板上
   从未配置 ⇒ 认出假阳性也只打日志。改成 `on`。**手改板上会被 provision 冲掉,必须落在
   `provisioning/systemd/smartbox-katrain.service.d/20-vision-led.conf`。**
2. **记账理由销毁参考帧**（`9f8561ec`）：一局销毁 12 次、**全是 `paused`**，而实体对弈每落一手
   编排器都会暂停 ⇒ 否决绝大部分时间不可用。Fan 定的原则：**照到新的参考帧才允许销毁旧的；
   拍新参考失败也不许丢掉旧的**。`paused` / 「不再领先一手」/ 帧尺寸变 / 比对抛异常四处全改。
   留着不会误否决：否决要同时满足「像素没变」与「检测≠参考」，像素没变 ⇒ 物理状态与拍参考
   那刻相同 ⇒ 参考里那个读数就是这堆像素的正确解读。
3. **低置信度提升器绕过否决**（本次）：`_promote_stuck_stone` 的候选过滤不问参考帧 ⇒
   refcheck 以 `zncc=1.00` 连否 7 帧的同时，一个 **conf=0.33** 的检测被提升进盘面并弹窗。
   病根在 `AmbiguousPromoter` 的 docstring：*"a real stone persists frame after frame,
   while glare/noise flickers"* —— **这个假设对镜面反光不成立**：固定棋盘+固定灯光下反光
   纹丝不动，比真子更容易满足「连续 12 帧」。修法：候选排除参考帧正在否决的格
   （`_ref_disagree` 逐格掩码；`_reference_check` 在同一帧内先于提升器运行，非陈旧）。

### 修复前后（同等时长一局）

| | 修复前 | 修复后 |
|---|---|---|
| 参考帧销毁 | 12（全 `paused`） | **0** |
| 假阳性最长驻留 | **96 秒** | ~1.3 秒，自愈 |
| 拦下假阳性 | 0（shadow） | **7 格次** |
| **救回漏检的子** | 0 | **14 格次**（zncc 多为 1.00） |

**意外收获：它救回的比拦下的多一倍。** 参考帧在这块板上最大的价值不是挡假阳性，而是
按像素证据补检测器的漏检。

## 3. 排期（Fan 2026-09-24 批准）

### 3.1 「不是落子」+ 用户否认样本的 ZNCC 比对 —— **已批准，下次开工**

出处：`superpowers/tracks/vision-optimizations/shadow-dedup/design.md:92`，原文含
「「不是落子」按钮 **+ 用户否认样本的 ZNCC 比对**」，当时定「另起切片，先出 mockup 给 Fan 确认」，
mockup 从未做 ⇒ 切片未开工，按钮至今仍是 `msgid "Ignore"` →「忽略」。

**比原估计便宜得多**：`ambiguous_stone` → `AmbiguousMoveCard` 这张确认卡**已经存在**，
「拒绝 → 120 帧冷却」（`AmbiguousPromoter.cooldown_frames`）也已经在跑。缺的只有：
- 按钮文案 `Ignore` → 「不是落子」（11 语种）
- **把用户否认的那一帧存下来做 ZNCC 比对**，让该位置以后不再被认成子（这是真正的新功能）

### 3.2 `move_pending` 对称化

`move confirmed` 要求 5 帧稳定，**而 `move_pending` 一出现就发**。今天两次 `illegal_change`
弹窗都是这个不对称造成的：假子先占了 pending 的位置，真子进来就成了「非法变化」。
最终落子都是对的（`Vision move submitted` 正确），只是弹了不该弹的窗。

### 3.3 标定固定 255（Fan 的分法）

Fan：「标定阶段用固定 255，目的是把棋盘网格标准确；开局以后再用可调节亮度，目的是别把白棋
照透影响 YOLO 识别」。现状 `FLASH_LEVELS = (96, 255)`，先 96 失败再升 255。
09-24 下午场景亮（曝光锁 median 156）⇒ 13 个锚点里 **6 个** @96 测不到（peak 0–6），
退回全画幅兜底才救回（peak 153–195）。**上午同一块板是 13 个全过、0 次兜底**（median 135）。
注：`ROI_FALLBACK_WARN_MIN = 7`，我们踩到 6，**正好压在报警线下没响**。

**已落地**：`FLASH_LEVELS = (255,)` —— 暗档取消，一颗锚点只闪一次（用户看到的
「13 个点亮 2 下」就是旧的两档阶梯）。当初留 96 的理由是「暗处拉满会削顶把质心拉偏」，
那句话没有实测；而「白天一半锚点测不到」是实测。

### 3.4 参照帧三处缺口（原 design.md §6，触发条件已满足）

原文：「参照帧的三处缺口（按格拍参照、**否决上限**、低于门槛路径）：**去影子落地后看残余弹窗
再定**」。去影子已于 09-23 落地（`ddedbf9b`），残余弹窗证据今天已齐 ⇒ **这条「再定」现在可以定**。
今天实测到的预算：`REFERENCE_HOLD_SUPPRESS=10`（压假阳性）/ `REFERENCE_HOLD_KEEP=90`（救漏检）。

## 4. 复查命令

```sh
ssh rk3562-direct 'R=$(systemctl show smartbox-katrain -p ActiveEnterTimestamp --value)
L=$(journalctl -u smartbox-katrain --since "$R" --no-pager)
echo "$L" | grep -c "refcheck keeps"
echo "$L" | grep -oE "reference dropped: .*" | sort | uniq -c   # 期望为空
echo "$L" | grep -c illegal_change'
```

**在跑的进程是不是真的开着否决**（provision 装完 drop-in 只 `daemon-reload`，不重启 ⇒
磁盘上是 `on` 不代表进程是 `on`）：

```sh
ps aux | grep "[k]atrain.web.server" | grep -o "\-\-vision-reference-check [a-z]*"
```
