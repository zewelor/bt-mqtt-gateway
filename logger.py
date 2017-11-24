import logging

import sys

_LOGGER = logging.getLogger('bt-mqtt-gw')
_LOGGER.addHandler(logging.StreamHandler(sys.stdout))
