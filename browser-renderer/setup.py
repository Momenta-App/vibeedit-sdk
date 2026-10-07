#!/usr/bin/env python3
"""Use the same explicit setup entry point as an installed wheel."""
from vibeedit.browser_setup import setup_cef
import json

if __name__ == "__main__":
    print(json.dumps(setup_cef(), indent=2))
