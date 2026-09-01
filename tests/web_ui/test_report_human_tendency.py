"""人类倾向（KataGo human SL）在报告链路上的落地。

覆盖三件事：
  1. cron 的 KataGo 客户端能把 overrideSettings 塞进去，且不吃掉原有的默认键；
  2. 报告分析会把 humanPrior **连同它是哪一档**一起存进 top_moves，引擎没给时存 None
     而不是 0（0 的意思是「没人会下」，和「没有这个数」不是一回事）；
  3. 配置里把 profile 清空 = 一键关掉这个特性（引擎没加载人类模型时设了 profile 会让
     整条 query 失败，所以这个开关必须真的能关）。
"""

import pytest
import respx
from httpx import Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, patch

from katrain.cron.clients.katago import KataGoClient
from katrain.cron.sgf import parse_game
from katrain.web.core import models_db


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    models_db.Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


def _response(with_human: bool) -> dict:
    move_info = {
        "move": "Q16",
        "visits": 500,
        "winrate": 0.52,
        "scoreLead": 1.5,
        "prior": 0.2,
        "pv": ["Q16"],
        "playSelectionValue": 0.73,
    }
    if with_human:
        move_info["humanPrior"] = 0.2253
    return {
        "rootInfo": {"scoreLead": 1.0, "winrate": 0.51, "visits": 500},
        "moveInfos": [move_info],
        "ownership": [0.0] * (19 * 19),
    }


# ── 1. 客户端 ──


@pytest.mark.asyncio
@respx.mock
async def test_extra_override_is_merged_without_dropping_defaults():
    route = respx.post("http://katago:8002/analyze").mock(return_value=Response(200, json={"id": "x"}))
    client = KataGoClient(base_url="http://katago:8002")

    await client.analyze(
        request_id="x",
        moves=[["B", "Q16"]],
        extra_override={"humanSLProfile": "rank_5d", "rootNumSymmetriesToSample": 8},
    )

    payload = route.calls[0].request.read()
    import json

    override = json.loads(payload)["overrideSettings"]
    assert override["humanSLProfile"] == "rank_5d"
    assert override["rootNumSymmetriesToSample"] == 8
    # 原有的默认键不能被顶掉：胜率口径变了整份报告的正负号都会翻。
    assert override["reportAnalysisWinratesAs"] == "BLACK"


@pytest.mark.asyncio
@respx.mock
async def test_without_extra_override_payload_is_unchanged():
    route = respx.post("http://katago:8002/analyze").mock(return_value=Response(200, json={"id": "x"}))
    client = KataGoClient(base_url="http://katago:8002")

    await client.analyze(request_id="x", moves=[["B", "Q16"]])

    import json

    override = json.loads(route.calls[0].request.read())["overrideSettings"]
    assert override == {"reportAnalysisWinratesAs": "BLACK"}


# ── 2 & 3. 分析落库 ──


async def _run_analyze(profile: str, with_human: bool):
    SessionLocal = _make_session()
    from katrain.cron.jobs import report_analyze

    parsed = parse_game("(;FF[4]SZ[19];B[pd];W[dp])")
    job = report_analyze.ReportAnalyzerJob()
    job._katago = AsyncMock()
    job._katago.analyze = AsyncMock(return_value=_response(with_human))

    with patch.object(report_analyze.config, "HUMAN_SL_PROFILE", profile), patch.object(
        report_analyze.config, "HUMAN_SL_SYMMETRIES", 8
    ), patch.object(report_analyze, "SessionLocal", lambda: SessionLocal()):
        result = await job._analyze_position(task_id=1, parsed=parsed, move_number=1, requested_visits=500)

    return result, job._katago.analyze.call_args.kwargs


@pytest.mark.asyncio
async def test_human_prior_is_stored_together_with_its_profile():
    result, kwargs = await _run_analyze("rank_5d", with_human=True)

    assert kwargs["extra_override"] == {"humanSLProfile": "rank_5d", "rootNumSymmetriesToSample": 8}
    # 只要 moveInfos[].humanPrior，不需要 includePolicy（那是全盘数组的开关）。
    assert kwargs["include_policy"] is False

    top = result["top_moves"][0]
    assert top["human_prior"] == pytest.approx(0.2253)
    # 一个概率不说清是哪一档人给的就没有意义 —— 换档之后老报告还要能自证。
    assert top["human_profile"] == "rank_5d"


@pytest.mark.asyncio
async def test_missing_human_prior_stores_none_not_zero():
    result, _ = await _run_analyze("rank_5d", with_human=False)

    top = result["top_moves"][0]
    assert top["human_prior"] is None
    # 0 会被读成「没人会下」；「没有这个数」必须是 None，界面才能显示成「—」。
    assert top["human_prior"] != 0
    assert top["human_profile"] is None


