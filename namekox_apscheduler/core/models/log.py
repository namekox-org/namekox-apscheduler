#! -*- coding: utf-8 -*-
#
# author: forcemain@163.com

from __future__ import unicode_literals


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
    def create(cls, engine, lock, job_id, status, run_time, ret_value=None, exception=None, traceback=None):
        lock.acquire()
        finished = datetime.utcnow()
        run_time = make_naive(run_time)
        duration = (finished - run_time).total_seconds()
        query_sql = sa.insert(cls).values(**{
            'run_time': run_time,
            'finished': finished,
            'duration': duration,
            'job_id': job_id,
            'status': status,
            'ret_value': ret_value,
            'exception': exception,
            'traceback': traceback,
        })
        engine.execute(query_sql)
        lock.release()
