"""Module providing common definitions."""

import copy
import logging
import os
import os.path
import sys
import yaml

from importlib import import_module
from logging.handlers import TimedRotatingFileHandler
from kivy.logger import Logger
from repository import check_param, ConfigError, Index, Repository, UuidError

#from .mylogging import Handler


APPLICATION_NAME = "Pyframe"
APPLICATION_DESCRIPTION = "Digital photo frame"
VERSION = "0.x"
PROJECT_NAME = "Pyframe project"

# Default configuration
DEFAULT_CONFIG = {
    'bg_color': [1, 1, 1],
    'cache': os.path.expanduser(f"~/.cache/01memories/cache"),
    'direction': "ascending",
    'display_mode': "static",
    'display_state': "on",
    'display_timeout': 300,
    'enable_exception_handler': False,
    'enable_logging': True,
    'enable_scheduler': True,
    'enable_mqtt': True,
    'index': os.path.expanduser(f"~/.cache/01memories/index.sqlite"),
    'index_update_interval': 0,
    'label_mode': "off",
    'label_content': "full",
    'label_duration': 60,
    'label_font_size': 0.08,
    'label_padding': 0.03,
    'log_level': "warning",
    'log_dir': os.path.expanduser(f"~/.cache/01memories/log"),
    'pause': 300,
    'resize': "fill",
    'rotation': 0,
    'smart_limit': 10,
    'smart_time': 24,
    'order': "name",
    'window_position': "auto",
    'window_size': "full"
}


# Mapping of name to numeric log level.
LOG_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}


class Formatter(logging.Formatter):
    """Pyframe log formatter.

    Used to imitate the Kivy log format in rotating log files.
    """

    def __init__(self, *args):
        """Initiaize Formatter instance."""
        super().__init__(*args)

    def format(self, record):
        """Split and format record."""
        try:
            msg = record.msg.split(':', 1)
            if len(msg) == 2:
                record.msg = '[%-13s]%s' % (msg[0], msg[1])
        except:
            pass
        return super().format(record)


def _configure_logging(config, filename):
    """Configure logging.

    Adjusts log levels based on the application configuration and adds a
    custom log handler for logging to rotating log files.

    :param config: Application configuration
    :type config: dict
    :param filename: Log filename
    :type filename: str
    :raises: Raises an exception if the directory cannot be created or is
      not writable.
    """

    # Check parameters.
    check_param('enable_logging', config, is_bool=True)
    check_param('log_level', config, options=set(LOG_LEVELS.keys()))
    check_param('log_dir', config, is_str=True)

    # Set log levels of default python and Kivy Logger.
    numeric_level = LOG_LEVELS[config['log_level']]
    logging.getLogger().setLevel(numeric_level)
    Logger.setLevel(numeric_level)

    # Reduce logging by IPTCInfo and exifread to errors or specified log
    # level, whatever is higher.
    logging.getLogger("iptcinfo").setLevel(max(logging.ERROR, numeric_level))
    logging.getLogger("exifread").setLevel(max(logging.ERROR, numeric_level))
    # Reduce logging by SQLAlchemy to warnings or specified log level,
    # whatever is higher.
    logging.getLogger("sqlalchemy").setLevel(max(logging.WARN, numeric_level))

    # Create log directory if it does not exist yet.
    log_dir = config['log_dir']
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            raise Exception(f"An exception occurred while creating the log directory '{log_dir}': {e}")

    # Make sure the directory is writable.
    if not os.access(log_dir, os.W_OK):
        raise Exception(f"The log directory '{log_dir}' is not writeable.")

    # Write all log messages to a rotating log file.
    if config['enable_logging'] == "on" or config['enable_logging'] == True:
        try:
            fullpath = os.path.join(log_dir, filename)
            logHandler = TimedRotatingFileHandler(os.path.join(fullpath), when="h", interval=24, backupCount=5, encoding='utf-8', errors='ignore')
            # Apply Kivy style formatter
            formatter = Formatter("%(asctime)s [%(levelname)-8s] %(message)s", "%Y-%m-%d %H:%M:%S")
            logHandler.setFormatter(formatter)
            # Add rotating log file handler to default logger.
            logging.info(f"Enabling logging to file '{fullpath}'.")
            logging.getLogger().addHandler(logHandler)
        except Exception as e:
            raise Exception(f"An error occurred while installing the log handler: {e}")


