# start from an official image
FROM python:3.8

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Copy our code from cantusdb directory into the new code directory
COPY cantusdb /code/django/cantusdb
WORKDIR /code/django/cantusdb

# install our dependencies with pip
RUN pip3 install -r requirements.txt

# expose the port 8000
EXPOSE 8000

# define the default command to run when starting the container
CMD ["gunicorn", "--chdir", "cantusdb", "--bind", ":8000", "cantusdb.wsgi:application"]