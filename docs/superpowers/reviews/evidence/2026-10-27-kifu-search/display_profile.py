"""Two isolated read-only local reads; profile the second, never write data."""
import cProfile
import pstats
import signal
import time

from sqlalchemy import text
from katrain.web.core.db import SessionLocal
from katrain.web.api.v1.endpoints.kifu import read_album_page

signal.alarm(40)
profile = cProfile.Profile()
for index in range(2):
    with SessionLocal() as db:
        db.execute(text('SET TRANSACTION READ ONLY'))
        db.execute(text("SET LOCAL statement_timeout='5000ms'"))
        started = time.perf_counter()
        timings = {}
        if index:
            profile.enable()
        result = read_album_page(db, q='\u738b\u661f\u660a', page=1, page_size=20, lang='cn', timings=timings)
        if index:
            profile.disable()
        print({'sample': index, 'wall_ms': (time.perf_counter()-started)*1000,
               'total': result.total, 'items': len(result.items), 'timings': timings}, flush=True)
        db.rollback()
pstats.Stats(profile).strip_dirs().sort_stats('cumulative').print_stats(45)
pstats.Stats(profile).strip_dirs().sort_stats('tottime').print_stats(25)
