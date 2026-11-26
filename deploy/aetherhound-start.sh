#!/bin/sh
set -eu
cd /opt/aetherhound
exec .venv/bin/python -m aetherhound.scripts.virtual_sdr_demo --backend python --seconds 86400
