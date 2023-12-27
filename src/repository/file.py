""""Module providing repository file class."""

import exifread
import ffmpeg
import fnmatch
import locale
import logging

from abc import ABC, abstractmethod
from datetime import datetime
from geopy.geocoders import Photon
from geopy.exc import GeopyError
from iptcinfo3 import IPTCInfo

from PIL import Image


# Global geolocator instance for reverse location lookups.
geolocator = Photon()

class RepositoryFile:
    """File within a repository.

    Abstract base class providing basic functionality common to all File
    subclasses.

    Properties:
        uuid (str): Universally unique identifier (UUID) of the file. Typically
            the full path of the file within the repository.
        rep (repository.Repository): Repository containing the file.
        name (str): Name of the file. Default is None.
        index (repository.Index): Optional file metadata index. Default is
            None.
        type (int): Type of the file. Default is None. If set the following
            values may be returend:
            TYPE_UNKNOWN: Unknown file type
            TYPE_IMAGE: Image file
            TYPE_VIDEO: Video file
        width (int): Width of the file content in pixels. Default is None.
        height (int): Height of the file content in pixels. Default is None.
        rotation (int): Clock-wise rotation of the content in degrees. Default
            is None. If set the following values may be returned: 0, 90, 180
            or 270.
        orientation (int): Orientation of the content considering rotation.
            Default is None. If set the following values may be returned:
            ORIENTATION_LANDSCAPE: Content wider than high (default)
            ORIENTATION_PORTRAIT: Content heigher than wide
        creation_date (datetime): Creation date of file content.
        last_modified (datetime): Date of last file modification.
        last_updated (datetime): Date of last metadata update.
        description (str): Description of the file content. Default is None.
        rating (int): Rating of the file content. Default is None.
        coordinates (list of float): Geographical coordinates of location [ latitude,
          longitude, altitude ]. Default is [ None, None, None ].
        location (str): Human-readable location (address). Default is None.
        source (str): Source of the file (e.g. full path or URL).
        tags (set of str): User defined tags on the file. Not to be confounded
            with EXIF tags in image files. Default is None.
    """

    # File type definitions
    TYPE_UNKNOWN = 0
    TYPE_IMAGE = 1
    TYPE_VIDEO = 2

    # Orientation definitions
    ORIENTATION_LANDSCAPE = 0
    ORIENTATION_PORTRAIT = 1

    def __init__(self, uuid, rep, index=None, index_lookup=True):
        """Initialize file instance.

        :param uuid: UUID of the file.
        :type uuid: str
        :param rep: Repository containing file
        :type rep: repository.Repository
        :param index: Optional file metadata index. Default is None.
        :param index_lookup: True if file metadata shall be looked up from index.
        :type index_lookup: bool
        :type index: repository.Index
        """
        # Basic initialization.
        self._in_index = False
        self._uuid = uuid
        self._rep = rep
        self._index = index
        self._type = RepositoryFile.TYPE_UNKNOWN
        self._name = str()
        self._width = 0
        self._height = 0
        self._rotation = 0
        self._orientation = RepositoryFile.ORIENTATION_LANDSCAPE
        self._creation_date = datetime.today()
        self._last_modified = datetime.today()
        self._last_updated = datetime.today()
        self._description = str()
        self._rating = None
        self._coordinates = [ None, None, None ]
        self._location = None
        self._tags = list()

        # Attempt to determine type from extension.
        self._type_from_extension()

        # Try to retrieve metadata from index if available.
        mdata = None
        if index is not None and index_lookup is True:
            mdata = index.lookup(self, rep)

        if mdata is not None:
            logging.debug(f"Assigning metadata of file '{self._uuid}' from index.")
            self._in_index = True
            self._type = mdata.type
            self._width = mdata.width
            self._height = mdata.height
            self._rotation = mdata.rotation
            self._orientation = mdata.orientation
            self._creation_date = mdata.creation_date
            self._last_modified = mdata.last_modified
            self._last_updated = mdata.last_updated
            self._description = mdata.description
            self._rating = mdata.rating
            self._coordinates = [ mdata.latitude, mdata.longitude, mdata.altitude ]
            self._tags = [tag.name for tag in mdata.tags]

    def __repr__(self):
        """Provide string representation of file instance.

        :return: String representation
        :rtype: str
        """
        return f"File=(uuid='{self.uuid}', rep=0x{id(self.rep):x}, name={self.name}, type={self.type}, width={self.width}, height={self.height}, rotation={self.rotation}, orientation={self.orientation}, creation_date='{self.creation_date}', description='{self.description}', rating={self.rating}, tags={self.tags})"

    # Extensions of supported files
    EXT_IMAGE = ("*.jpg", "*.jpeg", "*.png")
    EXT_VIDEO = ("*.mp4", "*.mv4", "*.mov")

    def _extract_image_metadata(self, path):
        """Extract image metadata from file content.

        Uses the exifread library to extract EXIF metadata and IPTCInfo3
        library to extract IPTC metadata from the image file. Metadata is
        stored in the corresponding object properties.

        Note the star rating tag is not yet supported by exifread and therefore
        always remains at the default.
        """
        # Save current datetime in property last_updated.
        self._last_updated = datetime.today()

        # Use PIL to determine image size.
        with Image.open(path) as image:
            self._width, self._height = image.size

        # Open image file for reading (binary mode) and extract EXIF information.
        with open(path, 'rb') as file:
            tags = exifread.process_file(file)

        # Obtain rotation from metadata if available
        if 'Image Orientation' in tags:
            orientation = tags['Image Orientation'].values[0]
            if orientation == 8:
                self._rotation = 90
            elif orientation == 3:
                self._rotation = 180
            elif orientation == 6:
                self._rotation = 270

        # Derive orientation from dimensions and rotation.
        if (self._width < self._height and (self.rotation == 0 or self.rotation == 180)) or (self._width > self._height and (self.rotation == 90 or self.rotation == 270)):
            self._orientation = RepositoryFile.ORIENTATION_PORTRAIT
        else:
            self._orientation = RepositoryFile.ORIENTATION_LANDSCAPE

        # Etract image description if available.
        if 'Image ImageDescription' in tags:
            self._description = tags['Image ImageDescription'].values

        # Extract image rating if available.
        if 'Image Rating' in tags:
            self._rating = tags['Image Rating'].values[0]

        # Extract creation date if available.
        try:
            if 'EXIF DateTimeOriginal' in tags:
                creation_date = tags['EXIF DateTimeOriginal'].values
                self._creation_date = datetime.strptime(creation_date, "%Y:%m:%d %H:%M:%S")
            elif 'Image DateTime' in tags:
                creation_date = tags['Image DateTime'].values
                self._creation_date = datetime.strptime(creation_date, "%Y:%m:%d %H:%M:%S")
        except ValueError:
            logging.error(f"Invalid creation time format '{creation_date}'.")

        # Extract latitude and longitude from GPS data.
        if tags.keys() >= {'GPS GPSLatitude', 'GPS GPSLatitudeRef', 'GPS GPSLongitude', 'GPS GPSLongitudeRef'}:
            try:
                # Latitude
                values = tags['GPS GPSLatitude'].values
                latitude = float(values[0] + values[1]/60 + values[2]/3600)
                if tags['GPS GPSLatitudeRef'].values[0] == "S": latitude = -latitude
                self._coordinates[0] = latitude
                # Longitude
                values = tags['GPS GPSLongitude'].values
                longitude = float(values[0] + values[1]/60 + values[2]/3600)
                if tags['GPS GPSLongitudeRef'].values[0] == "W": longitude = -longitude
                self._coordinates[1] = longitude
            except Exception:
                logging.error(f"Invalid format of GPS coodinates.")

        # Extract altitude from GPS data.
        if 'GPS GPSAltitude' in tags:
            altitude = float(tags['GPS GPSAltitude'].values[0])
            self._coordinates[2] = altitude

        # Extract image tags(keywords) from IPTC tag if available
        info = IPTCInfo(path, force=True, inp_charset="utf8")
        self._tags = info["keywords"]

    def _extract_video_metadata(self, path):
        """Extract video metadata from file content.

        Uses the ffmpeg ffprobe command to extract video metadata from the
        video file and stores metadata in corresponding object properties.
        """
        # Save current datetime in property last_updated.
        self._last_updated = datetime.today()

        # Obtain meta data of all streams (video and audio).
        streams = ffmpeg.probe(path)['streams']
        # Find first video stream and return corresponding meta data.
        for data in streams:
            if data.get('codec_type') == 'video': break

        # Try to obtain image dimensions from metadata.
        if data.get('width') is not None:
            self._width = int(data.get('width'))
        if data.get('height') is not None:
            self._height = int(data.get('height'))

        # Stop here if meta data does not contain any tags.
        if data.get('tags') is None: return

        # Try to obtain rotation from metadata.
        rotate = data['tags'].get('rotate')
        if rotate is not None:
            if rotate == "0":
                self._rotation = 0
            elif rotate == "90":
                self._rotation = 270
            elif rotate == "180":
                self._rotation == 180
            elif rotate == "270":
                self._rotation = 90

        # Derive orientation from dimensions and rotation.
        if (self._width < self._height and (self.rotation == 0 or self.rotation == 180)) or (self._width > self._height and (self.rotation == 90 or self.rotation == 270)):
            self._orientation = RepositoryFile.ORIENTATION_PORTRAIT
        else:
            self._orientation = RepositoryFile.ORIENTATION_LANDSCAPE

        # Try to extract creation time from metadata.
        creation_date = data['tags'].get('creation_time')
        if creation_date is not None:
            try:
                self._creation_date = datetime.strptime(creation_date, "%Y-%m-%dT%H:%M:%S.%fZ")
            except ValueError:
                logging.error(f"Invalid creation time format {creation_date}.")

    def _type_from_extension(self):
        """Determine file type based on file extension."""
        fname = self._uuid.upper()
        for pattern in RepositoryFile.EXT_IMAGE:
            if fnmatch.fnmatch(fname, pattern.upper()):
                self._type = RepositoryFile.TYPE_IMAGE
                return
        for pattern in RepositoryFile.EXT_VIDEO:
            if fnmatch.fnmatch(fname, pattern.upper()):
                self._type = RepositoryFile.TYPE_VIDEO
                return

    @abstractmethod
    def extract_metadata(self):
        """Extract metadata from file content.

        Used to enforce the metadata extraction from file content in cases
        where not done automatically during initiation.
        """
        pass

    @property
    def uuid(self):
        """Return UUID of the file.

        :return: Universally unique identifier (UUID) of the file. Typically
            the full path of the file within the repository.
        :rtype: str
        """
        return self._uuid

    @property
    def rep(self):
        """Return repository containing the file.

        :return: Repository containing the file.
        :rtype: repository.Repository
        """
        return self._rep

    @property
    def name(self):
        """Return name of the file.

        :return: Name of the file.
        :rtype: str
        """
        return self._name

    @property
    def source(self):
        """Return the source of the file (e.g. full path or URL).

        :return: Source of the file.
        :rtype: str
        """
        return None

    @property
    def type(self):
        """Return type of the file.

        :return: Type of the file. The following values may be returend:
            TYPE_UNKNOWN: Unknown file type
            TYPE_IMAGE: Image file
            TYPE_VIDEO: Video file
        :rtype: int
        """
        return self._type

    @property
    def width(self):
        """Return width of the file content.

        :return: Width of the file content in pixels.
        :rtype: int
        """
        return self._width

    @property
    def height(self):
        """Return height of the file content.

        :return: Height of file content in pixels.
        :rtype: int
        """
        return self._height

    @property
    def rotation(self):
        """Return rotation of the file content.

        :return: Clock-wise rotation of the content in degrees. Typical
            values are 0, 90, 180 and 270.
        :rtype: int
        """
        return self._rotation

    @property
    def orientation(self):
        """Return orientation of the file content.

        :return: Orientation of the content considering rotation. The
            following values may be returned:
            ORIENTATION_LANDSCAPE: Content wider than high (default)
            ORIENTATION_PORTRAIT: Content heigher than wide.
        :rtype: int
        """
        return self._orientation

    @property
    def creation_date(self):
        """Return creation date of the file content.

        :return: Creation date of the file content. Note that this is not
            necessarily the creation date of the file.
        :rtype: DateTime
        """
        return self._creation_date

    @property
    def last_modified(self):
        """Return date of last file modification.

        :return: Date of last file modification.
        :rtype: DateTime
        """
        return self._last_modified

    @property
    def last_updated(self):
        """Return date of last metadata update.

        :return: Date of last metadata update.
        :rtype: DateTime
        """
        return self._last_updated

    @property
    def description(self):
        """Return description of the file content.

        :return: Description of the file content.
        :rtype: str
        """
        return self._description

    @property
    def rating(self):
        """Return rating of the file content.

        :return: Rating of the file content. Typically a star rating with values
            from 1 to 5.
        :rtype: int
        """
        return self._rating

    @property
    def coordinates(self):
        """Return coordinates where the file content was created.

        :return: [ latitude, longitude, height ]. Note that elements may be None if information is not available.
        :rtype: list of floats
        """
        return self._coordinates

    @property
    def location(self):
        """Return location (address) where the file content was created.

        May return None if the geographical location is not available.

        The geographical location is not stored as part of the file meta data.
        Since all free geocoding services implement a rate limit, reverse
        location lookups would slow down the indexing process. The geographical
        location is thus only looked up once requested.

        :return: city/country
        :rtype: str
        """
        # Return cached value if avaialable.
        if self._location is not None: return self._location
        # Return None if no coordinates available.
        if self._coordinates[0] is None or self._coordinates[1] is None:
            return None

        # Try to obtain location from geocoding service otherwise.
        try:
            # Retrieve default language from locale.
            lc = locale.getdefaultlocale()
            if len(lc) >= 1 and len(lc[0]) >= 2:
                lang = lc[0][0:2]
            else:
                lang = "en"
            self._location = geolocator.reverse(self._coordinates[0:2], exactly_one=True, language=lang).address
        except GeopyError as e:
            logging.error(f"An error occurred while looking up the location. {e}")
        finally:
            return self._location

    @property
    def tags(self):
        """Return tags on the file.

        :return: Tags on the file.
        :rtype: set of str
        """
        return self._tags