@pytest.mark.asyncio
async def test_empty_profile_is_a_real_kill_switch():
    result, kwargs = await _run_analyze("", with_human=True)

    # 引擎没加载人类模型时，设了 profile 会让**整条 query 失败**（不是静默降级），
    # 所以清空配置必须真的不发这个键。
    assert kwargs["extra_override"] is None
    assert result["top_moves"][0]["human_profile"] is None


@pytest.mark.asyncio
async def test_engine_error_in_a_200_response_is_treated_as_failure():
    """:8002 的包装器用 HTTP 200 + {"error"} 表达拒绝，raise_for_status() 放行。

    不拦的话 rootInfo 缺失被 .get 兜成 {} ⇒ 落库 50% 平线 + 零候选，任务还被标 completed。
    """
    SessionLocal = _make_session()
    from katrain.cron.jobs import report_analyze

    parsed = parse_game("(;FF[4]SZ[19];B[pd];W[dp])")
    job = report_analyze.ReportAnalyzerJob()
    job._katago = AsyncMock()
    job._katago.analyze = AsyncMock(
        return_value={"error": "Could not set settings: Unknown human SL network profile: rank_10d",
                      "field": "overrideSettings", "id": "x"}
    )

    with patch.object(report_analyze.config, "HUMAN_SL_PROFILE", "rank_10d"), patch.object(
        report_analyze, "SessionLocal", lambda: SessionLocal()
    ):
        result = await job._analyze_position(task_id=1, parsed=parsed, move_number=1, requested_visits=500)

    # None ⇒ 走已有的重试/标失败路径；绝不能返回一份 winrate=0.5 的“成功”结果。
    assert result is None


# ── 4. 旧报告重跑 ──


