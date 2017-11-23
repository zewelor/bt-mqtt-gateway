import importlib
import pip

class WorkersManager:
  def __init__(self, config):
    self._config = config
    self._workers = self._register_klasses()

  def update(self, worker_name):
    messages = self.workers[worker_name].status_update()
    for message in messages:
      message['topic'] = '/'.join([self._config[worker_name]['topic_prefix'], message['topic']])

    return messages

  @property
  def workers(self):
    return self._workers

  def _register_klasses(self):
    arr = {}

    for worker_klass in self._config.keys():
      moduleObj = importlib.import_module("workers.%s" % worker_klass)
      klass = getattr(moduleObj, "%sWorker" % worker_klass.title())
      if moduleObj.REQUIREMENTS is not None:
        self._pip_install_helper(moduleObj.REQUIREMENTS)
      arr[worker_klass] = klass(**self._args_for(worker_klass))

    return arr

  def _args_for(self, klass):
    return self._config[klass]['args']

  def _pip_install_helper(self, package_names):
    for package in package_names:
      pip.main(['install','-q', package])
