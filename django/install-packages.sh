#!/bin/bash

pip install poetry==1.8.2

poetry config virtualenvs.in-project true # Creates a virtualenv in the project directory
poetry config virtualenvs.options.always-copy true # Ensures no symlinking in the virtualenv
poetry config virtualenvs.options.no-pip true # Don't install pip in the virtualenv
poetry config virtualenvs.options.no-setuptools true # Don't install setuptools in the virtualenv

if [ $1 = "DEVELOPMENT" ]; then
    poetry install --no-cache --with debug
else
    poetry install --no-cache
fi 