#! -*- coding: utf-8 -*-
#
# author: forcemain@163.com

from __future__ import unicode_literals


import sqlalchemy as sa
import sqlalchemy_utils as su


from sqlalchemy.orm import relationship
from namekox_core.core.generator import generator_uuid


from .base import Model


class Job(Model, su.Timestamp):
    __tablename__ = 'jobs'

    id = sa.Column(sa.String(36), default=generator_uuid, primary_key=True)
    name = sa.Column(sa.String(200), unique=True)
    next_run_time = sa.Column(sa.DateTime, nullable=True, default=None, index=True)
    job_state = sa.Column(sa.LargeBinary, nullable=False)

    logs = relationship('Log', backref='job', lazy='dynamic', cascade='all, delete-orphan', passive_deletes=True)
