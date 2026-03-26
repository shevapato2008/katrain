"""Entry point: python -m katrain.cron"""

import asyncio
import logging
import signal
import sys

from katrain.cron import config


def _setup_logging():
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def _main():
    logger = logging.getLogger("katrain_cron")
    logger.info("katrain-cron starting")

    # Late import so logging is configured first
    from katrain.cron.scheduler import CronScheduler

    scheduler = CronScheduler()

    # Graceful shutdown on SIGINT / SIGTERM
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(scheduler.shutdown()))

    try:
        await scheduler.start()
    except Exception:
        logger.exception("Fatal error in scheduler")
        sys.exit(1)


def main():
    _setup_logging()
    asyncio.run(_main())


if __name__ == "__main__":
    main()
