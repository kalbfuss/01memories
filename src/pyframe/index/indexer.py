"""Module providing Pyframe repository indexer."""

import logging
import os
import signal
import sys

from repository import ConfigError, Index, Repository

from ..common import _create_repositories, _configure_logging, _load_config, _load_index


indexer = None

def signal_handler(sig, frame):
    """Close application after SIGINT and SIGTERM signals."""
    logging.warning(f"Indexer: Signal '{signal.strsignal(sig)}' received. Preparing for safe exit.")
    indexer.close()
    sys.exit(1)


def run_indexer(uuids, rebuild):
    """Run indexer."""
    # Catch interrupt and term signals and exit gracefully.
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    # Run slideshow.
    indexer = Indexer(uuids, rebuild)
    indexer.run()
    # Clean up and exit.
    indexer.close()


class Indexer:
    """Pyframe repository indexer."""


    def __init__(self, uuids, rebuild):
        """Initialize repository indexer instance."""
        # Load configuration.
        self._config = _load_config()
        # Configure logging.
        _configure_logging(self._config, "indexer.log")

        # Load/create index.
        self._index = _load_index(self._config)
        # Create repositories from configuration.
        _create_repositories(self._config, self._index)

        # Assume all repositories shall be indexed if none specified.
        if not uuids: uuids = Repository.repositories()
        # Identify repositories based on uuid.
        self._reps = [ Repository.by_uuid(uuid) for uuid in uuids ]

        # Safe argumenst for later use.
        self._uuids = uuids
        self._rebuild = rebuild


    def run(self):
        """Run indexer."""
        logging.info(f"Indexer: Indexing the following repositories: {[ rep.uuid for rep in self._reps ]}")
        if self._rebuild:
            logging.info(f"Indexer: Index is rebuilt from scratch.")

        # Build index for selected repositories.
        for rep in self._reps:
            self._index.build(rep, rebuild=self._rebuild)


    def close(self):
        """Prepare application for safe exit."""
        # Close metadata index if open.
        if self._index is not None:
            logging.info("Indexer: Closing metadata index.")
            self._index.close()
