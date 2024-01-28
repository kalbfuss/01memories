"""Module providing meta data background indexer.

+++ OBSOLETE +++ OBSOLETE +++ OBSOLETE +++ OBSOLETE +++ OBSOLETE +++

This module is obsolete and no longer removed. It will be removed in the near
future. Do not use any longer.
"""

import logging

from repository import IoError
from threading import Thread
from time import asctime, localtime, mktime, time, sleep

from kivy.logger import Logger


class RepData:
    """Repository data structure.

    Used by the Idexer class to store information about queued repositories.
    """

    def __init__(self, interval=0, at=None):
        """Initialize RepData instance.

        : param interval: Index update interval in hours
        : type interval: int
        """
        self.interval = interval
        # Convert time string to numeric array.
        if at is not None:
            self.at = [int(s) for s in at.split(":")]
        else:
            self.at = None
        self.last = 0
        self.next = 0
        self.update_next()

    def update_next(self, last=None):
        """Returns ..."""
        # Update time of last run if specified.
        if last is not None:
            self.last = last
        # Determine time of next run.
        if self.at is not None:
            lt = localtime()
            offset = 0
            if self.at[0] < lt.tm_hour or (self.at[0] == lt.tm_hour and self.at[1] <= lt.tm_min):
                offset = 24*3600
            nt = (lt[0], lt[1], lt[2], self.at[0], self.at[1], 0, lt[6], lt[7], lt[8])
            self.next = offset + mktime(nt)
        elif self.last == 0:
            self.next = time()
        elif self.last > 0 and self.interval > 0:
            self.next = self.last + self.interval*3600
        else:
            self.next = 0


class Indexer:
    """Meta data background indexer.

    Used by the pyframe application to build the meta data index for active
    repositories in the background. The index is built using the
    repository.Index class.
    The index is built at least once for all queued repositories. If
    an update interval or time is specified, the index is built periodically
    for the respective repository.
    The class uses a special log handler IndexerLogHandler to redirect log
    messages from the background thread to a rotated log file.
    """

    def __init__(self, index):
        """Initialize Indexer instance.

        : param index: The index instance used to build the meta data index.
        : type index: repository.Index
        """
        self._rep_data = dict()
        self._thread = None
        self._index = index

    def _build(self):
        """Build meta data index for queued repositories.

        The method is executed in a background thread. The background thread
        is created and started by the start method. The _build method runs
        infinitely or until the queue of repositories is empty.
        """

        def format_duration(duration):
            """Helper function to format duration string.

            : param duration: Duration in seconds
            : type duration: int
            : return: Duration and unit as formatted string
            : rtype: str
            """
            if duration > 3600:
                duration_str = f"{duration/3600:.1f} hours"
            elif duration > 60:
                duration_str = f"{duration/60:.1f} minutes"
            else:
                duration_str = f"{duration:.1f} seconds"
            return duration_str

        pause_until = 0
        logging.info("Starting to build meta data index in the background.")

        while True:
            # Iterate through repositories, which have been queued for indexing.
            for rep in list(self._rep_data.keys()):

                cur_time = time()
                data = self._rep_data[rep]

                # Build index for repository if due, but at least once.
                if data.next < cur_time:
                    # Build meta data index for current repository.
                    try:
                        self._index.build(rep)
                    except IoError as e:
                        logging.error(f"An I/O error occurred while indexing the repository: {e.exception}")
                    # Log duration of indexing run.
                    end_time = time()
                    duration = (end_time - cur_time)
                    logging.info(f"Indexing of repository '{rep.uuid}' completed after {format_duration(duration)}.")
                    # Record completion time and update time for next indexing
                    # run.
                    data.update_next(end_time)
                    if data.next > 0:
                        # Log time of next indexing run.
                        logging.info(f"The next indexing run is due at {asctime(localtime(data.next))}.")
                    else:
                        logging.info(f"Removing repository '{rep.uuid}' from queue.")
                        self._rep_data.pop(rep)

                if pause_until == 0 or (data.next > 0 and data.next < pause_until):
                    pause_until = data.next

            # Stop building index if there are no more repositories queued.
            if len(self._rep_data) == 0:
                logging.info(f"Stopping to build meta data index in the background.")
                return

            # If necessary, sleep until next repository is due for indexing.
            cur_time = time()
            if pause_until > cur_time:
                # Log duration until next indexing run is due.
                duration = (pause_until - cur_time)
                pause_until = 0
                logging.info(f"Sleeping for {format_duration(duration)}.")
                sleep(duration)

    def queue(self, rep, interval=0, at=None):
        """Queue repositories for indexing.

        Repositories must be queued prior to starting index creation. It is not
        safe to queue repositories after index creation has been started.

        : param rep: Repository to be queued for indexing.
        : type rep: repository.RepositoryFile
        : param interval: Index update interval in hours. No value or a value of
          zero means that the index is created only once after start up.
        : type interval: int
        """
        Logger.info(f"Indexer: Queuing repository '{rep.uuid}' for indexing of meta data.")
        self._rep_data[rep] = RepData(interval, at)

    def start(self):
        """Start index creation in the background.

        Creates a background thread, which executes the _build method.
        Repositories must have been queued before. It is not safe to queue
        repositories after index creation has been started.
        """
        Logger.info(f"Indexer: Starting to build meata data index in the background.")
        self._thread = Thread(name="indexer", target=self._build, daemon=True)
        self._thread.start()
