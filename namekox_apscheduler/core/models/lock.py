#! -*- coding: utf-8 -*-

# author: forcemain@163.com


import sqlalchemy as sa
import sqlalchemy_utils as su


from namekox_core.core.generator import generator_uuid


from .base import Model


class Lock(Model, su.Timestamp):
    __tablename__ = 'locks'

    id = sa.Column(sa.String(36), default=generator_uuid, primary_key=True)
    name = sa.Column(sa.String(200), unique=True)
