import importlib


class WorkersManager:
  def __init__(self, config):
    self._config = config
    self._workers = self._register_klasses()

  def get_updates(self):
    lazy_map = map(lambda worker: worker.status_update(), self._workers)
    flat_list = sum(lazy_map, [])  # List flatten
    return flat_list

  def _register_klasses(self):
    arr = []

    for worker_klass in self._config.keys():
      klass = getattr(importlib.import_module("workers.%s" % worker_klass), "%sWorker" % worker_klass.title())
      arr.append(klass(**self._args_for(worker_klass)))

    return arr

  def _args_for(self, klass):
    return self._config[klass]['args']
