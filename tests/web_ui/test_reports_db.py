from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db


def test_report_task_relationships():
    engine = create_engine("sqlite:///:memory:")
    models_db.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    session = SessionLocal()
    try:
        user = models_db.User(username="reportuser", hashed_password="fakehash")
        session.add(user)
        session.commit()
        session.refresh(user)

        game = models_db.UserGame(
            user_id=user.id,
            sgf_content="(;FF[4]SZ[19];B[pd];W[dp])",
            source="import",
            move_count=2,
        )
        session.add(game)
        session.commit()
        session.refresh(game)

        task = models_db.ReportTask(
            user_id=user.id,
            user_game_id=game.id,
            report_type="normal",
            requested_visits=500,
            status="pending",
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        move = models_db.ReportTaskMove(
            task_id=task.id,
            move_number=1,
            status="success",
            winrate=0.52,
            score_lead=1.5,
            visits=500,
            top_moves=[{"move": "Q16", "visits": 500}],
        )
        session.add(move)
        session.commit()
        session.refresh(move)

        loaded_task = session.query(models_db.ReportTask).filter_by(id=task.id).one()
        assert loaded_task.user_game_id == game.id
        assert loaded_task.user_game.id == game.id
        assert len(loaded_task.moves) == 1
        assert loaded_task.moves[0].move_number == 1
        assert loaded_task.moves[0].task.id == task.id
        assert game.report_tasks[0].id == task.id
    finally:
        session.close()
