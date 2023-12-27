"""Module providing repository class"""

import logging

from abc import ABC, abstractmethod

from .common import ConfigError, UuidError


class Repository(ABC):
    """Repository of files.

    Abstract base class providing basic functionality common to all Repository
    sub-classes.
    """

    # Maximum length of uuid
    MAX_LEN_UUID = 36
    # Dictionary of all repositories by uuid
    _repositories = dict()

    # Required and valid configuration parameters. Need to be re-defined by
    # implementing sub-class.
    CONF_REQ_KEYS = {}
    CONF_VALID_KEYS = {}

    def __init__(self, uuid, config, index=None):
        """Initialize the repository.

        :param uuid: UUID of the repository.
        :type uuid: str
        :param config: Repository configuration from the configuration file.
        :type config: dict
        :param index: Optional file metadata index. Default is None.
        :type index: repository.Index
        :raises: UuidError
        """
        # Basic intialization.
        self._uuid = uuid
        self._index = index

        # Check the configuration for errors.
        self._check_config(config)

        # Test uuid for validity.
        if len(uuid) >= Repository.MAX_LEN_UUID:
            raise UuidError(f"UUID for repository too long. Maximum of {Repository.MAX_LEN_UUID} characters allowed.", uuid)
        # Warn if uuid already in use, but do not throw execption.
        if uuid in Repository._repositories:
            logging.warn(f"UUID for repository '{uuid}' is already in use.")

        # Add self to dictionary of repositories.
        Repository._repositories[uuid] = self

    def __del__(self):
        """Delete the repository."""
        if self.uuid in Repository._repositories:
            del Repository._repositories[self.uuid]

    @abstractmethod
    def iterator(self, index_lookup=True, extract_meta_data=True):
        """Provide iterator which allows to traverse through all files in the repository.

        :param index_lookup: True if file metadata shall be looked up from index.
        :type index_lookup: bool
        :return: File iterator.
        :return type: repository.FileIterator
        """
        pass

    def __iter__(self):
        """Provide iterator which allows to traverse through all files in the repository.

        :return: file iterator
        :return type: repository.FileIterator
        """
        return self.iterator()

    @abstractmethod
    def _check_config(self, config):
        """Check the configuration for the repository from the configuration
        file. This method is abstract and needs to be implemented by child
        classes.

        :param config: repository configuration
        :type config: dict
        :raises: ConfigError
        """
        pass

    @staticmethod
    def by_uuid(uuid):
        """Return an existing repository instance by its UUID. Raises a
        UuidError if no repository with the specified UUID exists.

        :param uuid: UUID of the repository.
        :type uuid: str
        :return: Repository with matching UUID.
        :rtype: repository.Repository
        :raises: UuidError
        """
        if uuid in Repository._repositories:
            return Repository._repositories[uuid]
        else:
            raise UuidError(f"There is no repository with UUID '{uuid}'", uuid)

    @abstractmethod
    def file_by_uuid(self, uuid, index_lookup=True, extract_metadata=True):
        """Return a file within the repository by its UUID. Raises a UuidError
        if the repository does not contain a file with the specified UUID.

        :param uuid: UUID of the file.
        :type uuid: str
        :param index_lookup: True if metadata shall be looked up from index.
        :type index_lookup: bool
        :param extract_metadata: True if metadata shall be extracted from the
          file if not available from the index.
        :type extract_metadata: bool
        :return: File with matching UUID.
        :rtype: repository.RepositoryFile
        :raises: UuidError
        """
        pass

    @property
    def index(self):
        """Return metadata index of the repository.

        :return: Metadata index of the repository. May return None if no index
            was specified.
        :rtype: repository.Index
        """
        return self._index

    @index.setter
    def index(self, index):
        """Set metadata index of the repository.

        :param index: Metadata index of the repository.
        :type index: repository.Index
        """
        self._index = index

    @staticmethod
    def repositories():
        """Return set of UUIDs of existing repositories.

        :return: UUIDs of existing repositories.
        :rtype: set
        """
        return set(Repository._repositories.keys())

    @property
    def uuid(self):
        """Return UUID of the repository.

        :return: UUID of repository.
        :rtype: str
        """
        return self._uuid


class FileIterator:
    """Iterator which can be used to traverse through files in a repository."""

    @abstractmethod
    def __next__(self):
        """Provide the next file.

        :returns: Next file in the repository.
        :rtype: repository.RepositoryFile
        :raises: StopIteration
        """
        pass

    def __iter__(self):
        """Provide self as iterator for traversing through all files in the
        repository.

        Enables the Repository.iterator method to create iterators with
        additional arguments.

        :return: File iterator.
        :return type: repository.FileIterator
        """
        return self
