import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TutorialLoader:
    """Loads the published tutorial package from disk into memory at startup.

    Reads active.json to find the current version directory, then loads all
    categories, topics, and examples into in-memory dicts. Thread-safe for
    read operations after load() completes. load() itself is not thread-safe
    and should only be called at startup or under an external lock.
    """

    def __init__(self, base_dir: Path):
        self._base_dir = base_dir
        self._version_dir: Optional[Path] = None
        self._categories: List[Dict] = []
        self._topics_by_category: Dict[str, List[Dict]] = {}
        self._topics_by_id: Dict[str, Dict] = {}
        self._examples: Dict[str, Dict] = {}

    def load(self) -> None:
        """Load (or reload) the active published package from disk."""
        active_path = self._base_dir / "active.json"
        if not active_path.exists():
            raise FileNotFoundError(f"Tutorial active.json not found at {active_path}")

        active = json.loads(active_path.read_text())
        version_path = self._base_dir / active["path"]
        if not version_path.is_dir():
            raise FileNotFoundError(f"Tutorial version dir not found: {version_path}")

        self._version_dir = version_path
        self._categories = []
        self._topics_by_category = {}
        self._topics_by_id = {}
        self._examples = {}

        self._load_categories()
        logger.info(
            "Tutorial package loaded: version=%s, categories=%d, topics=%d, examples=%d",
            active["version"],
            len(self._categories),
            len(self._topics_by_id),
            len(self._examples),
        )

    def _load_categories(self) -> None:
        categories_dir = self._version_dir / "categories"
        if not categories_dir.is_dir():
            return
        cats = []
        for f in sorted(categories_dir.glob("*.json")):
            cat = json.loads(f.read_text())
            cats.append(cat)
            self._load_topics_for_category(cat["slug"])
        self._categories = sorted(cats, key=lambda c: c.get("order", 999))

    def _load_topics_for_category(self, slug: str) -> None:
        topic_dir = self._version_dir / "topics" / slug
        if not topic_dir.is_dir():
            self._topics_by_category[slug] = []
            return
        topics = []
        for f in sorted(topic_dir.glob("*.json")):
            topic = json.loads(f.read_text())
            topics.append(topic)
            self._topics_by_id[topic["id"]] = topic
            for example_id in topic.get("example_ids", []):
                self._load_example(example_id)
        self._topics_by_category[slug] = topics

    def _load_example(self, example_id: str) -> None:
        path = self._version_dir / "examples" / f"{example_id}.json"
        if not path.exists():
            logger.warning("Example file not found: %s", path)
            return
        self._examples[example_id] = json.loads(path.read_text())

    # ── Public read API ───────────────────────────────────────────────────────

    def get_categories(self) -> List[Dict]:
        return list(self._categories)

    def get_topics_by_category(self, slug: str) -> List[Dict]:
        return list(self._topics_by_category.get(slug, []))

    def get_topic(self, topic_id: str) -> Optional[Dict]:
        return self._topics_by_id.get(topic_id)

    def get_example(self, example_id: str) -> Optional[Dict]:
        return self._examples.get(example_id)

    def get_examples_for_topic(self, topic_id: str) -> List[Dict]:
        """Return all published examples belonging to a topic, in order."""
        topic = self._topics_by_id.get(topic_id)
        if topic is None:
            return []
        return [
            self._examples[eid]
            for eid in topic.get("example_ids", [])
            if eid in self._examples
        ]

    def get_asset_path(self, asset_ref: str) -> Path:
        """Return the absolute path to an asset within the active version directory.

        Note: asset_ref must be a relative path within the version directory
        (e.g. 'assets/images/foo.png'). Callers are responsible for validating
        inputs before serving to external users to prevent path traversal.
        """
        return self._version_dir / asset_ref
