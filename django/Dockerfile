# start from an official image
FROM python:3.9

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

EXPOSE 8000

WORKDIR /code/django/cantusdb_project

COPY cantusdb_project/requirements.txt /code/django/cantusdb_project

RUN pip3 install -r requirements.txt

COPY cantusdb_project .

# define the default command to run when starting the container
CMD ["gunicorn", "--chdir", "cantusdb", "--bind", ":8000", "cantusdb.wsgi:application", "--workers", "5"]