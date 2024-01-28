"""Module for local repositories."""

import os
import os.path
import logging
import repository

from repository import ConfigError, IoError, check_param, check_valid_required

from .file import RepositoryFile


class Repository(repository.Repository):
    """Repository with local file base."""

    # Required and valid configuration parameters
    CONF_REQ_KEYS = {'root'}
    CONF_VALID_KEYS = set() | CONF_REQ_KEYS

    def __init__(self, uuid, config, index=None):
        """Initialize the repository.

        :param uuid: UUID of repository
        :type name: str
        :param config: dictionary with repository configuration
        :type config: dict
        :param index: Optional file metadata index. Default is None.
        :type index: repository.Index
        :raises: repository.UuidError, repository.ConfigError
        """
        # Call constructor of parent class.
        repository.Repository.__init__(self, uuid, config, index)
        # Basic initialization.
        self._root = config['root']

    def _check_config(self, config):
        """Check the repository configuration.

        :param config:
        :type config: dict
        :raises: repository.ConfigError
        """
        # Make sure valid and required parameters have been specified.
        check_valid_required(config, self.CONF_VALID_KEYS, self.CONF_REQ_KEYS)
        # Check parameter values.
        check_param('root', config, is_str=True)

    def iterator(self, index_lookup=True, extract_metadata=True):
        """Provide iterator to traverse through files in the repository.

        :param index_lookup: Flag indicating whether file metadata shall be
            looked up from index. Default is True.
        :type index_lookup: bool
        :param extract_metadata: Flag indicating whether file metadata shall be
            extracted from file if not available from index. Default is True.
        :type extract_metadata: bool
        :return: file iterator
        :return type: repository.FileIterator
        """
        return FileIterator(self, index_lookup, extract_metadata)

    def file_by_uuid(self, uuid, index_lookup=True, extract_metadata=True):
        """Return file within the repository by its UUID.

        Raises a UuidError if the file with UUID does not exist. And raises an
        IoError if the file cannot be accessed.

        :param uuid: UUID of repository file
        :type uuid: str
        :param index_lookup: Flag indicating whether file metadata shall be
            looked up from index. Default is True.
        :type index_lookup: bool
        :param extract_metadata: Flag indicating whether file metadata shall be
            extracted from file if not available from index. Default is True.
        :type extract_metadata: bool
        :return: file with matching UUID
        :rtype: repository.RepositoryFile
        :raises: repository.UuidError, repository.IoError
        """
        return RepositoryFile(uuid, self, self._index, index_lookup, extract_metadata)

    @property
    def root(self):
        """Return root directory of the repository.

        :return: root directory
        :rtype: str
        """
        return self._root


class FileIterator(repository.FileIterator):
    """Iterator to traverse through files in a local repository."""

    def __init__(self, rep, index_lookup=True, extract_metadata=True):
        """Initialize file iterator.

        :param rep: local repository
        :type rep: repository.local.Repository
        :param index_lookup: Flag indicating whether file metadata shall be
            looked up from index. Default is True.
        :type index_lookup: bool
        :param extract_metadata: Flag indicating whether file metadata shall be
            extracted from file if not available from index. Default is True.
        :type extract_metadata: bool
        :raises: repository.IoError
        """
        # Basic initialization.
        self._rep = rep
        self._index_lookup = index_lookup
        self._extract_metadata = extract_metadata
        self._dir_list = []
        # Create scandir iterator for provided root directory.
        try:
            self._iterator = os.scandir(self._rep.root)
        except Exception as e:
            raise IoError(f"An exception occurred while scanning the root directory. {e}.", e)

    def __next__(self):
        """Provide next file in iteration.

        :returns: next file
        :rtype: repository.rclone.RepositoryFile
        :raises: StopIteration
        """
        try:
            # Retrieve the next directory entry.
            entry = self._iterator.__next__()
            # Continue to retrieve entries if not a file.
            while not entry.is_file():
                # Save all sub-directories for later.
                if entry.is_dir():
                    self._dir_list.append(entry.path)
                entry = self._iterator.__next__()

            # Construct relative path to root directory of the repository.
            uuid = os.path.relpath(entry.path, start=self._rep.root)
            # Return the next file.
            logging.debug(f"Instantiating local repository file '{uuid}'.")
            return self._rep.file_by_uuid(uuid, self._index_lookup, self._extract_metadata)

        except StopIteration:
            if len(self._dir_list) > 0:
                # Start all over with first subdirectory in the list.
                try:
                    dir = self._dir_list.pop()
                    self._iterator = os.scandir(dir)
                except Exception as e:
                    raise IoError(f"An exception occurred while scanning directory '{dir}'. {e}", e)
                return self.__next__()
            else:
                # Raise exception to indicate end of iteration otherwise
                raise StopIteration
