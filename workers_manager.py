import importlib
import pip
from apscheduler.schedulers.background import BackgroundScheduler
from interruptingcow import timeout
from logger import _LOGGER
from workers_queue import _WORKERS_QUEUE

class WorkersManager:
  class Command:
    def __init__(self, callback, args=[], options={}):
      self._callback = callback
      self._args = args
      self._options = options

    def execute(self):
      messages = []
      with timeout(30):
        messages = self._callback(*self._args)

      _LOGGER.debug(messages)
      return messages

  def __init__(self, config, mqtt):
    self._mqtt = mqtt
    self._workers = self._register_klasses(config)

  @property
  def workers(self):
    return self._workers

  def _register_klasses(self, config):
    arr = {}
    scheduler = BackgroundScheduler()
    mqtt_callbacks = []

    for (worker_name, worker_config) in config.items():
      moduleObj = importlib.import_module("workers.%s" % worker_name)
      klass = getattr(moduleObj, "%sWorker" % worker_name.title())
      worker_obj = klass(**worker_config['args'])

      if moduleObj.REQUIREMENTS is not None:
        self._pip_install_helper(moduleObj.REQUIREMENTS)

      if 'update_interval' in worker_config:
        _LOGGER.debug("Added: %s with %d seconds interval" % (worker_name, worker_config['update_interval']))
        _WORKERS_QUEUE.put(self.Command(worker_obj.status_update, []))
        scheduler.add_job(lambda x: _WORKERS_QUEUE.put(self.Command(worker_obj.status_update, [])), 'interval', seconds=worker_config['update_interval'], args=[worker_name])

      if 'topic_subscription' in worker_config:
        _LOGGER.debug("Subscribing to: %s" % worker_config['topic_subscription'] + '/#')
        mqtt_callbacks.append((worker_config['topic_subscription'] + '/#', lambda client, _ , c: _WORKERS_QUEUE.put(self.Command(worker_obj.on_command, [c.topic, c.payload]))))

      arr[worker_name] = worker_obj

    scheduler.start()
    self._mqtt.callbacks_subscription(mqtt_callbacks)

    return arr

  def _pip_install_helper(self, package_names):
    for package in package_names:
      pip.main(['install', '-q', package])
