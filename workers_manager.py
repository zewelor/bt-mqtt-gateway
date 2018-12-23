import importlib
import threading

from pip import __version__ as pip_version
if int(pip_version.split('.')[0]) >= 10:
  from pip._internal import main as pip_main
else:
  from pip import main as pip_main

from apscheduler.schedulers.background import BackgroundScheduler
from interruptingcow import timeout
from functools import partial
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
      with timeout(35):
        messages = self._callback(*self._args)

      _LOGGER.debug(messages)
      return messages

  def __init__(self):
    self._mqtt_callbacks = []
    self._update_commands = []
    self._scheduler = BackgroundScheduler()
    self._daemons = []

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
            partial(self._queue_command, command), 'interval',
            seconds=worker_config['update_interval'],
          )
      elif hasattr(worker_obj, 'run'):
        _LOGGER.debug("Registered: %s as daemon" % (worker_name))
        self._daemons.append(worker_obj)
      else:
        raise "%s cannot be initialized, it has to define run or status_update method" % worker_name

      if 'topic_subscription' in worker_config:
        self._mqtt_callbacks.append((
          worker_config['topic_subscription'],
          partial(self._on_command_wrapper, worker_obj)
        ))

    if 'topic_subscription' in config:
      for (callback_name, options) in config['topic_subscription'].items():
        self._mqtt_callbacks.append((
          options['topic'],
          lambda client, _ , c: self._queue_if_matching_payload(self.Command(getattr(self, callback_name)), c.payload, options['payload']))
        )

    return self

  def start(self, mqtt):
    mqtt.callbacks_subscription(self._mqtt_callbacks)
    self._scheduler.start()
    self.update_all()
    for daemon in self._daemons:
      threading.Thread(target=daemon.run, args=[mqtt], daemon=True).start()

  def _queue_if_matching_payload(self, command, payload, expected_payload):
    if payload.decode('utf-8') == expected_payload:
      self._queue_command(command)

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
      pip_main(['install', '-q', package])

  def _on_command_wrapper(self, worker_obj, client, userdata, c):
    _LOGGER.debug("on command wrapper for with %s: %s", c.topic, c.payload)
    global_topic_prefix = userdata['global_topic_prefix']
    topic = c.topic[len(global_topic_prefix+'/'):] if global_topic_prefix is not None else c.topic
    self._queue_command(self.Command(worker_obj.on_command, [topic, c.payload]))
