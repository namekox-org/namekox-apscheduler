#! -*- coding: utf-8 -*-
#
# author: forcemain@163.com

from __future__ import unicode_literals


import pickle
import sqlalchemy as sa


from logging import getLogger
from apscheduler import events
from apscheduler.job import Job
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.expression import null
from namekox_core.core.timezone import make_aware, make_naive
from apscheduler.jobstores.base import BaseJobStore, JobLookupError, ConflictingIdError


from . import models


logger = getLogger(__name__)


class DBJobStoreMixin(object):
    def __init__(self, job_store_uri='', job_store_cfg=None):
        super(DBJobStoreMixin, self).__init__()
        self.db_stlock = None
        self.db_engine = None

        self._job_store_uri = job_store_uri
        self._job_store_cfg = job_store_cfg or {}

    def __call__(self, job_store_uri='', job_store_cfg=None):
        self._job_store_uri = job_store_uri or self._job_store_uri
        self._job_store_cfg = job_store_cfg or self._job_store_cfg
        self.db_engine = create_engine(self._job_store_uri, **self._job_store_cfg)
        return self

    def start(self, scheduler, alias):
        super(DBJobStoreMixin, self).start(scheduler, alias)
        self.db_stlock = self._scheduler._create_lock()
        self.register_event_listeners()

    def handle_executed_event(self, event):
        models.Log.create(
            self.db_engine,
            self.db_stlock,
            event.job_id,
            models.Log.STATUS_EXECUTED,
            event.scheduled_run_time,
            ret_value=str(event.retval)
        )

    def handle_missed_event(self, event):
        exception = 'execute of job {} time missed'.format(event.job_id)
        models.Log.create(
            self.db_engine,
            self.db_stlock,
            event.job_id,
            models.Log.STATUS_MISSED,
            event.scheduled_run_time,
            ret_value=str(event.retval),
            exception=exception
        )

    def handle_max_instances_event(self, event):
        exception = 'execute of job {} reached max instances'.format(event.job_id)
        models.Log.create(
            self.db_engine,
            self.db_stlock,
            event.job_id,
            models.Log.STATUS_MAX_INSTANCES,
            event.scheduled_run_times[0],
            exception=exception
        )

    def handle_error_event(self, event):
        if not event.exception:
            exception = 'job {} raised an error'.format(event.job_id)
            traceback = None
        else:
            exception = str(event.exception)
            traceback = str(event.traceback)
        models.Log.create(
            self.db_engine,
            self.db_stlock,
            event.job_id,
            models.Log.STATUS_ERROR,
            event.scheduled_run_time,
            ret_value=str(event.retval),
            exception=exception,
            traceback=traceback
        )

    def register_event_listeners(self):
        self._scheduler.add_listener(self.handle_executed_event, events.EVENT_JOB_EXECUTED)
        self._scheduler.add_listener(self.handle_missed_event, events.EVENT_JOB_MISSED)
        self._scheduler.add_listener(self.handle_max_instances_event, events.EVENT_JOB_MAX_INSTANCES)
        self._scheduler.add_listener(self.handle_error_event, events.EVENT_JOB_ERROR)


class DBJobStore(DBJobStoreMixin, BaseJobStore):
    def _raise_again(self, exc, message=''):
        raise exc(message) if message else exc()

    def _reconstitute_job(self, job_state):
        job_state = pickle.loads(job_state)
        job_state['jobstore'] = self
        job = Job.__new__(Job)
        job.__setstate__(job_state)
        job._scheduler = self._scheduler
        job._jobstore_alias = self._alias
        return job

    def _filter_some_jobs(self, *conditions):
        jobs = []
        query_sql = sa.select([models.Job.name, models.Job.next_run_time, models.Job.job_state])
        query_sql = query_sql.order_by(models.Job.next_run_time)
        query_sql = query_sql.where(*conditions) if conditions else query_sql
        fail_job_ids = set()
        for row in self.db_engine.execute(query_sql):
            try:
                jobs.append(self._reconstitute_job(row.job_state))
            except Exception:
                logger.warn('unable to restore job %s -- removing it', row.id)
                fail_job_ids.add(row.name)
        # remove all the jobs we failed to restore
        query_sql = sa.delete(models.Job)
        query_sql = query_sql.where(models.Job.name.in_(fail_job_ids))
        self.db_engine.execute(query_sql)
        return jobs

    def lookup_job(self, job_id):
        query_sql = sa.select([models.Job.job_state])
        query_sql = query_sql.where(models.Job.name == job_id)
        job_state = self.db_engine.execute(query_sql).scalar()
        return self._reconstitute_job(job_state) if job_state else None

    def get_due_jobs(self, now):
        conditions = (models.Job.next_run_time <= make_naive(now),)
        return self._filter_some_jobs(*conditions)

    def get_next_run_time(self):
        query_sql = sa.select([models.Job.next_run_time])
        query_sql = query_sql.where(models.Job.next_run_time != null())
        query_sql = query_sql.order_by(models.Job.next_run_time)
        query_sql = query_sql.limit(1)
        next_run_time = self.db_engine.execute(query_sql).scalar()
        return make_aware(next_run_time) if next_run_time else None

    def get_all_jobs(self):
        jobs = self._filter_some_jobs()
        self._fix_paused_jobs_sorting(jobs)
        return jobs

    def add_job(self, job):
        self.db_stlock.acquire()
        next_run_time = make_naive(job.next_run_time) if job.next_run_time else None
        query_sql = sa.insert(models.Job).values(**{
            'name': job.id,
            'next_run_time': next_run_time,
            'job_state': pickle.dumps(job.__getstate__(), pickle.HIGHEST_PROTOCOL)})
        try:
            self.db_engine.execute(query_sql)
        except IntegrityError:
            self._raise_again(ConflictingIdError, job.id)
        self.db_stlock.release()

    def update_job(self, job):
        self.db_stlock.acquire()
        next_run_time = make_naive(job.next_run_time) if job.next_run_time else None
        query_sql = sa.update(models.Job).values(**{
            'next_run_time': next_run_time,
            'job_state': pickle.dumps(job.__getstate__(), pickle.HIGHEST_PROTOCOL)
        }).where(models.Job.name == job.id)
        result = self.db_engine.execute(query_sql)
        self.db_stlock.release()
        result.rowcount == 0 and self._raise_again(JobLookupError, job.id)

    def remove_job(self, job_id):
        query_sql = sa.delete(models.Job).where(models.Job.name == job_id)
        result = self.db_engine.execute(query_sql)
        result.rowcount == 0 and self._raise_again(JobLookupError, job_id)

    def remove_all_jobs(self):
        query_sql = sa.delete(models.Job)
        self.db_engine.execute(query_sql)

    def shutdown(self):
        self.db_engine.engine.dispose()
