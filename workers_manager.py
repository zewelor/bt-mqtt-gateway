import importlib
import inspect
import threading
from functools import partial

from apscheduler.schedulers.background import BackgroundScheduler
from interruptingcow import timeout
from pytz import utc

from const import DEFAULT_COMMAND_TIMEOUT, DEFAULT_COMMAND_RETRIES, DEFAULT_UPDATE_RETRIES
from exceptions import WorkerTimeoutError
from workers_queue import _WORKERS_QUEUE
import logger

_LOGGER = logger.get(__name__)


class WorkersManager:
    class Command:
        def __init__(self, callback, timeout, args=(), options=dict()):
            self._callback = callback
            self._timeout = timeout
            self._args = args
            self._options = options
            self._source = "{}.{}".format(
                callback.__self__.__class__.__name__
                if hasattr(callback, "__self__")
                else callback.__module__,
                callback.__name__,
            )

        def execute(self):
            messages = []

            try:
                with timeout(
                        self._timeout,
                        exception=WorkerTimeoutError(
                            "Execution of command {} timed out after {} seconds".format(
                                self._source, self._timeout
                            )
                        ),
                ):
                    if inspect.isgeneratorfunction(self._callback):
                        for message in self._callback(*self._args):
                            messages += message
                    else:
                        messages = self._callback(*self._args)
            except WorkerTimeoutError as e:
                if messages:
                    logger.log_exception(
                        _LOGGER, "%s, sending only partial update", e, suppress=True
                    )
                else:
                    raise e

            _LOGGER.debug("Execution result of command %s: %s", self._source, messages)
            return messages

    def __init__(self, config, mqtt_config):
        self._mqtt_callbacks = []
        self._config_commands = []
        self._update_commands = []
        self._scheduler = BackgroundScheduler(timezone=utc)
        self._daemons = []
        self._config = config
        self._command_timeout = config.get("command_timeout", DEFAULT_COMMAND_TIMEOUT)
        self._command_retries = config.get("command_retries", DEFAULT_COMMAND_RETRIES)
        self._update_retries = config.get("update_retries", DEFAULT_UPDATE_RETRIES)
        self._mqtt = mqtt_config

    def register_workers(self, global_topic_prefix):
        for (worker_name, worker_config) in self._config["workers"].items():
            module_obj = importlib.import_module("workers.%s" % worker_name)
            klass = getattr(module_obj, "%sWorker" % worker_name.title())

            command_timeout = worker_config.get(
                "command_timeout", self._command_timeout
            )
            command_retries = worker_config.get(
                "command_retries", self._command_retries
            )
            update_retries = worker_config.get(
                "update_retries", self._update_retries
            )
            worker_obj = klass(
                command_timeout, command_retries, update_retries, global_topic_prefix, **worker_config["args"]
            )

            if "sensor_config" in self._config and hasattr(worker_obj, "config"):
                _LOGGER.debug(
                    "Added %s config with a %d seconds timeout", repr(worker_obj), 2
                )
                command = self.Command(worker_obj.config, 2, [self._mqtt.availability_topic])
                self._config_commands.append(command)

            if hasattr(worker_obj, "status_update"):
                _LOGGER.debug(
                    "Added %s worker with %d seconds interval and a %d seconds timeout",
                    repr(worker_obj),
                    worker_config["update_interval"],
                    worker_obj.command_timeout,
                )
                command = self.Command(
                    worker_obj.status_update, worker_obj.command_timeout, []
                )
                self._update_commands.append(command)

                if "update_interval" in worker_config:
                    job_id = "{}_interval_job".format(worker_name)
                    self._scheduler.add_job(
                        partial(self._queue_command, command),
                        "interval",
                        seconds=worker_config["update_interval"],
                        id=job_id,
                    )
                    self._mqtt_callbacks.append(
                        (
                            worker_obj.format_topic("update_interval"),
                            partial(self._update_interval_wrapper, command, job_id),
                        )
                    )
            elif hasattr(worker_obj, "run"):
                _LOGGER.debug("Registered %s as daemon", repr(worker_obj))
                self._daemons.append(worker_obj)
            else:
                raise "%s cannot be initialized, it has to define run or status_update method" % worker_name

            if "topic_subscription" in worker_config:
                self._mqtt_callbacks.append(
                    (
                        worker_config["topic_subscription"],
                        partial(self._on_command_wrapper, worker_obj),
                    )
                )

        if "topic_subscription" in self._config:
            for (callback_name, options) in self._config["topic_subscription"].items():
                self._mqtt_callbacks.append(
                    (
                        options["topic"],
                        lambda client, _, c: self._queue_if_matching_payload(
                            self.Command(
                                getattr(self, callback_name), self._command_timeout
                            ),
                            c.payload,
                            options["payload"],
                        ),
                    )
                )

    def start(self):
        self._mqtt.callbacks_subscription(self._mqtt_callbacks)

        if "sensor_config" in self._config:
            self._publish_config()

        self._scheduler.start()
        self.update_all()
        for daemon in self._daemons:
            threading.Thread(target=daemon.run, args=[self._mqtt], daemon=True).start()

    def _queue_if_matching_payload(self, command, payload, expected_payload):
        if payload.decode("utf-8") == expected_payload:
            self._queue_command(command)

    def update_all(self):
        _LOGGER.debug("Updating all workers")
        for command in self._update_commands:
            self._queue_command(command)

    @staticmethod
    def _queue_command(command):
        _WORKERS_QUEUE.put(command)

    def _update_interval_wrapper(self, command, job_id, client, userdata, c):
        _LOGGER.info("Recieved updated interval for %s with: %s", c.topic, c.payload)
        try:
            new_interval = int(c.payload)
            self._scheduler.remove_job(job_id)
            self._scheduler.add_job(
                partial(self._queue_command, command),
                "interval",
                seconds=new_interval,
                id=job_id,
            )
        except ValueError:
            logger.log_exception(
                _LOGGER, "Ignoring invalid new interval: %s", c.payload
            )

    def _on_command_wrapper(self, worker_obj, client, userdata, c):
        _LOGGER.debug(
            "Received command for %s on %s: %s", repr(worker_obj), c.topic, c.payload
        )
        global_topic_prefix = userdata["global_topic_prefix"]
        topic = (
            c.topic[len(global_topic_prefix + "/"):]
            if global_topic_prefix is not None
            else c.topic
        )
        self._queue_command(
            self.Command(
                worker_obj.on_command, worker_obj.command_timeout, [topic, c.payload]
            )
        )

    def _publish_config(self):
        for command in self._config_commands:
            messages = command.execute()
            for msg in messages:
                msg.topic = "{}/{}".format(
                    self._config["sensor_config"].get("topic", "homeassistant"),
                    msg.topic,
                )
                msg.retain = self._config["sensor_config"].get("retain", True)
            self._mqtt.publish(messages)
