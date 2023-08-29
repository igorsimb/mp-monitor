- Make sure Docker is up and running
- Duplicate cmd tab  
`docker run -d -p 6379:6379 redis`  
`celery -A mp_monitor worker -l INFO --pool=eventlet`  
- duplicate tab again  
`celery -A mp_monitor beat -l INFO`