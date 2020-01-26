import yaml
import os
import sys

with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.yaml"), "r") as f:
    settings = yaml.safe_load(f)
