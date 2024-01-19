"""pyframe main module."""

import signal
import time

from kivy.base import stopTouchApp
from kivy.core.window import Window
from kivy.logger import Logger

from .app import App

app = App()

def handler(sig, frame):
    """Close application after SIGINT and SIGTERM signals."""
    Logger.info(f"App: Signal '{signal.strsignal(sig)}' received. Preparing for safe exit.")
    app.close()
    stopTouchApp()


# Catch interrupt and term signals and exit gracefully.
signal.signal(signal.SIGINT, handler)
signal.signal(signal.SIGTERM, handler)
# Run application.
app.run()
app.close()
stopTouchApp()
