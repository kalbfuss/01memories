"""Module for WebDAV repositories."""

import logging
import repository
import tempfile

from repository import ConfigError, IoError, check_param, check_valid_required
from webdav3.client import Client

from .file import RepositoryFile


class Repository(repository.Repository):
    """Repository with WebDAV file base."""

    # Required and valid configuration parameters
    CONF_REQ_KEYS = {'url', 'user', 'password', 'cache'}
    CONF_VALID_KEYS = {'root'} | CONF_REQ_KEYS

    def __init__(self, uuid, config, index=None):
        """Initialize the repository.

        :param uuid: UUID of repository
        :type name: str
        :param index: Optional file metadata index. Default is None.
        :type index: repository.Index
        :param config: Dictionary with repository Configuration
        :type config: dict
        :raises: repository.UuidError, repository.ConfigError
        """
        # Call constructor of parent class.
        repository.Repository.__init__(self, uuid, config, index)

        # Basic initialization.
        self._url = config['url']
        self._user = config['user']
        self._password = config['password']
        self._root = config.get('root', "/")

        # Create temporary directory for file caching.
        self._cache_dir = tempfile.TemporaryDirectory(dir=config['cache'], prefix=f"{uuid}-")

        # Open WebDav client session.
        options = {
         'webdav_hostname': self._url,
         'webdav_login':    self._user,
         'webdav_password': self._password
        }
        self._client = Client(options)

    def _check_config(self, config):
        """Check the repository configuration.

        :param config:
        :type config: dict
        :raises: repository.ConfigError
        """
        # Make sure all valid and required parameters have been specified.
        check_valid_required(config, self.CONF_VALID_KEYS, self.CONF_REQ_KEYS)
        # Check parameter values.
        check_param('url', config, is_str=True)
        check_param('user', config, is_str=True)
        check_param('password', config, is_str=True)
        check_param('cache', config, is_str=True)

    @property
    def cache_dir(self):
        """Return path of cache directory for the temporary storage of files.

        :return: path of cache directory
        :rtype: str
        """
        return self._cache_dir.name

    @property
    def client(self):
        """Return WebDAV client session of the repository.

        :return: WebDAV client session
        :rtype: webdav3.client.Client
        """
        return self._client

    @property
    def root(self):
        """Return WebDAV root directory of the repository.

        :return: WebDav root directory
        :rtype: str
        """
        return self._root

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

        :param uuid: UUID of file
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


class FileIterator(repository.FileIterator):
    """Iterator which can be used to traverse through files in a webdav repository."""

    def __init__(self, rep, index_lookup=True, extract_metadata=True):
        """Initialize file iterator.

        :param rep: WebDAV repository
        :type rep: repository.webdav.repository
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

        # Create iterator for list of root directory.
        try:
            self._file_list = rep.client.list(rep.root, get_info=True)
        except Exception as e:
            raise IoError(f"An exception occurred while listing the root directory. {e}", e)
        self._iterator = iter(self._file_list)

    def __next__(self):
        """Provide next file in iteration.

        :returns: next file
        :rtype: repository.webdav.RepositoryFile
        :raises: StopIteration
        """
        try:
            # Retrieve the next directory entry.
            entry = self._iterator.__next__()
            # Continue to retrieve entries if not a file.
            while entry['isdir']:
                # Save all sub-directories for later.
                self._dir_list.append(entry['path'])
                entry = self._iterator.__next__()

            # Construct relative path to root directory of the repository.
            uuid = entry['path']
            # Return the next file.
            logging.debug(f"Creating webdav repository file '{uuid}'.")
            return self._rep.file_by_uuid(uuid, self._index_lookup, self._extract_metadata)

        except StopIteration:
            if len(self._dir_list) > 0:
                # Start all over with last subdirectory in the list
                try:
                    dir = self._dir_list.pop()
                    self._file_list = self._rep.client.list(dir, get_info=True)
                except Exception as e:
                    raise IoError(f"An exception occurred while listing directiory '{dir}'. {e}", e)
                self._iterator = iter(self._file_list)
                return self.__next__()
            else:
                # Raise exception to indicate end of iteration otherwise
                raise StopIteration
