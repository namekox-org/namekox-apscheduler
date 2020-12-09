#! -*- coding: utf-8 -*-

# author: forcemain@163.com


import sqlalchemy as sa


from functools import wraps
from logging import getLogger
from sqlalchemy.exc import IntegrityError


from . import models


logger = getLogger(__name__)


def del_dblock(engine, lock_name):
    sql = sa.delete(models.Lock).where(models.Lock.name == lock_name)
    engine.execute(sql)


def add_dblock(engine, lock_name):
    sql = sa.insert(models.Lock).values(**{'name': lock_name})
    engine.execute(sql)


def distributed_lock(func):
    @wraps(func)
    def wrapper(cls, *args, **kwargs):
        job_store = cls.apscheduler.scheduler._jobstores.get('default', None)
        if not hasattr(job_store, 'db_engine'):
            return func(cls, *args, **kwargs)
        ret_value = None
        lock_name = func.__name__
        db_engine = job_store.db_engine
        try:
            add_dblock(db_engine, lock_name)
            mesg = 'acquire distributed dblock {} succ'.format(lock_name)
            logger.debug(mesg)
            ret_value = func(cls, *args, **kwargs)
        except IntegrityError as e:
            errs = 'acquire distributed dblock {} fail'.format(lock_name)
            logger.error(errs)
            raise e
        finally:
            mesg = 'release distributed dblock {} succ'.format(lock_name)
            del_dblock(db_engine, lock_name)
            logger.debug(mesg)
        return ret_value
    return wrapper
