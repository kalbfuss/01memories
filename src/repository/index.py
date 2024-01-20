"""Module providing metadata index class.

The following test script is based on the tutorial by Philipp Wagner [1]. The
script depends on the following debian packages:
- python3-sqlalchemy

References;
----------
1. https://bytefish.de/blog/first_steps_with_sqlalchemy/
"""

import logging
import random
import time

from enum import Enum
from sqlalchemy import asc, create_engine, desc, event, func, update, delete, or_, Column, DateTime, Float, ForeignKey, Integer, String, Boolean
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import backref, relationship, sessionmaker, scoped_session

from .common import UuidError, check_param, check_valid_required
from .file import RepositoryFile
from .repository import Repository


# Install listener for connection events to automatically enable foreign key
# constraint checking by SQLite.
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(conn, *largs):
    """Enable foreign key constraint checking and write-ahead logging (WAL)
    in SQLite."""
#    logging.debug("Enable foreign key database constraints.")
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

"""
# Install listener to record time prior to execution of statements.
@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, *largs):
    conn.info.setdefault("query_start_time", []).append(time.time())

# Install listener to calculate and log total execution time.
@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, *largs):
    total = time.time() - conn.info["query_start_time"].pop(-1)
    logging.debug(f"SQL query executed within {round(total*1000, 2)} ms.")
"""

Base = declarative_base()


class MetaData(Base):
    """Database model for file metadata.

    Database representation of file metadata using SQLAlchemy object relational
    mapper. Properties resemble properties of class repository.RepositoryFile.

    Properties:
        id(Integer): Numerical unique identifier. Automatically generated.
        rep_uuid(String(36)): Universally unique identifier of the repository
            containing the file.
        file_uuid(String(255)): Universally unique identifier of the file.
        type(Integer): Type of the file. See repository.RepositoryFile for
            acceptable values.
        width(Integer): Width of the file content in pixels.
        height(Integer): Height of the file content in pixels.
        rotation(Iteger): Clock-wise rotation of the content in degrees. See
            repository.RepositoryFile for acceptable values.
        orientation(Integer): Orientation of the content considering rotation.
            See repository.RepositoryFile for acceptable values.
        creation_date(DateTime): Creation date of the file content.
        last_modified(DateTime): Date of last file modification.
        last_updated(DateTime): Date of last metadata update.
        description(String(255)): Description of the file.
        rating(Integer): Star rating of the file content.
        latitude(Float): Latitude of geographical coordinates
        longitude(Float): Longitude of geographical coordinates
        altitude(Float): Altitude of geopgraphical coordinates
        random_number(Float): Random number between 0..1. Used for creating
          starting points of smart order index iterations.
        verified(Boolean): Verification flag set during index building. True if
            file exists. False if not yet verified or does not exist.
    """

    __tablename__ = "files"
    id = Column(Integer, primary_key=True)
    rep_uuid = Column(String(Repository.MAX_LEN_UUID), nullable=False)
    # File uuid needs to be unique within a repository, but not across repositories.
#    file_uuid = Column(String(255), unique=True, nullable=False)
    file_uuid = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False, index=True)
    type = Column(Integer)
    width = Column(Integer)
    height = Column(Integer)
    rotation = Column(Integer)
    orientation = Column(Integer)
    creation_date = Column(DateTime, index=True)
    description = Column(String(255))
    rating = Column(Integer)
    latitude = Column(Float)
    longitude = Column(Float)
    altitude = Column(Float)
    random_number = Column(Float, index=True)
    last_modified = Column(DateTime)
    last_updated = Column(DateTime)
    verified = Column(Boolean)
    tags = relationship("MetaDataTag", secondary="tag_file", backref=backref("files", lazy="dynamic"))


