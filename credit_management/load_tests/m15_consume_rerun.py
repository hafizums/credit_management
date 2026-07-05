# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import json

from credit_management.load_tests.m15_runner import bulk_consume


def run():
	out = {"1000": bulk_consume(1000), "5000": bulk_consume(5000)}
	return out


if __name__ == "__main__":
	print(json.dumps(run(), default=str, indent=2))