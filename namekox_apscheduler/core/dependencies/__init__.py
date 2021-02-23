#! -*- coding: utf-8 -*-
#
# author: forcemain@163.com

from __future__ import unicode_literals


import six
import time


from pytz import UTC
from namekox_core.core.friendly import AsLazyProperty
from namekox_core.core.service.dependency import Dependency
from namekox_apscheduler.core.schedule import EventletScheduler
from namekox_apscheduler.constants import APSCHEDULER_CONFIG_KEY


class APSchedulerHelper(Dependency):
    def __init__(self, **options):
        self.gt = None
        self.db_engine = None
        self.is_stopped = False
        options.setdefault('timezone', UTC)
        self.options = options
        self.scheduler = EventletScheduler()
        super(APSchedulerHelper, self).__init__(**options)

    @AsLazyProperty
    def config(self):
        return self.container.config.get(APSCHEDULER_CONFIG_KEY, {})

    def setup(self):
        config = self.config.copy()
        extra_job = config.pop('extra_job', {})
        job_store = self.options.get('jobstores', {}).get('default', None)
        job_store and self.options['jobstores'].update({'default': job_store(**config)})
        self.scheduler.configure(**self.options)
        for job_id, job_conf in six.iteritems(extra_job):
            job_conf.setdefault('id', job_id)
            if 'args' in job_conf and isinstance(job_conf['args'], (tuple, list)):
                job_conf['args'] = (self.container.service_cls,) + tuple(job_conf['args'])
            else:
                job_conf['args'] = (self.container.service_cls,)
            self.scheduler.add_job(**job_conf)

    def start(self):
        self.gt = self.container.spawn_manage_thread(self._run)

    def _run(self):
        self.scheduler.start()
        while not self.is_stopped:
            time.sleep(1)
        self.is_stopped = True

    def stop(self):
        self.is_stopped = True
        self.scheduler.shutdown()
        self.gt.wait()
