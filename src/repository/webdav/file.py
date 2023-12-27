"""Module for WebDAV repository files."""

import logging
import os
import os.path
import repository
import tempfile

from datetime import datetime
from repository import IoError, UuidError


class RepositoryFile(repository.RepositoryFile):
    """File within a webdav repository.

    See repository.File for documentation of properties.
    """

    def __init__(self, uuid, rep, index=None, index_lookup=True, extract_metadata=True):
        """Initialize the repository file.

        :param rep: WebDAV repository
        :type rep: repository.webdav.Repository
        :param uuid: UUID of repository file
        :type uuid: str
        :param index: Optional file metadata index. Default is None.
        :type index: repository.Index
        :param index_lookup: Flag indicating whether file metadata shall be
            looked up from index. Default is True.
        :type index_lookup: bool
        :param extract_metadata: Flag indicating whether file metadata shall be
            extracted from file if not available from index. Default is True.
        :type extract_metadata: bool
        :raises: repository.UuidError, repository.IoError
        """
        # Call constructor of parent class.
        super().__init__(uuid, rep, index, index_lookup)

        # Basic initialization.
        self._cache_file = None
        self._path = None

        # Set file name from uuid
        self._name = os.path.basename(uuid)

        # Attempt to determine last modification and file creation date.
        if not self._in_index:
            # Attempt to retrieve file attributes.
            try:
                info = self._rep.client.info(self.uuid)
            except Exception as e:
                raise IoError(f"An exception occurred while retrieving WebDAV file information. {e}", e)
            # Attempt to determine last modified date.
            try:
                modified = info.get('modified')
                last_modified = datetime.strptime(modified, "%a, %d %b %Y %H:%M:%S %Z")
                self._last_modified = last_modified
            except (ValueError, TypeError):
                logging.warn(f"Failed to convert last modified date string '{modified}' to datetime.")
                last_modified = self.last_modified
            # Attempt to determine file creation date.
            try:
                created = info.get('created')
                creation_date = datetime.strptime(created, "%a, %d %b %Y %H:%M:%S %Z")
                self._creation_date = creation_date
            except (ValueError, TypeError):
                logging.warn(f"Failed to convert created date string '{created}' to datetime.")

        # Attempt to extract metadata from file content.
        if not self._in_index and extract_metadata:
            self.extract_metadata()

    def __del__(self):
        """Delete the file."""
        # Close and delete cache file if exists to prevent clean up errors.
        if self._cache_file is not None:
            try:
                self._cache_file.close()
            except FileNotFoundError:
                # Ignore any file not found errors, which can occur if the
                # cache directory and its content are deleted before the
                # temporary file.
                pass

    def _download(self):
        """Download file from WebDAV repository to local cache file.

        :raises: repository.IoError
        """
        if self._cache_file is None:
            # Create temporary file for local caching inside cache directory
            # of the WebDav repository.
            self._cache_file = tempfile.NamedTemporaryFile(dir=self._rep.cache_dir)
            self._path = self._cache_file.name
            logging.debug(f"Local cache file '{self._path}' created.")

            # Download file from WebDav repository.
            logging.info(f"Downloading file '{self.uuid}' from webdav repository to local cache file.")
            try:
                self._rep.client.download_from(self._cache_file, self._uuid)
            except Exception as e:
                raise repository.IoError(f"An exception occurred while downloading file '{self._uuid}' from WebDAV repository. {e}", e)

    def extract_metadata(self):
        """Extract metadata from file content."""
        # Download file if file type is supported.
        if self.type in (repository.RepositoryFile.TYPE_IMAGE, repository.RepositoryFile.TYPE_VIDEO):
            self._download()
        # Attempt to extract metadata from file content.
        logging.debug(f"Extracting metadata of file '{self.uuid}' from file content.")
        if self._type == repository.RepositoryFile.TYPE_IMAGE:
            self._extract_image_metadata(self._path)
        elif self._type == repository.RepositoryFile.TYPE_VIDEO:
            self._download()
            self._extract_video_metadata(self._path)

    @property
    def source(self):
        """Return full path of the local cache file.

        :return: full path
        :rtype: str
        """
        # Make sure to download file before returning path.
        self._download()
        # Return full path to local cache file.
        return self._path
