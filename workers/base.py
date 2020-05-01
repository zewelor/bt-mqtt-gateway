import logger

class BaseWorker:
    def __init__(self, command_timeout, global_topic_prefix, **kwargs):
        self.command_timeout = command_timeout
        self.global_topic_prefix = global_topic_prefix
        for arg, value in kwargs.items():
            setattr(self, arg, value)
        self._setup()

    def _setup(self):
        return

    def format_discovery_topic(self, mac, *sensor_args):
        node_id = mac.replace(":", "-")
        object_id = "_".join([repr(self), *sensor_args])
        return "{}/{}".format(node_id, object_id)

    def format_discovery_id(self, mac, *sensor_args):
        return "bt-mqtt-gateway/{}".format(
            self.format_discovery_topic(mac, *sensor_args)
        )

    def format_discovery_name(self, *sensor_args):
        return "_".join([repr(self), *sensor_args])

    def format_topic(self, *topic_args):
        return "/".join([self.topic_prefix, *topic_args])

    def format_prefixed_topic(self, *topic_args):
        topic = self.format_topic(*topic_args)
        if self.global_topic_prefix:
            return "{}/{}".format(self.global_topic_prefix, topic)
        return topic

    def __repr__(self):
        return self.__module__.split(".")[-1]

    @staticmethod
    def true_false_to_ha_on_off(true_false):
        if true_false:
            return 'ON'

        return 'OFF'

    def log_update_exception(self, named_logger, dev_name, exception):
        logger.log_exception(
            named_logger,
            "Error during update of %s device '%s': %s",
            repr(self),
            dev_name,
            type(exception).__name__,
            suppress=True,
        )

    def log_timeout_exception(self, named_logger, dev_name):
        logger.log_exception(
            named_logger,
            "Time out during update of %s device '%s'",
            repr(self),
            dev_name,
            suppress=True,
        )

    def log_connect_exception(self, named_logger, dev_name, exception):
        logger.log_exception(
            named_logger,
            "Failed connect from %s to device '%s': %s",
            repr(self),
            dev_name,
            type(exception).__name__,
            suppress=True,
        )

    def log_unspecified_exception(self, named_logger, dev_name, exception):
        logger.log_exception(
            named_logger,
            "Failed btle from %s to device '%s': %s",
            repr(self),
            dev_name,
            type(exception).__name__,
            suppress=True,
        )
