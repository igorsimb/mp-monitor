- Make sure Docker is up and running
- Duplicate cmd tab  
  `docker run -d -p 6379:6379 redis`  
  `celery -A mp_monitor worker -l INFO --pool=eventlet`  
  (for windows:) `celery -A mp_monitor worker -l info -P gevent`
- duplicate tab  
  `celery -A mp_monitor beat -l INFO`

- Or run one command (Linux):  
  `celery -A mp_monitor  worker --beat --scheduler django --loglevel=info`

### Check pytest coverage

`pytest -n 4 --cov-config=.coveragerc --cov=. tests/`

### Use pytest-xdist for multithreading tests

`pytest -n 4` (4 = number of processes, up to 32)

### Trigger pre-commit checks manually

`pre-commit run --all-files`

### Run ruff format on everything

`ruff format .`