def _seed_report(SessionLocal, *, human: bool, rows: int = 3, candidates: bool = True):
    """建一份 completed 报告；human=True 表示它的候选表里已经有 human_prior。"""
    with SessionLocal() as session:
        # 用户名要在同一个库里唯一：同一测试可能连建几份报告。
        seq = session.query(models_db.User).count()
        user = models_db.User(username=f"seed-{seq}", hashed_password="x")
        session.add(user)
        session.commit()
        session.refresh(user)
        game = models_db.UserGame(user_id=user.id, sgf_content="(;FF[4]SZ[19];B[pd])", source="import", move_count=1)
        session.add(game)
        session.commit()
        session.refresh(game)
        task = models_db.ReportTask(
            user_id=user.id,
            user_game_id=game.id,
            report_type="normal",
            requested_visits=500,
            status="completed",
            total_moves=rows,
            analyzed_moves=rows,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        for n in range(rows):
            top = (
                [{"move": "Q16", "prior": 0.2, "human_prior": 0.22 if human else None,
                  "human_profile": "rank_5d" if human else None}]
                if candidates
                else []
            )
            session.add(models_db.ReportTaskMove(task_id=task.id, move_number=n, top_moves=top))
        session.commit()
        return task.id


def _requeue(SessionLocal, **kwargs):
    """跑 requeue，并**显式**把 profile 设成一个合法档。

    2026-09-01 起 `config.HUMAN_SL_PROFILE` 的默认值是空串（Fan 裁定这一列先不上），
    而 `requeue()` 的第一件事就是「profile 为空就 SystemExit」—— 那条守卫是对的：
    没配档位时重跑出来仍然没有人类倾向，白删数据白烧 GPU。
    这几个用例测的是**重排机制**（选哪些报告、删不删行、limit 生效没有），
    不是默认值，所以在这里把档位钉死，别让它跟着默认值漂。
    默认值本身由 `test_requeue_refuses_when_profile_is_empty` 那条守着。
    """
    from katrain.cron.jobs import requeue_reports

    with patch.object(requeue_reports, "SessionLocal", lambda: SessionLocal()), patch.object(
        requeue_reports.config, "HUMAN_SL_PROFILE", "rank_5d"
    ):
        return requeue_reports.requeue(**kwargs)


def test_requeue_refuses_when_profile_is_empty():
    """profile 没配就必须拒绝，而不是删完 move 行再重跑出一份同样没有人类倾向的报告。

    2026-09-01 起这是**默认走的分支**（`HUMAN_SL_PROFILE` 默认空串），所以它比另一支
    更需要被守住：一旦有人把这条守卫删了，生产上任何一次 requeue 都会白删几千行。
    变异验证：把 `requeue_reports.py` 里的 `if not config.HUMAN_SL_PROFILE:` 改成
    `if False:`，这条会红（stats 正常返回而不是 SystemExit）。
    """
    SessionLocal = _make_session()
    stale = _seed_report(SessionLocal, human=False)

    from katrain.cron.jobs import requeue_reports

    with patch.object(requeue_reports, "SessionLocal", lambda: SessionLocal()), patch.object(
        requeue_reports.config, "HUMAN_SL_PROFILE", ""
    ):
        with pytest.raises(SystemExit):
            requeue_reports.requeue(commit=True)

    with SessionLocal() as session:
        # 拒绝必须是**在动数据之前**拒绝。
        assert session.query(models_db.ReportTaskMove).filter_by(task_id=stale).count() == 3
        assert session.get(models_db.ReportTask, stale).status == "completed"


def test_human_sl_is_off_by_default():
    """默认关闭。Fan 2026-09-01 裁定人类倾向先不上，代价不只是多一列 ——
    开着它每一手都要多做 8 次根节点对称采样（`HUMAN_SL_SYMMETRIES`）。
    这条钉住默认值本身，免得有人「顺手」把它改回 rank_5d 而没人发现。
    """
    import importlib

    from katrain.cron import config as cron_config

    reloaded = importlib.reload(cron_config)
    assert reloaded.HUMAN_SL_PROFILE == ""


def test_requeue_dry_run_writes_nothing():
    SessionLocal = _make_session()
    stale = _seed_report(SessionLocal, human=False)
    fresh = _seed_report(SessionLocal, human=True)

    stats = _requeue(SessionLocal)

    assert stats["requeued"] == 1
    assert stats["already_has"] == 1
    with SessionLocal() as session:
        # 空跑必须真的什么都没动 —— 这个脚本会删 move 行，删错了要重跑整份报告。
        assert session.get(models_db.ReportTask, stale).status == "completed"
        assert session.query(models_db.ReportTaskMove).filter_by(task_id=stale).count() == 3
        assert session.get(models_db.ReportTask, fresh).status == "completed"


def test_requeue_commit_deletes_rows_and_resets_only_the_stale_one():
    SessionLocal = _make_session()
    stale = _seed_report(SessionLocal, human=False)
    fresh = _seed_report(SessionLocal, human=True)

    stats = _requeue(SessionLocal, commit=True)

    assert stats["requeued"] == 1
    assert stats["rows_deleted"] == 3
    with SessionLocal() as session:
        task = session.get(models_db.ReportTask, stale)
        assert task.status == "pending"
        assert task.analyzed_moves == 0
        assert task.completed_at is None
        # 必须把 move 行删掉：续跑点是 max(move_number)+1，行留着就等于「已经跑完了」。
        assert session.query(models_db.ReportTaskMove).filter_by(task_id=stale).count() == 0

        untouched = session.get(models_db.ReportTask, fresh)
        assert untouched.status == "completed"
        assert session.query(models_db.ReportTaskMove).filter_by(task_id=fresh).count() == 3


def test_requeue_skips_reports_that_have_no_candidates_at_all():
    SessionLocal = _make_session()
    broken = _seed_report(SessionLocal, human=False, candidates=False)

    stats = _requeue(SessionLocal, commit=True)

    # 一行候选表都没有的报告本来就是坏的，重排它不会变好；而且「没有候选表」不能
    # 当成「缺人类倾向」的证据，否则会把好报告也一起重排掉。
    assert stats["no_candidates"] == 1
    assert stats["requeued"] == 0
    with SessionLocal() as session:
        assert session.get(models_db.ReportTask, broken).status == "completed"


def test_requeue_respects_limit():
    SessionLocal = _make_session()
    for _ in range(3):
        _seed_report(SessionLocal, human=False, rows=2)

    stats = _requeue(SessionLocal, commit=True, limit=2)

    assert stats["requeued"] == 2
    with SessionLocal() as session:
        assert session.query(models_db.ReportTask).filter_by(status="pending").count() == 2


def test_requeue_catches_a_report_that_only_has_human_prior_on_later_moves():
    """续跑是按 max(move_number)+1 往后接的 —— 半途开启人类倾向的报告是**新行有、老行没有**。

    原来按 move_number.desc() 取最新 5 行判断，正好把这种报告判成「已经有了」，
    前面那一百多手就永久缺列且再跑多少遍也修不回来。
    """
    SessionLocal = _make_session()
    with SessionLocal() as session:
        user = models_db.User(username="half-done", hashed_password="x")
        session.add(user); session.commit(); session.refresh(user)
        game = models_db.UserGame(user_id=user.id, sgf_content="(;FF[4]SZ[19];B[pd])", source="import", move_count=10)
        session.add(game); session.commit(); session.refresh(game)
        task = models_db.ReportTask(
            user_id=user.id, user_game_id=game.id, report_type="normal",
            requested_visits=500, status="completed", total_moves=10, analyzed_moves=10,
        )
        session.add(task); session.commit(); session.refresh(task)
        for n in range(10):
            has = n >= 6  # 后 4 手才有
            session.add(models_db.ReportTaskMove(
                task_id=task.id, move_number=n,
                top_moves=[{"move": "Q16", "prior": 0.2,
                            "human_prior": 0.2 if has else None,
                            "human_profile": "rank_5d" if has else None}],
            ))
        session.commit()
        task_id = task.id

    stats = _requeue(SessionLocal, commit=True)

    assert stats["requeued"] == 1, "半途才有人类倾向的报告必须被重排"
    assert stats["already_has"] == 0
    with SessionLocal() as session:
        assert session.get(models_db.ReportTask, task_id).status == "pending"
