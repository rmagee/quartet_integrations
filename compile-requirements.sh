#!/usr/bin/env bash
pip-compile --output-file requirements.txt requirements.in
pip-compile --output-file requirements_dev.txt requirements_dev.in
pip-compile --output-file requirements_test.txt requirements_test.in

