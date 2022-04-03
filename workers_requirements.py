import importlib
from pathlib import Path
import pkg_resources
import re
import os

import logger

_LOGGER = logger.get(__name__)


def configured_workers():
    from config import settings

    workers = settings['manager']['workers']
    return _get_requirements(workers)


def all_workers():
    workers = map(lambda x: x.stem, Path('./workers').glob('*.py'))
    return _get_requirements(workers)


def verify():
    requirements = configured_workers()
    egg = re.compile(r'.+#egg=(.+)$')

    distributions = []
    for req in requirements:
        try:
            pkg_resources.Requirement.parse(req)
            distributions.append(req)
        except (pkg_resources.extern.packaging.requirements.InvalidRequirement,
                pkg_resources.RequirementParseError):
            match = egg.match(req)
            if match:
                distributions.append(match.group(1))
            else:
                raise

    errors = []
    for dist in distributions:
        try:
            pkg_resources.require(dist)
        except pkg_resources.ResolutionError as e:
            errors.append(e.report())

    if errors:
        _LOGGER.error('Error: unsatisfied requirements:')
        for error in errors:
            _LOGGER.error('  %s', error)

        if os.geteuid() == 0:
            prefix = " sudo"
        else:
            prefix = ""

        _LOGGER.error('You may install those with pip: cd %s ; %s python3 -m pip install `./gateway.py -r configured`',
                      os.path.dirname(os.path.abspath(__file__)), prefix)
        exit(1)


def _get_requirements(workers):
    requirements = set()

    for worker_name in workers:
        module_obj = importlib.import_module("workers.%s" % worker_name)

        try:
            requirements.update(module_obj.REQUIREMENTS)
        except AttributeError:
            continue

    return requirements
