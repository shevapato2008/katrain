"""Base class for all cron jobs."""

import logging
from abc import ABC, abstractmethod


class BaseJob(ABC):
    """Base class for scheduled jobs.

    Subclasses must set ``name`` and ``interval_seconds``, and implement ``run()``.
    """

    name: str = "unnamed"
    interval_seconds: int = 60
    enabled: bool = True

    def __init__(self):
        self.logger = logging.getLogger(f"katrain_cron.{self.name}")

    @abstractmethod
    async def run(self) -> None:
        raise NotImplementedError
