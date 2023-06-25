# Django Bootstrap Starter Kit

#### Includes the following features
- 2 apps - core and accounts - with URLs, views and basic templates already set up
- Bootstrap 5
- Custom User model 
- Registration, log in/out using `django-allauth` (with email as authentication method)
- [`django-extensions`](https://django-extensions.readthedocs.io/en/latest/)
- [`django-debug-toolbar`](https://django-debug-toolbar.readthedocs.io/en/latest/)
- [`django-widget-tweaks`](https://pypi.org/project/django-widget-tweaks/)
- Tests for Custom User, sign up, views, and templates

## Installation

### Create a virtual environment
```shell
python -m venv <virtual_env_name>
```

### Activate it

(windows)
```shell
<virtual_env_name>\Scripts\activate
```

(macOS)
```shell
source <virtual_env_name>/bin/activate
```

### Install Django
```shell
pip install django
```

### Run startproject command
Use this repository as Django project template (don't forget the dot at the end if you want to create project in the same directory). Also, use your own preferred name for `<project_name>`

```shell
 django-admin startproject --template https://github.com/igorsimb/django-project-template/archive/refs/heads/master.zip <project_name> .
```

### Install everything from requirements.txt
```shell
pip install -r requirements.txt
```

### Make migrations:

```shell
python manage.py makemigrations
```

```shell
python manage.py migrate
```

### Run tests
```shell
python manage.py test
```

### Run server:

```shell
python manage.py runserver
```

Note:
Whenever you need to call User, put this at the top of the file (e.g. in views.py, models.py):
```python
from django.contrib.auth import get_user_model
User = get_user_model()
```

You are all set! :)