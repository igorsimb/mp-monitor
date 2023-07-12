import os

from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mp_monitor.settings')

app = Celery('mp_monitor')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')



# celery beat tasks

app.conf.beat_schedule ={
'say-hello-every-10-seconds':{
'task': 'main.tasks.print_hello',
        'schedule': 10.0,
},
}

# use commands:
# one tab:  celery -A mp_monitor worker -l info --pool=eventlet
# another tab: celery -A mp_monitor beat -l info