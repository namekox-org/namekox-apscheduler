#! -*- coding: utf-8 -*-

# author: forcemain@163.com


import time


from functools import wraps


def apscheduler_task(func):
    @wraps(func)
    def wrapper(cls, *args, **kwargs):
        # fix apscheduler event order
        time.sleep(0.01)
        return func(cls, *args, **kwargs)
    return wrapper
