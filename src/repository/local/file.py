"""Module for local repository files."""

import logging
import os.path
import repository

from repository import UuidError
from datetime import datetime


class RepositoryFile(repository.RepositoryFile):
    """File within a local repository.

    For images, the following properties are extracted from EXIF/IPTC tags if
    available: width, height, rotation, creation_date, description, rating, GPS
    coordinates, and tags (keywords).

    See repository.File for documentation of properties.
    """

    def __init__(self, uuid, rep, index=None, index_lookup=True, extract_metadata=True):
        """Initialize the repository file.

        :param rep: local repository
        :type rep: repository.local.Repository
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

        # Throw exception if file does not exist.
        self._path = os.path.join(rep.root, uuid)
        if not os.path.isfile(self._path):
            raise UuidError("There is no file with UUID '{uuid}'.", uuid)

        # Set file name from uuid.
        self._name = os.path.basename(uuid)

        # Determine last modification and file creation date.
        last_modified = datetime.fromtimestamp(os.path.getmtime(self._path))
        if not self._in_index or self.last_updated < last_modified:
            self._last_modified = last_modified
            self._creation_date = datetime.fromtimestamp(os.path.getctime(self._path))

        # Attempt to extract metadata from file content.
        if (not self._in_index or self.last_updated < last_modified) and extract_metadata:
            self.extract_metadata()

    def extract_metadata(self):
        """Extract metadata from file content."""
        logging.debug(f"Extracting metadata of file '{self.uuid}' from file content.")
        # If image try to extract metadata from EXIF tag.
        if self._type == repository.RepositoryFile.TYPE_IMAGE:
            self._extract_image_metadata(self._path)
        elif self._type == repository.RepositoryFile.TYPE_VIDEO:
            self._extract_video_metadata(self._path)

    @property
    def source(self):
        """Return full path of the file.

        :return: full path
        :rtype: str
        """
        return self._path
