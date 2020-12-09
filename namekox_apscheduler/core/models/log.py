# ! -*- coding: utf-8 -*-
#
# author: forcemain@163.com


import sqlalchemy as sa
import sqlalchemy_utils as su


from datetime import datetime
from logging import getLogger
from namekox_core.core.timezone import make_naive
from namekox_core.core.generator import generator_uuid


from .base import Model


logger = getLogger(__name__)


class Log(Model, su.Timestamp):
    __tablename__ = 'logs'

    STATUS_PENDING = 0

    STATUS_SUBMITTED = 1

    STATUS_EXECUTED = 2

    STATUS_MISSED = 3

    STATUS_MAX_INSTANCES = 4

    STATUS_ERROR = 5

    id = sa.Column(sa.String(36), default=generator_uuid, primary_key=True)
    status = sa.Column(sa.Integer, default=STATUS_PENDING)
    run_time = sa.Column(sa.DateTime, nullable=True, default=None, index=True)
    finished = sa.Column(sa.DateTime, nullable=True, default=None, index=True)
    duration = sa.Column(sa.Numeric(15, 2), nullable=True, default=None)
    ret_value = sa.Column(sa.Text, nullable=True, default=None)
    exception = sa.Column(sa.Text, nullable=True, default=None)
    traceback = sa.Column(sa.Text, nullable=True, default=None)

    job_id = sa.Column(sa.String(200), sa.ForeignKey('jobs.name', ondelete='CASCADE'))

    @classmethod
    def update_or_create(cls, engine, lock, job_id, status, run_time, ret_value=None, exception=None, traceback=None):
        lock.acquire()
        run_time = make_naive(run_time)
        where_sql = sa.and_(cls.job_id == job_id, cls.run_time == run_time)
        query_sql = sa.select([cls.id])
        query_sql = query_sql.where(where_sql)
        log_id = engine.execute(query_sql).scalar()
        if not log_id:
            query_sql = sa.insert(cls).values(**{'status': status, 'run_time': run_time, 'job_id': job_id})
        else:
            finished = datetime.utcnow()
            duration = (finished - run_time).total_seconds()
            query_sql = sa.update(cls).values(**{'status': status, 'finished': finished, 'duration': duration,
                                                 'ret_value': ret_value, 'exception': exception, 'traceback': traceback})
            query_sql = query_sql.where(cls.id == log_id)
        engine.execute(query_sql)
        lock.release()
