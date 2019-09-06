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
