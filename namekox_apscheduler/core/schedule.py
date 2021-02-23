#! -*- coding: utf-8 -*-
#
# author: forcemain@163.com

from __future__ import unicode_literals


from apscheduler.schedulers.background import BackgroundScheduler


class EventletScheduler(BackgroundScheduler):
    def get_job(self, job_id, jobstore=None):
        self._jobstores_lock.acquire()
        resp = self._lookup_job(job_id, jobstore)[0]
        self._jobstores_lock.release()
        return resp

    def shutdown(self, *args, **kwargs):
        super(BackgroundScheduler, self).shutdown(*args, **kwargs)
