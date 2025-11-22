#!/usr/bin/env python3
"""Entrypoint module that exposes the Flask `app` for Gunicorn.

Gunicorn start command should reference this as `gunicorn main:app`.
"""

from oanda_bot import app


if __name__ == "__main__":
    # Local development server
    app.run(host="0.0.0.0", port=5000)
