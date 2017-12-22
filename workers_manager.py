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

  def __init__(self):
    self._mqtt_callbacks = []
    self._update_commands = []
    self._scheduler = BackgroundScheduler()

  def register_workers(self, config):
    for (worker_name, worker_config) in config['workers'].items():
      module_obj = importlib.import_module("workers.%s" % worker_name)
      klass = getattr(module_obj, "%sWorker" % worker_name.title())

      if module_obj.REQUIREMENTS is not None:
        self._pip_install_helper(module_obj.REQUIREMENTS)

      worker_obj = klass(**worker_config['args'])

      if hasattr(worker_obj, 'status_update'):
        _LOGGER.debug("Added: %s with %d seconds interval" % (worker_name, worker_config['update_interval']))
        command = self.Command(worker_obj.status_update, [])
        self._update_commands.append(command)

        if 'update_interval' in worker_config:
          self._scheduler.add_job(
            lambda x: self._queue_command(command), 'interval',
            seconds=worker_config['update_interval'],
            args=[worker_name]
          )

      if 'topic_subscription' in worker_config:
        _LOGGER.debug("Subscribing to: %s" % worker_config['topic_subscription'])
        self._mqtt_callbacks.append((
          worker_config['topic_subscription'],
          lambda client, _ , c: self._queue_command(self.Command(worker_obj.on_command, [c.topic, c.payload]))
        ))

    if 'topic_subscription' in config:
      for (callback_name, options) in config['topic_subcription'].items():
        _LOGGER.debug("Subscribing to: %s with command: %s" % (options['topic'], callback_name))
        self._mqtt_callbacks.append((
          options['topic'],
          lambda client, _ , c: self._queue_if_matching_payload(self.Command(getattr(self, callback_name)), c.payload, options['payload']))
        )

    return self

  def start(self, mqtt):
    mqtt.callbacks_subscription(self._mqtt_callbacks)
    self._scheduler.start()
    self.update_all()

  def _queue_if_matching_payload(self, command, payload, expected_payload):
    if payload.decode('utf-8') == expected_payload:
      self._queue_command(command)

  @property
  def mqtt_callbacks(self):
    return self._mqtt_callbacks

  def update_all(self):
    _LOGGER.debug("Updating all workers")
    for command in self._update_commands:
      self._queue_command(command)

  @staticmethod
  def _queue_command(command):
    _WORKERS_QUEUE.put(command)

  @staticmethod
  def _pip_install_helper(package_names):
    for package in package_names:
      pip.main(['install', '-q', package])