class MetaDataTag(Base):
    """Database model for tags in file metadata.

    Database representation of tags in file metadata using SQLAlchemy object
    relational mapper. Tags and metadata are connected via a separate table
    'tag_file' in the database.

    Properties:
        id(Integer): Numerical unique identifier. Automatically generated.
        name(String(255)): Unique name of the tag.
    """

    __tablename__ = "tags"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)


class Link(Base):
    """Association table for file metadata and tags."""

    __tablename__ = "tag_file"
    tag_id = Column(Integer, ForeignKey('tags.id', ondelete="CASCADE"), primary_key=True)
    file_id = Column(Integer, ForeignKey('files.id', ondelete="CASCADE"), primary_key=True)


class SORT_DIR(str, Enum):
    """Enumeration of index sort directions."""
    ASC = "ascending"
    DESC = "descending"


class SORT_ORDER(str, Enum):
    """Enumeration of index sort orders."""
    DATE = "date"
    NAME = "name"
    RANDOM = "random"
    SMART = "smart"


class Index:
    """File metadata index.

    Enables quick lookup and filtering of files based on their metadata. Index
    may span multiple repositories. Files and repositories are referenced via
    there universal unique identifiers.

    Use method build() to build metadata index. Method build() may be run in
    the background from a different thread.
    """

    # Required and valid index filter and sort criteria
    CRIT_REQ_KEYS = set()
    CRIT_VALID_KEYS = {'direction', 'excluded_tags', 'most_recent', 'order', 'orientation', 'repositories', 'smart_limit', 'smart_time', 'tags', 'types'} | CRIT_REQ_KEYS

    def __init__(self, dbname="index.sqlite"):
        """Initialize file index.

        :param dbname: Name of database. Default is "index.sqlite".
        :type dbname: str
        """
        self._dbname = dbname
        try:
            logging.info(f"Opening file index database '{dbname}'")
            # Determine whether we want verbose SQL debugging information.
            echo_flag = False
            if logging.getLogger("sqlalchemy").getEffectiveLevel() <= logging.DEBUG:
                echo_flag = True
            # Create sqlite database engine
            self._engine = create_engine(f"sqlite:///{dbname}", echo=echo_flag)
            # Create base class metadata
            Base.metadata.create_all(self._engine)
            # Open database session
            self._session_factory = sessionmaker(bind=self._engine)
            self._scoped_session = scoped_session(self._session_factory)
            self._session = self._scoped_session()
        except Exception as e:
            logging.critical(f"An error ocurred while opening the index database '{dbname}': {e}")

    def __del__(self):
        self.close()

    def build(self, rep, rebuild=False):
        """Build metadata index.

        Build method may be called from a different thread to build the index in
        the background. The method thus creates its own session and prevents
        files from looking up metadata from the index.

        :param rep: Repository for which to build the index.
        :type rep: repository.Repository
        :param rebuild: Indicates whether index is to be completely rebuilt.
            Default (False) is to update only, i.e. add the missing entries.
        :type rebuild: bool
        """
        # Create new session since build may be called from different thread.
        session = self._scoped_session()

        # Delete all metadata for the specified repository.
        if rebuild:
            logging.info(f"Rebuilding metadata index for repository '{rep.uuid}'.")
            try:
                logging.debug(f"Deleting all metadata entries of repository '{rep.uuid}'.")
                # Delete all file entries for the specified repository.
                session.query(MetaData).filter(MetaData.rep_uuid == rep.uuid).delete()
                session.commit()
                # Delete all unused tags.
                tags = session.query(MetaDataTag).all()
                for tag in tags:
                    if tag.files.count() == 0:
                        logging.info(f"Deleting unused tag '{tag.name}'.")
                        session.delete(tag)
                session.commit()
            except Exception as e:
                logging.error(f"An error occurred while deleting metadata of repository {rep.uuid} from index: {e}")
        # Mark existing metadata entries for verification.
        else:
            logging.info(f"Updating metadata index for repository '{rep.uuid}'.")
            try:
                logging.debug(f"Resetting verification flags for all metadata entries of repository '{rep.uuid}'.")
                query = update(MetaData).where(MetaData.rep_uuid == rep.uuid).values(verified=False)
                session.execute(query)
                session.commit()
            except Exception as e:
                logging.error(f"An error occurred while marking metadata entries of repository '{rep.uuid}' for verification: {e}")

        # Iterate through all files in the repository.
        for file in rep.iterator(index_lookup=False, extract_metadata=False):
            try:
                # Create new metadata entry for file if not included in the
                # index yet or outdated.
                mdata = session.query(MetaData).filter(MetaData.rep_uuid == rep.uuid).filter(MetaData.file_uuid == file.uuid).first()
                if mdata is None or mdata.last_updated < file.last_modified:
                    # Extract metadata from file.
                    file.extract_metadata()

                    # Create all necessary tags in database.
                    tags = list()
                    if file.tags:
                        for name in file.tags:
                            # Try to query tag from database.
                            tag = session.query(MetaDataTag).filter(MetaDataTag.name == name).first()
                            # Create and add tag to database otherwise.
                            if tag is None:
                                logging.info(f"Adding tag '{name}'.")
                                tag = MetaDataTag(name=name)
                            tags.append(tag)

                    # Create/update metadata entry with file metadata.
                    if mdata is None:
                        logging.info(f"Adding metadata of file '{file.uuid}' to index.")
                    else:
                        logging.info(f"Updating metadata of file '{file.uuid}' in index.")
                    mdata = MetaData(rep_uuid=file.rep.uuid,
                        file_uuid=file.uuid,
                        name=file.name,
                        type=file.type,
                        width=file.width,
                        height=file.height,
                        rotation=file.rotation,
                        orientation=file.orientation,
                        creation_date=file.creation_date,
                        last_modified=file.last_modified,
                        last_updated=file.last_updated,
                        description=file.description, rating=file.rating,
                        latitude=file._coordinates[0],
                        longitude=file._coordinates[1],
                        altitude=file._coordinates[2],
                        random_number=random.random(),
                        verified=True,
                        tags=tags)
                    session.add(mdata)
                    # Commit all changes to the database.
                    session.commit()
                else:
                    logging.debug(f"Skipping file '{file.uuid} as already included in index.")
                    # Mark entry as verified.
                    query = update(MetaData).where(MetaData.rep_uuid == rep.uuid).where(MetaData.file_uuid == file.uuid).values(verified=True)
                    session.execute(query)
                    # Do not immediately commit update for performance reasons.