def _create_repositories(config, index):
    """Create file repositories from configuration.

    :param config: Application configuration
    :type config: dict
    :param index: Repository index
    :type index: repository.Index
    :raises: ConfigError, Exception
    """

    # Dictionary used to map type names to repository classes.
    supported_types = {
        'local': ("repository.local", "Repository"),
        'webdav': ("repository.webdav", "Repository"),
        'rclone': ("repository.rclone", "Repository")}

    # Exit application if no repositories have been defined.
    if 'repositories' not in config or type(config['repositories']) is not dict:
        raise ConfigError("Exiting application as no repositories have been defined.")

    # Extract global repository index configuration.
    global_index_config = {key: config[key] for key in ('index_update_interval', 'index_update_at') if key in config}

    # Create repositories based on the configuration.
    for uuid, rep_config in config['repositories'].items():

        # Skip disabled repositories.
        enabled_flag = rep_config.get('enabled', True)
        if enabled_flag is False or enabled_flag == "off":
            logging.info(f"Configuration: Skipping repository '{uuid}' as it has been disabled.")
            continue

        # Check parameters.
        check_param('type', rep_config, options=set(supported_types.keys()))

        # Substitute patterns in root paths of local directories. The
        # following patterns are substituted:
        #   {sys.prefix} => sys.prefix (e.g. "/usr/local")
        if rep_config.get('type') == "local":
            rep_config['root'] = os.path.expanduser(rep_config.get('root'))
            rep_config['root'] = rep_config.get('root').replace("{sys.prefix}", sys.prefix, 1)

        # Retrieve repository class from type.
        ref = supported_types[rep_config.get('type')]
        module = import_module(ref[0])
        rep_class = getattr(module, ref[1])

        # Combine global and local repository configuration. Local
        # configuration settings supersede global settings.
        rep_config2 = copy.deepcopy(config)
        rep_config2.update(rep_config)
        rep_config = { key: rep_config2[key] for key in rep_class.CONF_VALID_KEYS if key in rep_config2 }

        try:
            # Create repository instance.
            logging.info(f"Configuration: Creating {rep_config2.get('type')} repository '{uuid}'.")
            rep = rep_class(uuid, rep_config, index=index)
        # Catch any invalid configuration and UUID errors.
        except (ConfigError, UuidError) as e:
            raise ConfigError(f"Error in the configuration of repository '{uuid}'. {e}", rep_config)

    # Raise exception if no valid repositories have been defined.
    if len(Repository._repositories.items()) == 0:
        raise ConfigError("Exiting application as no valid repositories have been defined.", config['repositories'])

    # Create cache directory if it does not exist yet.
    cache_dir = config['cache']
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except Exception as e:
        raise Exception(f"An exception occurred while creating the cache file directory '{cache_dir}': {e}")


def _load_config():
    """Load application configuration.

    Loads the application configuration from the default configuration file
    and applies default values where missing.

    :returns: Application configuration
    :rtype: dict
    """
    conf_paths = [
        "./config.yaml",
        os.path.expanduser("~/.config/01memories/config.yaml"),
        "/etc/01memories/config.yaml",
        os.path.expanduser("~/.local/share/01memories/config/config.yaml"),
        "/usr/local/share/01memories/config/config.yaml",
        "/usr/share/01memories/config/config.yaml",
        "../config/config-dev.yaml"
    ]

    # Determine path of configuration file.
    for path in conf_paths:
        if os.path.isfile(path): break

    # Load configuration from yaml file.
    with open(path, 'r', encoding='utf8') as config_file:
        config2 = yaml.safe_load(config_file)

    # Copy and update default configuration.
    config = copy.deepcopy(DEFAULT_CONFIG)
    config.update(config2)

    logging.debug(f"Configuration: Configuration = {config}")
    return config


def _load_index(config):
    """Load or create repository index.

    :param config: Application configuration
    :type config: dict
    :returns: Repository index
    :rtype: repository.Index
    :raises: Exception
    """
    # Create index directory if it does not exist yet.
    index_path = config['index']
    index_dir = os.path.dirname(index_path)
    try:
        os.makedirs(index_dir, exist_ok=True)
    except Exception as e:
        raise Exception(f"An exception occurred while creating the index file directory '{index_dir}': {e}")

    # Load/create and return index.
    return Index(index_path)
