"""把缺少某个字段的旧报告重新排队，让 cron 重跑一遍分析。

起因是「人类倾向」：`human_prior` 存在 `report_task_moves.top_moves` 这个 JSON 列里，
**旧报告补不出来** —— 那个数只有引擎能给，没有任何办法从已存字段推导。所以要么让老报告
永远空着，要么重跑。

**跑之前必须先确认两件事**，否则等于白删一遍数据：
  1. **新的 web 镜像已经上线**。人类倾向那一列在前端 bundle 里，而 bundle 只在
     Dockerfile.web 里产出。只发 cron 的话，重跑完数据是有的，屏幕上什么都不会变。
  2. `CRON_HUMAN_SL_PROFILE` 配好了（本模块开头会拦一道）。

用法（在 cron 容器里）：

    python -m katrain.cron.jobs.requeue_reports                # 只报告，不写库
    python -m katrain.cron.jobs.requeue_reports --commit       # 真的重排
    python -m katrain.cron.jobs.requeue_reports --commit --limit 5

重排会保留原来的 ``created_at``（那承载「报告什么时候要的」这个事实，不该改），
而 cron 是按 ``created_at`` 升序认领的 —— 所以一次性重排全部会**排在**迁移窗口内
用户新点的报告前面。用 ``--limit`` 分批、挑低峰跑。

**这个脚本会删掉被重排任务的 move 行。** 不删不行：`_get_resume_move_number` 是按
`max(move_number)+1` 续跑的，行留着就等于「已经跑完了」，重排也不会重算。代价是重跑期间
那几份报告在用户那里是残缺的 —— 所以默认不写库，必须显式 `--commit`。

只 import katrain.cron.* —— Dockerfile.cron 只 COPY 了这一个子目录，跨目录 import
在本仓永远是绿的、只在容器里炸。
"""

import argparse
import logging
import sys

from katrain.cron import config
from katrain.cron.db import SessionLocal
from katrain.cron.models import ReportTaskDB, ReportTaskMoveDB

logger = logging.getLogger("katrain_cron.requeue_reports")

def _task_has_human_prior(db, task_id: int) -> bool | None:
    """True=全都有；False=有一行没有；None=判不了（这份报告一行候选表都没有）。

    **不取样，从最早的手看起。** 原来的写法取最新 5 行 —— 方向正好反了：续跑是按
    ``max(move_number)+1`` 往后接的，所以一份「跑到一半改了配置」的报告恰好是**新的
    行有、老的行没有**，取最新几行会把它判成「已经有了」，那前 120 手就永久缺列且
    再跑多少遍也修不回来。整个生产库才 2944 行，逐行看没有任何成本。
    """
    rows = (
        db.query(ReportTaskMoveDB)
        .filter(ReportTaskMoveDB.task_id == task_id)
        .order_by(ReportTaskMoveDB.move_number.asc())
        .all()
    )
    checked = 0
    for row in rows:
        candidates = row.top_moves or []
        if not candidates:
            continue
        checked += 1
        if not any(c.get("human_prior") is not None for c in candidates if isinstance(c, dict)):
            return False
    return True if checked else None


def requeue(commit: bool = False, limit: int | None = None) -> dict[str, int]:
    # 没配 profile 的话重跑出来还是没有人类倾向 —— 白删一遍数据、白烧一轮 GPU。
    if not config.HUMAN_SL_PROFILE:
        raise SystemExit(
            "CRON_HUMAN_SL_PROFILE 是空的：重跑出来仍然不会有人类倾向。先配好再来。"
        )

    stats = {"completed": 0, "already_has": 0, "no_candidates": 0, "requeued": 0, "rows_deleted": 0}

    with SessionLocal() as db:
        tasks = (
            db.query(ReportTaskDB)
            .filter(ReportTaskDB.status == "completed")
            .order_by(ReportTaskDB.id.asc())
            .all()
        )
        stats["completed"] = len(tasks)

        for task in tasks:
            if limit is not None and stats["requeued"] >= limit:
                break

            has = _task_has_human_prior(db, task.id)
            if has is True:
                stats["already_has"] += 1
                continue
            if has is None:
                # 一行候选表都没有的报告本来就是坏的，重排它不会变好，交给人看。
                stats["no_candidates"] += 1
                logger.warning("Task %d has no stored candidates at all; skipping", task.id)
                continue

            row_count = (
                db.query(ReportTaskMoveDB).filter(ReportTaskMoveDB.task_id == task.id).count()
            )
            stats["requeued"] += 1
            stats["rows_deleted"] += row_count
            logger.info(
                "%s task %d (game %s): delete %d move rows and re-queue",
                "REQUEUE" if commit else "WOULD REQUEUE",
                task.id,
                task.user_game_id,
                row_count,
            )

            if commit:
                db.query(ReportTaskMoveDB).filter(ReportTaskMoveDB.task_id == task.id).delete(
                    synchronize_session=False
                )
                task.status = "pending"
                task.analyzed_moves = 0
                task.completed_at = None
                task.started_at = None
                task.error_message = None
                task.retry_count = 0

        if commit:
            db.commit()
        else:
            db.rollback()

    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true", help="真的写库（默认只报告）")
    parser.add_argument("--limit", type=int, default=None, help="最多重排几份")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    stats = requeue(commit=args.commit, limit=args.limit)

    print(
        f"completed={stats['completed']} "
        f"already_has_human_prior={stats['already_has']} "
        f"no_candidates={stats['no_candidates']} "
        f"requeued={stats['requeued']} "
        f"rows_deleted={stats['rows_deleted']}"
    )
    if not args.commit and stats["requeued"]:
        print("（这是空跑，什么都没写。要真的重排，加 --commit）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
