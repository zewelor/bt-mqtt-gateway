import yaml
import os
import sys

with open(os.path.join(sys.path[0], "config.yaml"), "r") as f:
    settings = yaml.safe_load(f)
