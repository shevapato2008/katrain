import pytest
from pathlib import Path
from katrain.web.tutorials.loader import TutorialLoader

FIXTURE_PATH = Path("data/tutorials_published")


@pytest.fixture
def loader():
    ldr = TutorialLoader(base_dir=FIXTURE_PATH)
    ldr.load()
    return ldr


def test_loader_loads_categories(loader):
    cats = loader.get_categories()
    assert len(cats) == 1
    assert cats[0]["id"] == "cat_opening"
    assert cats[0]["slug"] == "opening"


def test_loader_loads_topics_for_category(loader):
    topics = loader.get_topics_by_category("opening")
    assert len(topics) == 1
    assert topics[0]["id"] == "topic_opening_001"


def test_loader_get_topic_by_id(loader):
    topic = loader.get_topic("topic_opening_001")
    assert topic is not None
    assert topic["title"] == "角、边与中央的价值"


def test_loader_get_unknown_topic_returns_none(loader):
    assert loader.get_topic("does_not_exist") is None


def test_loader_get_example(loader):
    example = loader.get_example("ex_opening_001")
    assert example is not None
    assert example["step_count"] == 2
    assert len(example["steps"]) == 2


def test_loader_get_examples_for_topic(loader):
    examples = loader.get_examples_for_topic("topic_opening_001")
    assert len(examples) == 1
    assert examples[0]["id"] == "ex_opening_001"


def test_loader_get_examples_for_unknown_topic(loader):
    assert loader.get_examples_for_topic("does_not_exist") == []


def test_loader_example_steps_have_no_source_fields(loader):
    example = loader.get_example("ex_opening_001")
    forbidden = {"source_path", "raw_text", "source_id", "book_title", "author"}
    for step in example["steps"]:
        assert not forbidden.intersection(step.keys())


def test_loader_example_steps_board_mode_image(loader):
    example = loader.get_example("ex_opening_001")
    step = example["steps"][0]
    assert step["board_mode"] == "image"
    assert step["board_payload"] is None


def test_loader_asset_exists(loader):
    asset_path = loader.get_asset_path("assets/images/ex_opening_001_step_01.png")
    assert asset_path.exists()


def test_loader_reload_is_idempotent(loader):
    loader.load()
    cats = loader.get_categories()
    assert len(cats) == 1
