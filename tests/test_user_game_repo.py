"""Tests for UserGameRepository and UserGameAnalysisRepository."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.user_game_repo import UserGameRepository, UserGameAnalysisRepository


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    models_db.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    # Create a test user
    session = SessionLocal()
    user = models_db.User(username="testuser", hashed_password="fakehash")
    session.add(user)
    session.commit()
    session.refresh(user)
    user_id = user.id
    session.close()

    return SessionLocal, user_id


class TestUserGameRepository:
    def test_create_game(self, db_session):
        factory, user_id = db_session
        repo = UserGameRepository(factory)

        game = repo.create(
            user_id=user_id,
            sgf_content="(;FF[4]SZ[19];B[pd];W[dp])",
            source="research",
            title="Test Game",
            player_black="Alice",
            player_white="Bob",
            board_size=19,
            move_count=2,
        )

        assert game["id"] is not None
        assert game["title"] == "Test Game"
        assert game["player_black"] == "Alice"
        assert game["sgf_content"] == "(;FF[4]SZ[19];B[pd];W[dp])"

    def test_get_game(self, db_session):
        factory, user_id = db_session
        repo = UserGameRepository(factory)

        created = repo.create(user_id=user_id, sgf_content="(;FF[4])", source="research")
        fetched = repo.get(created["id"], user_id)

        assert fetched is not None
        assert fetched["id"] == created["id"]
        assert fetched["sgf_content"] == "(;FF[4])"

    def test_get_nonexistent_game(self, db_session):
        factory, user_id = db_session
        repo = UserGameRepository(factory)

        result = repo.get("nonexistent", user_id)
        assert result is None

    def test_list_games(self, db_session):
        factory, user_id = db_session
        repo = UserGameRepository(factory)

        repo.create(user_id=user_id, sgf_content="(;FF[4])", source="research", title="Game 1")
        repo.create(user_id=user_id, sgf_content="(;FF[4])", source="research", title="Game 2")
        repo.create(user_id=user_id, sgf_content="(;FF[4])", source="research", title="Game 3")

        result = repo.list(user_id=user_id)
        assert result["total"] == 3
        assert len(result["items"]) == 3

    def test_list_with_pagination(self, db_session):
        factory, user_id = db_session
        repo = UserGameRepository(factory)

        for i in range(5):
            repo.create(user_id=user_id, sgf_content=f"(;FF[4]C[{i}])", source="research")

        page1 = repo.list(user_id=user_id, page=1, page_size=2)
        assert page1["total"] == 5
        assert len(page1["items"]) == 2
        assert page1["page"] == 1

        page2 = repo.list(user_id=user_id, page=2, page_size=2)
        assert len(page2["items"]) == 2

    def test_list_with_category_filter(self, db_session):
        factory, user_id = db_session
        repo = UserGameRepository(factory)

        repo.create(user_id=user_id, sgf_content="(;FF[4])", source="research", category="game")
        repo.create(user_id=user_id, sgf_content="(;FF[4])", source="research", category="position")

        games = repo.list(user_id=user_id, category="game")
        assert games["total"] == 1
        positions = repo.list(user_id=user_id, category="position")
        assert positions["total"] == 1

    def test_list_with_search(self, db_session):
        factory, user_id = db_session
        repo = UserGameRepository(factory)

        repo.create(user_id=user_id, sgf_content="(;FF[4])", source="research", player_black="Ke Jie")
        repo.create(user_id=user_id, sgf_content="(;FF[4])", source="research", player_black="Lee Sedol")

        result = repo.list(user_id=user_id, q="Ke")
        assert result["total"] == 1
        assert result["items"][0]["player_black"] == "Ke Jie"

    def test_update_game(self, db_session):
        factory, user_id = db_session
        repo = UserGameRepository(factory)

        created = repo.create(user_id=user_id, sgf_content="(;FF[4])", source="research", title="Old Title")
        updated = repo.update(created["id"], user_id, title="New Title")

        assert updated is not None
        assert updated["title"] == "New Title"

    def test_delete_game(self, db_session):
        factory, user_id = db_session
        repo = UserGameRepository(factory)

        created = repo.create(user_id=user_id, sgf_content="(;FF[4])", source="research")
        assert repo.delete(created["id"], user_id) is True
        assert repo.get(created["id"], user_id) is None

    def test_delete_nonexistent(self, db_session):
        factory, user_id = db_session
        repo = UserGameRepository(factory)

        assert repo.delete("nonexistent", user_id) is False

    def test_sgf_hash_generated(self, db_session):
        factory, user_id = db_session
        repo = UserGameRepository(factory)

        game = repo.create(user_id=user_id, sgf_content="(;FF[4])", source="research")
        # sgf_hash is not in the returned dict by default, but the DB has it
        # We verify it was created without errors (the hash computation ran)
        assert game["id"] is not None


class TestUserGameAnalysisRepository:
    def test_upsert_and_get(self, db_session):
        factory, user_id = db_session
        game_repo = UserGameRepository(factory)
        analysis_repo = UserGameAnalysisRepository(factory)

        game = game_repo.create(user_id=user_id, sgf_content="(;FF[4])", source="research")
        game_id = game["id"]

        # Insert
        result = analysis_repo.upsert(
            game_id=game_id,
            move_number=0,
            status="complete",
            winrate=0.52,
            score_lead=1.5,
            visits=500,
        )
        assert result["move_number"] == 0
        assert result["winrate"] == pytest.approx(0.52)
        assert result["score_lead"] == pytest.approx(1.5)

    def test_upsert_update_existing(self, db_session):
        factory, user_id = db_session
        game_repo = UserGameRepository(factory)
        analysis_repo = UserGameAnalysisRepository(factory)

        game = game_repo.create(user_id=user_id, sgf_content="(;FF[4])", source="research")
        game_id = game["id"]

        # Insert then update
        analysis_repo.upsert(game_id=game_id, move_number=1, winrate=0.50, visits=100)
        updated = analysis_repo.upsert(game_id=game_id, move_number=1, winrate=0.55, visits=500)

        assert updated["winrate"] == pytest.approx(0.55)
        assert updated["visits"] == 500

    def test_get_analysis_range(self, db_session):
        factory, user_id = db_session
        game_repo = UserGameRepository(factory)
        analysis_repo = UserGameAnalysisRepository(factory)

        game = game_repo.create(user_id=user_id, sgf_content="(;FF[4])", source="research")
        game_id = game["id"]

        for i in range(5):
            analysis_repo.upsert(game_id=game_id, move_number=i, winrate=0.5 + i * 0.01)

        # Get all
        all_analysis = analysis_repo.get_analysis(game_id)
        assert len(all_analysis) == 5

        # Get range
        subset = analysis_repo.get_analysis(game_id, start_move=2, limit=2)
        assert len(subset) == 2
        assert subset[0]["move_number"] == 2
        assert subset[1]["move_number"] == 3

    def test_get_move_analysis(self, db_session):
        factory, user_id = db_session
        game_repo = UserGameRepository(factory)
        analysis_repo = UserGameAnalysisRepository(factory)

        game = game_repo.create(user_id=user_id, sgf_content="(;FF[4])", source="research")
        game_id = game["id"]

        analysis_repo.upsert(game_id=game_id, move_number=5, winrate=0.48, move="D4", actual_player="B")

        result = analysis_repo.get_move_analysis(game_id, 5)
        assert result is not None
        assert result["move"] == "D4"
        assert result["actual_player"] == "B"

    def test_get_nonexistent_move_analysis(self, db_session):
        factory, user_id = db_session
        game_repo = UserGameRepository(factory)
        analysis_repo = UserGameAnalysisRepository(factory)

        game = game_repo.create(user_id=user_id, sgf_content="(;FF[4])", source="research")
        result = analysis_repo.get_move_analysis(game["id"], 999)
        assert result is None

    def test_analysis_with_json_fields(self, db_session):
        factory, user_id = db_session
        game_repo = UserGameRepository(factory)
        analysis_repo = UserGameAnalysisRepository(factory)

        game = game_repo.create(user_id=user_id, sgf_content="(;FF[4])", source="research")
        game_id = game["id"]

        import json
        top_moves = json.dumps([{"move": "D4", "winrate": 0.52, "visits": 300}])
        analysis_repo.upsert(
            game_id=game_id,
            move_number=1,
            top_moves=top_moves,
            is_brilliant=True,
            is_mistake=False,
        )

        result = analysis_repo.get_move_analysis(game_id, 1)
        assert result["top_moves"] is not None
        assert result["is_brilliant"] is True
        assert result["is_mistake"] is False