#                    session.commit()
            except Exception as e:
                logging.error(f"An error occurred while building the metadata index: {e}")

        # Delete entries which have not been successfulyy verified.
        query = delete(MetaData).where(MetaData.verified == False)
        session.execute(query)
        # Commit pending changes and close session
        session.commit()
        session.close()

    def close(self):
        try:

            # Close database session and dispose engine
            if self._session:
                logging.debug(f"Closing database session.")
                self._session.close()
                self._session = None
            if self._engine:
                logging.debug(f"Disposing engine for database '{self._dbname}'.")
                self._engine.dispose()
                self._engine = None
        except Exception as e:
            logging.error(f"An error ocurred while closing the index database '{self._dbname}': {e}")

    def lookup(self, file, rep):
        """Lookup file metadata.

        :param file: File for which to lookup metadata.
        :type file: repository.Index
        :param rep: Repository containing the file.
        :type rep: repository.Repository
        :return: Returns a metadata object for the file if available. Returns
            None otherwise.
        :return type: repository.MetaData
        """
        try:
            mdata = self._session.query(MetaData).filter(MetaData.rep_uuid == rep.uuid).filter(MetaData.file_uuid == file.uuid).first()
            return mdata
        except Exception as e:
            logging.error(f"An error ocurred while looking up metadata from index for file '{file.uuid}' in repository '{rep.uuid}': {e}")
            return None

    def count(self):
        """Count the number of rows in the index.

        :return: Number of rows in the index.
        :return type: int
        """
        return self._session.query(MetaData).count()

    def iterator(self, **criteria):
        """Return selective iterator.

        Return selective iterator which allows to traverse through a
        sub-population of files in the index according to specified criteria.

        :param criteria: Selection criteria
        :type criteria: dict
        :return: Selective iterator
        :return type: repository.IndexIterator
        """
        return IndexIterator(self._session, **criteria)


