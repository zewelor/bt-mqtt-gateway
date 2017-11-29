import importlib
import pip
from apscheduler.schedulers.background import BackgroundScheduler
from interruptingcow import timeout
from logger import _LOGGER
from workers_queue import _WORKERS_QUEUE

class WorkersManager:
  class Command:
    def __init__(self, callback, args=(), options=dict()):
      self._callback = callback
      self._args = args
      self._options = options

    def execute(self):
      messages = []
      with timeout(30):
        messages = self._callback(*self._args)

      _LOGGER.debug(messages)
      return messages

  @classmethod
  def start(cls, mqtt, config):
    scheduler = BackgroundScheduler()
    mqtt_callbacks = []

    for (worker_name, worker_config) in config.items():
      module_obj = importlib.import_module("workers.%s" % worker_name)
      klass = getattr(module_obj, "%sWorker" % worker_name.title())

      if module_obj.REQUIREMENTS is not None:
        cls._pip_install_helper(module_obj.REQUIREMENTS)

      worker_obj = klass(**worker_config['args'])

      if 'update_interval' in worker_config:
        _LOGGER.debug("Added: %s with %d seconds interval" % (worker_name, worker_config['update_interval']))
        _WORKERS_QUEUE.put(cls.Command(worker_obj.status_update, []))
        scheduler.add_job(
          lambda x: _WORKERS_QUEUE.put(cls.Command(worker_obj.status_update, [])), 'interval',
          seconds=worker_config['update_interval'],
          args=[worker_name]
        )

      if 'topic_subscription' in worker_config:
        _LOGGER.debug("Subscribing to: %s" % worker_config['topic_subscription'])
        mqtt_callbacks.append((
          worker_config['topic_subscription'],
          lambda client, _ , c: _WORKERS_QUEUE.put(cls.Command(worker_obj.on_command, [c.topic, c.payload]))
        ))

    scheduler.start()
    mqtt.callbacks_subscription(mqtt_callbacks)

  @staticmethod
  def _pip_install_helper(package_names):
    for package in package_names:
      pip.main(['install', '-q', package])
