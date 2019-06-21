class BaseWorker:
  def __init__(self, command_timeout, **args):
    self.command_timeout = command_timeout
    for arg, value in args.items():
      setattr(self, arg, value)
    self._setup()

  def _setup(self):
    return

  def format_id(self, *args, separator='/'):
    return separator.join(["bt-mqtt-gateway", repr(self), *args])

  def format_topic(self, *args, separator='/'):
    return separator.join([self.topic_prefix, *args])

  def __repr__(self):
    return self.__module__.split(".")[-1]
