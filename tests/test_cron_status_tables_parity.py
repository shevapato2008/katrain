"""The web process owns these tables; cron maps the same columns independently."""

from sqlalchemy import create_engine, inspect

from katrain.cron import models as cron_models
from katrain.web.core import models_db


def _shape(model):
    columns = {
        col.name: (
            str(col.type),
            getattr(col.type, "timezone", None),
            col.nullable,
            col.primary_key,
            bool(col.index),
            repr(getattr(col.default, "arg", None)),
            repr(getattr(col.server_default, "arg", None)),
        )
        for col in model.__table__.columns
    }
    indexes = {(index.name, tuple(col.name for col in index.columns)) for index in model.__table__.indexes}
    return columns, indexes


def test_web_and_cron_map_identical_cron_tables():
    for web, cron in (
        (models_db.CronJobStatus, cron_models.CronJobStatusDB),
        (models_db.CronJobRun, cron_models.CronJobRunDB),
    ):
        assert web.__tablename__ == cron.__tablename__
        assert _shape(web) == _shape(cron)


def test_web_schema_creates_cron_tables():
    engine = create_engine("sqlite:///:memory:")
    models_db.Base.metadata.create_all(engine)
    assert {"cron_job_status", "cron_job_runs"} <= set(inspect(engine).get_table_names())
