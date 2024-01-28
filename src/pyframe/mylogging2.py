"""Module providing pyframe log handler.

+++ OBSOLETE +++ OBSOLETE +++ OBSOLETE +++ OBSOLETE +++ OBSOLETE +++

This module is obsolete and no longer removed. It will be removed in the near
future. Do not use any longer.
"""

import logging
import os
import threading

from logging.handlers import TimedRotatingFileHandler


class Formatter(logging.Formatter):
    """Pyframe log formatter."""

    def __init__(self, *args):
        super().__init__(*args)

    def format(self, record):
        """Apply terminal color code to the record"""
        # deepcopy so we do not mess up the record for other formatters
        try:
            msg = record.msg.split(':', 1)
            if len(msg) == 2:
                record.msg = '[%-13s]%s' % (msg[0], msg[1])
        except:
            pass
        return super().format(record)


class Handler(logging.Handler):
    """Pyframe log handler.

    Writes log messages from selected (background) threads to rotating log
    files. Used to separate messages generated during indexing in the background
    from foreground log messages.
    Threads are identified by their names. The handler creates one log file per
    thread. The name of the log file is identical to the name of the thread plus
    the suffix ".log".
    Log files are rotated once per day and a maximum of 5+1 log files is kept.
    """

    def __init__(self, dir_name, thread_names):
        """Initialize IndexLogHandler instance.

        :param dir_name: Directory for the log files (path). The path must be
          writable. The directory is created if it does not exist.
        :type dir_name: str
        :param thread_name: Name of the threads for wich log messages shall be
          redirected to a rotating log file.
        :type thread_names: list of str or str (single thread)
        :raises: Raises an exception if the directory cannot be created or is
          not writable.
        """
        super().__init__()
        self._handlers = dict()

        # Create log directory if it does not exist yet.
        if not os.path.exists(dir_name):
            try:
                os.makedirs(dir_name, exist_ok=True)
            except Exception as e:
                raise Exception(f"An exception occurred while creating the log directory '{dir_name}': {e}")

        # Make sure the directory is writable.
        if not os.access(dir_name, os.W_OK):
            raise Exception(f"The log directory '{dir_name}' is not writeable.")

        # Convert thread_names to list if only single thread name specified.
        if type(thread_names) == str:
            thread_names = [thread_names]

        # Create one rotating file handler per specified thread.
        formatter = Formatter("%(asctime)s [%(levelname)-8s] %(message)s", "%Y-%m-%d %H:%M:%S")
        for name in thread_names:
            self._handlers[name] = TimedRotatingFileHandler(os.path.join(dir_name, f"{name}.log"), when="h", interval=24, backupCount=5)
            self._handlers[name].setFormatter(formatter)
        # Create default rotating file handler and associate with name of main
        # thread.
        name = threading.main_thread().name
        self._handlers[name] = TimedRotatingFileHandler(os.path.join(dir_name, f"pyframe.log"), when="h", interval=24, backupCount=5)
        self._handlers[name].setFormatter(formatter)

    def emit(self, record):
        """Log the specified logging record."""
        # Get name of current thread.
        name = threading.current_thread().name
        # Use default handler if no specific handler available.
        if name not in self._handlers:
            name = threading.main_thread().name
        # Emit log message using specific handler.
        try:
            self._handlers[name].emit(record)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

    def flush(self):
        "Ensure all logging output has been flushed."
        name = threading.current_thread().name
        if name in self._handlers:
            self._handlers[name].flush()

    def setFormatter(self, formatter):
        "Set the formatter for this handler."
        self.acquire()
        for name, handler in self._handlers.items():
            handler.setFormatter(formatter)
        self.release()

    def setPrefix(self, *args):
        """Set a message prefix.

        The prefix is cleared if the message is called without arguments or an
        empty string is provided.
        :param *args: Message prefix
        :type *args: str
        """
        # Clear prefix if no argument specified or empty string.
        if len(args) == 0 or args[0] == "":
            fmt_str = f"%(asctime)s %(message)s"
        # Set message prefix.
        else:
            fmt_str = f"%(asctime)s [{args[0]}] %(message)s"
        formatter = Formatter(fmt_str, "%Y-%m-%d %H:%M:%S")
        self.setFormatter(formatter)
