#!/usr/bin/env python3
"""Gunicorn entrypoint exposing Flask `app` from `oanda_bot`.

Start with: `gunicorn main:app`
"""

from oanda_bot import app


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