class IndexIterator:
    """Selective index iterator.

    Selective iterator which allows to traverse through a sub-population of
    files in the index according to specified filter and order criteria.
    """

    def __init__(self, session, **criteria):
        """Initialize selective index iterator.

        :param session: SQLAlchemy database session
        :type session: sqlalchemy.orm.Session
        :param criteria: dictionary containing iteration criteria
        :type criteria: dict
        :raises: ConfigError
        """
        self._criteria = criteria
        self._result = None
        self._length = 0
        self._position = 0

        # Check the configuration for valid and required parameters.
        check_valid_required(criteria, Index.CRIT_VALID_KEYS, Index.CRIT_REQ_KEYS)
        # Check parameters.
        check_param('direction', criteria, required=False, options={ item.value for item in SORT_DIR })
        check_param('excluded_tags', criteria, required=False, recurse=True, is_str=True)
        check_param('most_recent', criteria, required=False, gr=0)
        check_param('order', criteria, required=False, options={ item.value for item in SORT_ORDER })
        check_param('orientation', criteria, required=False, options={ RepositoryFile.ORIENTATION_PORTRAIT, RepositoryFile.ORIENTATION_LANDSCAPE })
        check_param('repositories', criteria, required=False, recurse=True, is_str=True)
        check_param('tags', criteria, required=False, recurse=True, is_str=True)
        check_param('types', criteria, required=False, options={ RepositoryFile.TYPE_IMAGE, RepositoryFile.TYPE_VIDEO })
        # Check smart order related parameters.
        if criteria.get('orientation') == SORT_ORDER.SMART:
            check_param('smart_limit', criteria, required=True, is_int=True, gr=0)
            check_param('smart_time', criteria, required=True, gr=0)

        # Initialize query.
        query = session.query(MetaData.file_uuid, MetaData.rep_uuid, MetaData.creation_date)

        # Extend query based on iteration criteria.
        for key, value in criteria.items():

            # Filter for repository by UUID
            if key == "repositories":
                if isinstance(value, (list, set)):
                    query = query.filter(MetaData.rep_uuid.in_(value))
                else:
                    query = query.filter(MetaData.rep_uuid == value)

            # Filter for file type.
            elif key == "types":
                if isinstance(value, (list, set)):
                    query = query.filter(MetaData.type.in_(value))
                else:
                    query = query.filter(MetaData.type == value)

            # Filter for orientation of content.
            elif key == "orientation":
                query = query.filter(MetaData.orientation == value)

            # Limit iteration to files with specified tags.
            elif key == "tags":
                # Convert to list if single value specified.
                if type(value) == str: value = [value]
                query = query.filter(MetaData.tags.any(func.lower(MetaDataTag.name).in_([tag.lower() for tag in value])))

            # Exclude files with excluded tags from iteration.
            elif key == "excluded_tags":
                # Convert to list if single value specified.
                if type(value) == str: value = [value]
                query = query.filter(or_(~MetaData.tags.any(func.lower(MetaDataTag.name).in_([tag.lower() for tag in value])), MetaData.tags == None))

        # Determine limiting date to limit iteration to the n most recent files
        # based on the creation date. Outside of the loop since query needs to
        # be executed after all filters, but prior to specifying any order
        # (see below).
        if 'most_recent' in criteria:
            value = criteria['most_recent']
            result = query.order_by(desc(MetaData.creation_date)).limit(value).all()
            if len(result) > 0:
                date_limit = result[-1].creation_date
                query = query.filter(MetaData.creation_date >= date_limit)

        # Retrieve files in a specific or random order.
        if 'order' in criteria:
            order = criteria['order']
            dir = criteria.get('direction', SORT_DIR.ASC)
            map = { SORT_DIR.ASC: asc, SORT_DIR.DESC: desc }
            dir_fun = map[dir]
            if order == SORT_ORDER.RANDOM:
                query = query.order_by(func.random())
            elif order == SORT_ORDER.DATE:
                query = query.order_by(dir_fun(MetaData.creation_date))
            elif order == SORT_ORDER.NAME:
                query = query.order_by(dir_fun(func.upper(MetaData.name)))
            elif order == SORT_ORDER.SMART:
                logging.debug("Determine start date for smart order iteration.")
                # Metadata entries have been assigned a random number in the
                # range from 0..1 during creation. We now generate another
                # random number in the same range and retrieve the metadata
                # entry with the closest match as starting point for the series.
                random_number = random.random()
                result = query.filter(MetaData.random_number >= random_number).order_by(MetaData.random_number).first()
                if result is None:
                    result = query.filter(MetaData.random_number <= random_number).order_by(desc(MetaData.random_number)).first()
                if result is not None:
                    query = query.order_by(MetaData.creation_date).filter(MetaData.creation_date >= result.creation_date).limit(criteria['smart_limit'])

        # Query data and save list of metadata objects.
        logging.debug("Querying files for new iteration.")
        self._result = query.all()
        logging.debug(f"New iteration has {len(self._result)} files.")

    def __iter__(self):
        """Return self as iterator.

        :return: self
        :return type: repository.IndexIterator
        """
        return self

    def __next__(self):
        """Return next file in iteration.

        :return: next file in iteration
        :return type: repository.RepositoryFile
        :raises: StopIteration
        """
        # Repeat until we have a valid file or end of iteration is reached.
        while True:
            # Retrieve next metadata object in iteration.
            if self._position < len(self._result):
                mdata = self._result[self._position]
                self._position = self._position + 1
            # Raise exception if end of iteration is reached.
            else:
                raise StopIteration()
            # Evaluate smart order termination criteria from second file onwards.
            if self._criteria.get('order') == SORT_ORDER.SMART and self._position > 1:
                # Obtain meta data of previous file.
                prev_mdata = self._result[self._position - 2]
                # Stop iteration if delta in creation date between current and
                # previous file exceeds smart time limit.
                delta = mdata.creation_date - prev_mdata.creation_date
                delta = delta.seconds/3600 + delta.days*24
                if delta > self._criteria['smart_time']:
                    logging.debug("Ending iteration early due to smart time criterion.")
                    raise StopIteration()
                # We additionally plan to implement a smart distance criterion
                # at a later point in time once location meta data are supported.
            # Try to obtain corresponding file.
            try:
                return Repository.by_uuid(mdata.rep_uuid).file_by_uuid(mdata.file_uuid)
            # Catch any invalid uuid errors in case the file is no longer
            # available in the repository and continue.
            except UuidError:
                logging.warn(f"Skipping invalid file '{mdata.file_uuid}' in repository '{mdata.rep_uuid}'. The metadata index may be outdated.")
                pass

    @property
    def length(self):
        """Return number of files in index."""
        return len(self._result)

    def previous(self, n=1):
        """Return previous file in iteration.

        Optionally, an offset may be specified to retrieve even earlier elements
        of the iteration.

        :param n: Optional offset. An offset of 1 corresponds to the previous
          element. An offset of 2 to the second previous element etc.
        :type n: int
        :return: previous file in iteration
        :return type: repository.RepositoryFile
        :raises: StopIteration
        """
        # Adjust position to retrieve previous as next file.
        if self._position > n:
            self._position = self._position - (n + 1)
            return next(self)
        else:
            raise StopIteration()
