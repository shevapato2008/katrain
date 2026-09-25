export const jobLabels: Record<string, string> = {
  poll_moves: '落子轮询', analyze: '直播分析', report_analyze: '复盘分析',
  fetch_upcoming: '赛事预告', fetch_list: '赛事列表', poll_pandanet: 'Pandanet 对局',
  translate: '棋手译名', tutorial_backup: '教程备份', cleanup: '数据清理',
};

// Stable purpose, verified against katrain/cron/jobs; health and cadence still come from the API.
export const jobDescriptions: Record<string, string> = {
  poll_moves: '检查直播对局的新落子，并为新增落子提交分析任务。',
  analyze: '持续领取直播分析任务，用 KataGo 计算并写回分析结果。',
  report_analyze: '持续领取用户复盘任务，用 cron 侧 KataGo 逐手分析棋局。',
  fetch_upcoming: '从已接入的赛事来源抓取预告，去重后更新即将开始的对局。',
  fetch_list: '从已启用的对局来源同步直播列表，并更新对局的完赛状态。',
  poll_pandanet: '扫描 Pandanet-IGS 职业对局，获取新落子并提交分析任务。',
  translate: '为直播和赛事预告中缺少译名的棋手、赛事补齐译名。',
  tutorial_backup: '定期导出教程相关数据表的压缩 JSON 快照，并清理过期快照。',
  cleanup: '定期清理过期对局、孤立分析结果、已过期赛事预告和旧 cron 运行记录。',
};
