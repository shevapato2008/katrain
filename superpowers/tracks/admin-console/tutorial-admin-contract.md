# 教程管理数据契约（本地实现基准）

状态：2026-09-24 Galaxy 风格新版四图获 Fan 确认后冻结首版范围。本契约只授权本地实现；不授权远程连接、真实写库、push 或部署。

## 身份和读取

- 后台是独立进程与站点。`POST /api/admin/auth/login` 接收 `{username,password}`，返回 `{access_token,token_type:"bearer"}`；`GET /api/admin/auth/me` 返回后台身份，`POST /api/admin/auth/logout` 用于结束当前前端会话。后台令牌只发往 `/api/admin/*`，不被公开 Galaxy API 接受。
- 书、章、节、图、原书页和音视频沿用现有只读 `/api/v1/tutorials/*` 与 `TutorialFigureOut`，在后台进程上同源挂载。分类/书/章/节/图 ID 都是数据库整数，不沿用 Fixture 的字符串 ID。只有当前环境真实数据能作为正式运行时内容。
- 展示字段以既有 `TutorialFigureOut` 为准：`id`、`section_id`、`page`、`figure_label`、`book_text`、`page_context_text`、`page_image_path`、`board_payload`、`recognition_debug`、`narration`、`audio_asset`、`video_asset`、`updated_at` 等。加载失败显示错误与重试；不存在则 404；不得以 Fixture 顶替。

## 后台写入

| 路径 | 请求体 | 成功响应 | 作用 |
| --- | --- | --- | --- |
| `PUT /api/admin/tutorials/figures/{id}/board` | `{board_payload,expected_updated_at,narration?}` | `TutorialFigureOut` | 保存棋图；`narration` 仅在传入时与棋图同事务保存 |
| `PUT /api/admin/tutorials/figures/{id}/narration` | `{narration,expected_updated_at}` | `TutorialFigureOut` | 只保存讲解文字 |
| `POST /api/admin/tutorials/figures/{id}/generate-audio` | `{narration,expected_updated_at}` | `TutorialFigureOut` | 生成并绑定新语音；失败不能先保存讲解或假报成功 |
| `PUT /api/admin/tutorials/figures/{id}/verify` | `{expected_updated_at}` | `{figure:TutorialFigureOut,training_export:{status,count,reason?}}` | 审核当前棋图，明确呈现训练样本导出结果 |

- 全部写请求必须带后台 Bearer；缺失/无效为 401。`expected_updated_at` 是必传的 ISO 时间字符串；仅当数据库原值确为 `NULL` 时可传 `null`。缺字段/非法值为 422；版本不一致为 409，前端保留草稿并引导刷新。刷新后只合并服务端对草稿未编辑字段的更改；同字段双方都修改时，必须显式核对并确认覆盖，不能以整份旧草稿悄悄覆盖服务器版本。不存在的图为 404。后端以条件更新完成版本比较，而非先读再比后无条件写入；每次成功更新产生严格递增 UTC `updated_at`。
- `board_payload` 使用现有严格棋盘校验与服务端 viewport 计算。无棋盘图只编辑讲解时不得顺带创建空棋盘；显式选择“编辑棋图”才可初始化空盘。棋图编辑撤销审核标记，并清掉属于旧棋图的训练样本。棋图、讲解或语音改变时清掉旧视频引用及其时长、大小；讲解文字改变还使旧语音引用失效。视频不自动重做，以免把旧内容显示成当前成品；不动棋图审核。不能由客户端提供媒体路径、`changed_by`、`verified_by` 或审核标记。
- 后台服务端以 `realm=admin`、后台用户名写 `admin_audit_log`；棋图历史的可读署名是 `admin:fan`。棋图/文字/审核、历史和审计必须同一数据库事务提交；审计失败整体回滚。审核的训练样本若无法导出，响应必须诚实说明 `skipped` 或 `failed`，不能默默显示已导出；重试时不得保留与新棋图不符的旧样本。
- TTS 在版本预检后先生成临时文件，再上传独立版本化对象键；生成或上传失败返回明确错误，数据库不变。仅上传成功后用版本条件更新绑定讲解与音频路径；若期间发生冲突则 409，未引用的对象可留待清理。不得复用旧的“先提交讲解、后生成、再提交音频”的公共路径。

## 集成边界

- 正式前端仅用真实请求，401 清除后台会话并允许重登，409 保留未保存草稿；成功返回后重新呈现音视频状态。删除 `src/admin/fixtures/**` 及生产代码中的演示业务数据是完成条件。
- 撤挂公开教程四个写接口、旧设备列表和两项计费管理员接口属于集成步骤，不能在后台写入可用前制造额外编辑断档。公开教程读取及资产保持可用。
- 后台不调用公开 `create_app()` 或自行初始化数据库表。所需审计表由公开 web 的既有 schema 初始化路径建好；表缺失要给出明确不可用错误，不能把已做业务写入伪装成成功。生产全表替换式教程同步上线前须停用或调整，并备份核差，避免覆盖后台编辑。
