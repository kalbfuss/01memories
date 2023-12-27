"""Module for rclone repositories."""

import logging
import repository
import tempfile

from rclone_python import rclone
from repository import ConfigError, IoError, check_param, check_valid_required

from .file import RepositoryFile


class Repository(repository.Repository):
    """Repository with rclone file base.

    The rclone repository class currently does not provide any functionality
    to configure rclone remotes. Remotes must have been configured before in
    the rclone configuration file, e.g. by using the *rclone config* command.

    The root directory needs to include the rclone remote (e.g.
    "owncloud:<myroot>").
    """

    # Required and valid configuration parameters
    CONF_REQ_KEYS = {'root', 'cache'}
    CONF_VALID_KEYS = set() | CONF_REQ_KEYS

    def __init__(self, uuid, config, index=None):
        """Initialize the repository.

        :param uuid: UUID of repository
        :type name: str
        :param config: dictionary with repository configuration
        :type config: dict
        :param index: optional file metadata index. Default is None.
        :type index: repository.Index
        :raises: repository.UuidError, repository.ConfigError
        """
        # Call constructor of parent class.
        repository.Repository.__init__(self, uuid, config, index)
        # Basic initialization.
        self._root = config.get('root', "/")
        # Create temporary directory for file caching.
        self._cache_dir = tempfile.TemporaryDirectory(dir=config['cache'], prefix=f"{uuid}-")

    def _check_config(self, config):
        """Check the repository configuration.

        :param config:
        :type config: dict
        :raises: repository.ConfigError
        """
        # Make sure all valid and required parameters have been specified.
        check_valid_required(config, self.CONF_VALID_KEYS, self.CONF_REQ_KEYS)
        # Check parameter values.
        check_param('root', config, is_str=True)
        check_param('cache', config, is_str=True)

    @property
    def cache_dir(self):
        """Return path of cache directory for the temporary storage of files.

        :return: path of cache directory
        :rtype: str
        """
        return self._cache_dir.name

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

        Raises an IoError if the file with UUID does not exist/cannot be
        accessed.

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
        :raises: repository.IoError
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
    """Iterator to traverse through files in an rclone repository."""

    def __init__(self, rep, index_lookup=True, extract_metadata=True):
        """Initialize file iterator.

        :param rep: rclone repository
        :type rep: repository.rclone.Repository
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

        # Create iterator for list of files in root directory.
        try:
            # The default max_depth of rclone is 1. A value of 0 menas no limit,
            # but is not passed on by the wrapper. As workaround we specify a
            # reasonably high number.
            self._file_list = rclone.ls(f"'{rep.root}'", max_depth=1000)
        except Exception as e:
            raise IoError(f"An exception occurred while listing the root directory. {e}", e)
        self._iterator = iter(self._file_list)

    def __next__(self):
        """Provide next file in iteration.

        :returns: next file
        :rtype: repository.rclone.RepositoryFile
        :raises: StopIteration
        """
        # Retrieve the next directory entry.
        entry = self._iterator.__next__()
        # Skip all directories.
        while entry['IsDir']:
            logging.debug(f"Skipping directory '{entry['Path']}'.")
            # Save all sub-directories for later.
            entry = self._iterator.__next__()

        # Derive uuid from path.
        uuid = entry['Path']
        # Return the next file.
        logging.debug(f"Creating rclone repository file '{uuid}'.")
        return self._rep.file_by_uuid(uuid, self._index_lookup, self._extract_metadata)
