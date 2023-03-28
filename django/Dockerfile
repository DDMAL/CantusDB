# start from an official image
FROM python:3.9

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Copy our code from cantusdb directory into the new code directory
COPY cantusdb_project /code/django/cantusdb_project
WORKDIR /code/django/cantusdb_project

# install our dependencies with pip
RUN pip3 install -r requirements.txt

# expose the port 8000
EXPOSE 8000

# define the default command to run when starting the container
CMD ["gunicorn", "--chdir", "cantusdb", "--bind", ":8000", "cantusdb.wsgi:application"]