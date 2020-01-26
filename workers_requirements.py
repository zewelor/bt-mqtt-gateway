import importlib
from pathlib import Path


def configured_workers():
    from config import settings

    workers = settings['manager']['workers']
    return _get_requirements(workers)


def all_workers():
    workers = map(lambda x: x.stem, Path('./workers').glob('*.py'))
    return _get_requirements(workers)


def _get_requirements(workers):
    requirements = set()

    for worker_name in workers:
        module_obj = importlib.import_module("workers.%s" % worker_name)

        try:
            requirements.update(module_obj.REQUIREMENTS)
        except AttributeError:
            continue

    return requirements
