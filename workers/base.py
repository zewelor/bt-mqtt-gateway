class BaseWorker:
  def __init__(self, **args):
    for arg, value in args.items():
      setattr(self, arg, value)
    self._setup()

  def _setup(self):
    return

  def format_topic(self, *args):
    return '/'.join([self.topic_prefix, *args])
