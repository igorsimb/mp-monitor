import datetime

from celery import shared_task
from celery.beat import logger


@shared_task(schedule=datetime.timedelta(seconds=10)) # does not work
def print_hello():
    logger.info(f'LOGGER Hello, current time is {datetime.datetime.now()}')