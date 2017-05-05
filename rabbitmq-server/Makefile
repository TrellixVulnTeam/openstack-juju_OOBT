#!/usr/bin/make
PYTHON := /usr/bin/env python
CHARM_DIR := $(PWD)
HOOKS_DIR := $(PWD)/hooks
TEST_PREFIX := PYTHONPATH=$(HOOKS_DIR)

clean:
	rm -f .coverage .testrepository
	find . -name '*.pyc' -delete

lint:
	@tox -e pep8

bin/charm_helpers_sync.py:
	@mkdir -p bin
	@bzr cat lp:charm-helpers/tools/charm_helpers_sync/charm_helpers_sync.py \
        > bin/charm_helpers_sync.py

sync: bin/charm_helpers_sync.py
	@$(PYTHON) bin/charm_helpers_sync.py -c charm-helpers-hooks.yaml
	@$(PYTHON) bin/charm_helpers_sync.py -c charm-helpers-tests.yaml

publish: lint test
	bzr push lp:charms/rabbitmq-server
	bzr push lp:charms/trusty/rabbitmq-server

test:
	@echo Starting unit tests...
	@tox -e py27

functional_test:
	@echo Starting amulet tests...
	@tox -e func27
