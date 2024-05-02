# Download and install python dependencies in a container
FROM python:3.9 as dependency-install-container
ARG PROJECT_ENVIRONMENT
COPY ./poetry.lock ./pyproject.toml ./django/install-packages.sh /code/
WORKDIR /code
RUN chmod u+x /code/install-packages.sh && \
    /code/install-packages.sh $PROJECT_ENVIRONMENT

# Copy our dependencies into the base image
FROM python:3.9
COPY --from=dependency-install-container /code/.venv /code/.venv

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

EXPOSE 8000

WORKDIR /code/cantusdb_project

# Add our python environment binaries and package files to the path
ENV PATH="$PATH:/code/.venv/bin/" \
    PYTHONPATH="$PYTHONPATH:/code/.venv/lib/python3.9/site-packages/"

# define the default command to run when starting the container
CMD ["gunicorn", "--bind", ":8000", "cantusdb.wsgi:application", "--workers", "5"]