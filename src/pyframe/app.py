"""Module providing Pyframe application."""

import copy
import kivy.app
import logging
import repository.local
import repository.webdav
import subprocess
import sys
import time
import traceback
import yaml

from importlib import import_module
from repository import ConfigError, Index, Repository, UuidError, check_param, check_valid_required

from kivy.base import ExceptionManager
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.logger import Logger, LOG_LEVELS

from .mylogging import Handler
from .indexer import Indexer
from .slideshow import Slideshow
from .scheduler import Scheduler
from .controller import Controller, DISPLAY_MODE, DISPLAY_STATE, PLAY_STATE
from .mqtt import MqttInterface


class ExceptionHandler(kivy.base.ExceptionHandler):
    """Pyframe exception handler.

    Logs all exceptions, but continues with the execution. The main purpose of
    the handler is to prevent the application from exiting unexpectedly.
    """

    def __init__(self, app):
        """Initialize exception handler instance."""
        super().__init__()
        self._app = app

    def handle_exception(self, exception):
        """Log all exceptions and continue with execution.

        For unknown reasons, the exception is not always provided as an argument
        albeit the kivy documentation says so. The method thus retrieves the
        last raised exception via a system call.
        """
        # Make sure we do not produce any unhandled exceptions within the
        # exception handler.
        try:
            # Log information on exception.
            Logger.error("App: An exception was raised:")
            # Formatting the excpetion has failed for unknown reasons in the
            # past. Putting into separate try block to make sure subsequent
            # code is executed.
            try:
                # Retrieve information on last exception via system call since
                # exception object passed to handler sometimes seems to be
                # missing/incomplete.
                _, e, _ = sys.exc_info()
                Logger.error(f"App: {''.join(traceback.format_exception(e)).rstrip()}")
            except:
                pass
            Logger.error("App: Ignoring and continuing with execution.")
            # Wait for a moment to slow down infinite loops.
            time.sleep(10)
            # Restart slideshow if playing.
            if self._app.play_state == PLAY_STATE.PLAYING:
                self._app.stop()
                self._app.play()
            # Continue with execution.
        except: pass
        return ExceptionManager.PASS


class App(kivy.app.App, Controller):
    """Pyframe main application."""

    # Required and valid configuration parameters
    CONF_REQ_KEYS = {'display_mode', 'display_state', 'display_timeout', 'enable_exception_handler', 'enable_mqtt', 'enable_logging', 'enable_scheduler', 'index', 'log_level', 'log_dir', 'repositories', 'slideshows', 'window_size'} | Slideshow.CONF_REQ_KEYS
    CONF_VALID_KEYS = {'cache', 'index_update_at', 'index_update_interval', 'mqtt', 'schedule' } | CONF_REQ_KEYS | Slideshow.CONF_VALID_KEYS

    def __configure_logging(self):
        """Configure logging.

        Adjusts log levels based on the application configuration and adds a
        custom log handler for logging to rotating log files.

        :raises: ConfigError
        """
        config = self._config

        # Check parameters.
        check_param('enable_logging', config, is_bool=True)
        check_param('log_level', config, options=set(LOG_LEVELS.keys()))
        check_param('log_dir', config, is_str=True)

        # Set log levels of default python and Kivy Logger.
        numeric_level = LOG_LEVELS[config['log_level']]
        logging.basicConfig(level=numeric_level)
        Logger.setLevel(numeric_level)

        # Reduce logging by IPTCInfo and exifread to errors or specified log
        # level, whatever is higher.
        logging.getLogger("iptcinfo").setLevel(max(logging.ERROR, numeric_level))
        logging.getLogger("exifread").setLevel(max(logging.ERROR, numeric_level))
        # Reduce logging by SQLAlchemy to warnings or specified log level,
        # whatever is higher.
        logging.getLogger("sqlalchemy").setLevel(max(logging.WARN, numeric_level))

        # Write all log messages to rotating log files using a special log
        # handler if file logging is activated. A separate log file is used for
        # the background indexing thread.
        if config['enable_logging'] == "on" or config['enable_logging'] == True:
            try:
                self._logHandler = Handler(config['log_dir'], "indexer")
                logging.getLogger().addHandler(self._logHandler)
            except Exception as e:
                raise Exception(f"App: An error occurred while installing the log handler. {e}")

    def __create_repositories(self):
        """Create file repositories from configuration."""
        config = self._config
        index = self._index
        # Dictionary used to map type names to repository classes.
        supported_types = {
            'local': ("repository.local", "Repository"),
            'webdav': ("repository.webdav", "Repository"),
            'rclone': ("repository.rclone", "Repository")}

        # Exit application if no repositories have been defined.
        if 'repositories' not in config or type(config['repositories']) is not dict:
            raise ConfigError("Configuration: Exiting application as no repositories have been defined.")

        # Extract global repository index configuration.
        global_index_config = {key: config[key] for key in ('index_update_interval', 'index_update_at') if key in config}

        # Create repositories based on the configuration.
        for uuid, local_config in config['repositories'].items():

            # Skip disabled repositories.
            enabled_flag = local_config.get('enabled')
            if enabled_flag is False or enabled_flag == "off":
                Logger.info(f"Configuration: Skipping repository '{uuid}' as it has been disabled.")
                continue

            # Combine global and local repository index configuration. Local
            # configuration settings supersede global settings.
            index_config = copy.deepcopy(global_index_config)
            index_config.update(local_config)

            # Check parameters.
            check_param('type', local_config, options=set(supported_types.keys()))
            check_param('enabled', local_config, is_bool=True)
            check_param('index_update_interval', index_config, required=False, is_int=True, ge=0)
            check_param('index_update_at', index_config, required=False, is_time=True)

            # Retrieve repository class from type.
            ref = supported_types[local_config.get('type')]
            module = import_module(ref[0])
            rep_class = getattr(module, ref[1])

            # Combine global and local repository configuration. Local
            # configuration settings supersede global settings.
            rep_config = copy.deepcopy(config)
            rep_config.update(local_config)
            rep_config = { key: rep_config[key] for key in rep_class.CONF_VALID_KEYS if key in rep_config }

            try:
                # Create repository instance.
                Logger.info(f"Configuration: Creating {local_config.get('type')} repository '{uuid}'.")
                rep = rep_class(uuid, rep_config, index=index)
            # Catch any invalid configuration and UUID errors.
            except (ConfigError, UuidError) as e:
                raise ConfigError(f"Configuration: Error in the configuration of repository '{uuid}'. {e}", rep_config)

            try:
                # Queue the repository for indexing.
                interval = index_config.get('index_update_interval', 0)
                at = index_config.get('index_update_at', None)
                self._indexer.queue(rep, interval, at)
            # Catch any invalid configuration and UUID errors.
            except (ConfigError) as e:
                raise ConfigError(f"Configuration: Error in the configuration of repository '{uuid}'. {e}", index_config)

        # Exit application if no valid repositories have been defined.
        if len(Repository._repositories.items()) == 0:
            raise ConfigError("Configuration: Exiting application as no valid repositories have been defined.", config['repositories'])

    def __create_slideshows(self):
        """Create slideshows from configuration.

        Slideshow configurations are extracted from the 'slideshows' section
        in the configuration file. One slideshow is created per has entry.
        Slideshow instances are collected in the hash _slideshows, with the key
        being identical to the slideshow name in the configuration file.

        :raises: ConfigError
        """
        config = self._config
        index = self._index
        # Exit application if no slideshow has been defined.
        if 'slideshows' not in config or type(config['slideshows']) is not dict:
            raise ConfigError("Configuration: Exiting application as no slideshows have been defined.", config)

        # Create empty dictionary to collect slideshows
        self._slideshows = dict()
        # Extract global slideshow configuration
        global_config = {key: config[key] for key in Slideshow.CONF_VALID_KEYS if key in config}

        # Create slideshows from configuration.
        for name, config in config['slideshows'].items():
            # Combine global and local configuration. Local configuration
            # settings supersede global settings.
            combined_config = copy.deepcopy(global_config)
            combined_config.update(config)

            # Create new slideshow, bind 'on_content_change' event and add to
            # slideshow do dictionary.
            try:
                # Verify that only existing/enabled repositories have been defined.
                check_param('repositories', combined_config, required=False, recurse=True, options=Repository.repositories())
                # Create slideshow and add to the list of slideshows.
                slideshow = Slideshow(name, index, combined_config)
                self._slideshows[name] = slideshow
                # Make sure we receive all content change events.
                slideshow.bind(on_content_change=self.on_content_change)

            except ConfigError as e:
                raise ConfigError(f"Configuration: Error in the configuration of slideshow '{name}'. {e}", config)
            except Exception as e:
                raise Exception(f"Slideshow: {e}")

        # Exit application if no valid repositories have been defined.
        if len(self._slideshows.items()) == 0:
            raise ConfigError("Configuration: Exiting application as no valid slideshows have been defined.")

    def __init_display(self):
        """Initialize display and window.

        :raises: ConfigError
        """
        config = self._config

        # Check parameters.
        check_param('display_mode', config, options={ item.value for item in DISPLAY_MODE })
        check_param('display_state', config, is_bool=True)
        check_param('display_timeout', config, is_int=True, gr=0)

        # Convert from boolean to "on" (True) and "off" (False) if necessary.
        # This is a pecularity of the YAML 1.1 standard, which interprets "on"
        # and "off" as boolean values.
        map = {True: "on", False: "off", "on": "on", "off": "off"}
        display_state = map[config['display_state']]

        # Initialize display timeout, state and mode.
        self._display_timeout = config['display_timeout']
        self._timeout_event = None
        self._display_mode = ""
        self._display_state = ""
        self.display_state = display_state
        self.display_mode = config['display_mode']

        # Set window size.
        value = config['window_size']
        if type(value) is list and len(value) == 2 and value[0] > 0 and value[1] > 0:
            Window.size = (value)
        elif value == "full":
            Window.fullscreen = 'auto'
        else:
            raise ConfigError(f"Configuration: Invalid value '{value}' for parameter 'window_size' specified. Valid values are [width, height] and 'full'.", config)
        # Disable display of mouse cursor
        Window.show_cursor = False

    def __load_config(self):
        """Load application configuration.

        Loads the application configuration from the default configuration file
        and applies default values where missing.
        """
        # Load configuration from yaml file.
        with open('./config.yaml', 'r') as config_file:
            config = yaml.safe_load(config_file)
        self._config.update(config)
        Logger.debug(f"Configuration: Configuration = {self._config}")
        return self._config

    # Default configuration.
    _config = {
        'bg_color': [1, 1, 1],
        'cache': "./cache",
        'direction': "ascending",
        'display_mode': "static",
        'display_state': "on",
        'display_timeout': 300,
        'enable_exception_handler': False,
        'enable_logging': True,
        'enable_scheduler': True,
        'enable_mqtt': True,
        'index': "./index.sqlite",
        'index_update_interval': 0,
        'label_mode': "off",
        'label_content': "full",
        'label_duration': 60,
        'label_font_size': 0.08,
        'label_padding': 0.03,
        'log_level': "warning",
        'log_dir': "./log",
        'pause': 300,
        'resize': "fill",
        'rotation': 0,
        'smart_limit': 10,
        'smart_time': 24,
        'order': "name",
        'window_size': "full"
    }

    def build(self):
        """Build Kivy application.

        Loads the application configuration from the default configuration file.
        Creates configured repositories and builds an index across the latter.
        """
        self._index = None
        self._scheduler = None
        self._mqtt_interface = None
        self._play_state = PLAY_STATE.STOPPED

        # Register 'state_change' event, which is fired upon content and
        # controller state changes.
        self.register_event_type('on_state_change')

        # Load configuration.
        self.__load_config()
        # Check the configuration for valid and required parameters.
        check_valid_required(self._config, self.CONF_VALID_KEYS, self.CONF_REQ_KEYS)

        # Configure logging.
        self.__configure_logging()
        # Create/load index.
        self._index = Index(self._config['index'])
        # Create background indexer.
        self._indexer = Indexer(self._index)
        # Create repositories.
        self.__create_repositories()
        # Start building index in the background.
        self._indexer.start()
        # Create slideshows.
        self.__create_slideshows()

        # Make first slideshow the main root widget
        self.root = next(iter(self._slideshows.values()))

        # Create mqtt interface if configured and activated.
        value = self._config.get('enable_mqtt')
        if 'mqtt' in self._config and (value == "on" or value is True):
            try:
                self._mqtt_interface = MqttInterface(self._config['mqtt'], self)
            except ConfigError as e:
                raise ConfigError(f"Configuration: Error in the MQTT interface configuration. {e}", e.config)
            except Exception as e:
                raise Exception(f"MQTT: {e}")

        # Initialize display
        self.__init_display()

        # Bind keyboard listener
        Window.bind(on_keyboard=self.on_keyboard)

        # Create scheduler if configured and activated.
        value = self._config.get('enable_scheduler')
        if 'schedule' in self._config and (value == "on" or value is True):
            try:
                self._scheduler = Scheduler(self._config['schedule'], self)
            except ConfigError as e:
                raise ConfigError(f"Configuration: {e}", e.config)
            except Exception as e:
                raise Exception(f"Scheduler: {e}")
        # Start playing first defined slideshow otherwise.
        else:
            self.play()

        # Install default exception handler to prevent the application from
        # exiting unexpectedly. All exceptions are caught and logged, but the
        # appplication continues with the execution afterwards.
        value = self._config.get('enable_exception_handler')
        if value == "on" or value is True:
            ExceptionManager.add_handler(ExceptionHandler(self))

        return self.root

    def on_content_change(self, slideshow, *largs):
        """Handle slideshow content change events."""
        Logger.debug(f"App: Event 'on_content_change' from slideshow '{slideshow.name}' received. Forwarding as event 'on_state_change'.")
        # Forward as 'on_state_change' event.
        self.dispatch('on_state_change')
        # Consume event.
        return True

    def on_keyboard(self, window, key, *args):
        """Handle keyboard events.

        The following events are currently supported:
        - Right arrow: Show net file.
        - Left arrow: Show previous file (not yet implemented).
        - Escape: Exit application.
        """
        Logger.info(f"App: Key '{key}' pressed.")
        # Exit application if escape key pressed.
        if key == 27:
            # Let the default handler do the necessary work.
            return False
        # Touch controller to prevent screen timeout.
        self.touch()
        # Display next file if right arrow pressed.
        if key == 275:
            self.next()
        # Display previous file if left arrow pressed.
        elif key == 276:
            self.previous()
        # Consume event.
        return True

    def on_state_change(self, *largs):
        """Default handler for 'on_state_change' events."""
        pass

    def close(self):
        """Prepare application for safe exit.

        Shuts down the MQTT remote controller, scheduler and stops the current
        the current slideswhow."""
        # Stop current slideshow.
        self.stop()
        # Stop MQTT interface if running.
        if self._mqtt_interface is not None:
            Logger.info("App: Stopping MQTT interface.")
            self._mqtt_interface.stop()
        # Stop scheduler if running.
        if self._scheduler is not None:
            Logger.info("App: Stopping scheduler.")
            self._scheduler.stop()
        # Close metadata index if open.
        if self._index is not None:
            Logger.info("App: Closing metadata index.")
            self._index.close()

    def on_display_timeout(self, dt):
        """Handle display timeouts in motion mode."""
        # Pause playing slideshow and turn display off.
        Logger.info(f"Controller: Display has timed out.")
        self.pause()
        self.display_off()

    @property
    def current_file(self):
        """Return the current repository file.

        :return: current file
        :rtype: repository.File
        """
        return self.root.current_file

    @property
    def display_mode(self):
        """Return display mode.

        See enumeration DISPLAY_MODE for possible values.

        :return: display mode
        :rtype: str
        """
        return self._display_mode

    @display_mode.setter
    def display_mode(self, mode):
        """Set display mode.

        See enumeration DISPLAY_MODE for possible values.

        :param mode: display mode
        :type mode: str
        """
        # Return if already in the right mode.
        if mode == self._display_mode: return
        Logger.info(f"Controller: Changing display mode from '{self._display_mode}' to '{mode}'.")
        # Turn display on and start playing slideshow.
        # Cancel previously scheduled timeout event.
        if self._timeout_event is not None:
            self._timeout_event.cancel()
        #  Set display to motion mode and start playing slideshow.
        if mode == DISPLAY_MODE.STATIC: pass
        elif mode == DISPLAY_MODE.MOTION:
            # Update last touch time stamp.
            self._last_touch = time.time()
            # Schedule schedule timeout event if not stopped.
            if self.play_state != PLAY_STATE.STOPPED:
                self._timeout_event = Clock.schedule_once(self.on_display_timeout, self._display_timeout)
        # Raise exception upon invalid display mode.
        else:
            raise Exception(f"The selected display mode '{mode}' is invalid. Acceptable values are '{[ item.value for item in DISPLAY_MODE ]}'.")
        # Update display mode.
        self._display_mode = mode
        self.dispatch('on_state_change')

    def display_on(self):
        """Turn the display on."""
        # Return if already on.
        if self._display_state == DISPLAY_STATE.ON: return
        Logger.info("Controller: Turning display on.")
        # Turn display on on Linux with X server.
        subprocess.run("/usr/bin/xset dpms force on", shell=True,  stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)
        # Raise window to top (just in case) and make full screen again.
#        Window.raise_window()
#        if self._config['window_size'] == "full":
#            Window.fullscreen = 'auto'
        # Update display state.
        self._display_state = DISPLAY_STATE.ON
        self.dispatch('on_state_change')

    def display_off(self):
        """Turn the display off."""
        # Return if already off.
        if self._display_state == DISPLAY_STATE.OFF: return
        Logger.info("Controller: Turning display off.")
        # Turn display off on Linux with X server.
        subprocess.run("/usr/bin/xset dpms force off", shell=True, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)
        # Update display state.
        self._display_state = DISPLAY_STATE.OFF
        self.dispatch('on_state_change')

    @property
    def display_state(self):
        """Return display state.

        See enumeration DISPLAY_STATE for possible values.

        :return: display state
        :rtype: str
        """
        return self._display_state

    @display_state.setter
    def display_state(self, state):
        """Set display state.

        See enumeration DISPLAY_STATE for possible values.

        :param state: display state
        :type mode: str
        """
        if self._display_state == state: return
        if state == DISPLAY_STATE.ON: self.display_on()
        elif state == DISPLAY_STATE.OFF: self.display_off()
        else:
            raise Exception(f"The selected display state '{state}' is invalid. Acceptable values are '{[ item.value for item in DISPLAY_STATE ]}'.")

    @property
    def display_timeout(self):
        """Return display timeout.

        :return: display timeout in seconds
        :rtype: int
        """
        return self._display_timeout

    @display_timeout.setter
    def display_timeout(self, timeout):
        """Set display timeout.

        :param timeout: display timeout in seconds
        :type timeout: int
        """
        Logger.info(f"Controller: Setting display timeout to {timeout} s.")
        self._display_timeout = timeout

    def pause(self):
        """Pause playing the current slideshow."""
        # Skip if already paused or stopped.
        if self._play_state == PLAY_STATE.PAUSED or self._play_state == PLAY_STATE.STOPPED: return
        Logger.info(f"Controller: Pausing slideshow '{self.slideshow}'.")
        self.root.pause()
        self._play_state = PLAY_STATE.PAUSED
        self.dispatch('on_state_change')

    def play(self):
        """Start/resume playing the current slideshow."""
        # Skip if already playing.
        if self._play_state == PLAY_STATE.PLAYING: return
        Logger.info(f"Controller: Playing/resuming slideshow '{self.slideshow}'.")
        # Start playing current slideshow.
        self.root.play()
        self._play_state = PLAY_STATE.PLAYING
        self.display_on()
        self.touch()
        self.dispatch('on_state_change')

    @property
    def play_state(self):
        """Return play state.

        See enumeration PLAY_STATE for possible values.

        :return: play state
        :rtype: str
        """
        return self._play_state

    @play_state.setter
    def play_state(self, state):
        """Set play state.

        See enumeration PLAY_STATE for possible values.

        :param mode: play state
        :type mode: str
        """
        if self._play_state == state: return
        if state == PLAY_STATE.PLAYING: self.play()
        elif state == PLAY_STATE.PAUSED: self.pause()
        elif state == PLAY_STATE.STOPPED: self.stop()
        else:
            raise Exception(f"The selected play state '{state}' is invalid. Acceptable values are '{[ item.value for item in PLAY_STATE ]}'.")

    def stop(self):
        """Stop playing the current slideshow."""
        # Skip if already stopped.
        if self._play_state == PLAY_STATE.STOPPED: return
        Logger.info(f"Controller: Stopping slideshow '{self.slideshow}'.")
        # Cancel previously scheduled timeout event.
        if self._timeout_event is not None:
            self._timeout_event.cancel()
        # Stop playing current slideshow.
        self.root.stop()
        self._play_state = PLAY_STATE.STOPPED
        self.display_off()
        self.dispatch('on_state_change')

    def previous(self):
        """Change to previous file in slideshow."""
        # Skip if not playing.
        if self._play_state == PLAY_STATE.STOPPED: return
        Logger.info(f"Controller: Changing to previous file in slideshow '{self.slideshow}'.")
        self.root.previous()

    def next(self):
        """Change to next file in slideshow."""
        # Skip if not playing.
        if self._play_state == PLAY_STATE.STOPPED: return
        Logger.info(f"Controller: Changing to next file in slideshow '{self.slideshow}'.")
        self.root.next()

    @property
    def slideshow(self):
        """Return name of the current slideshow.

        :return: slideshow name
        :rtype: str
        """
        return self.root.name

    @slideshow.setter
    def slideshow(self, name):
        """Set current slideshow by its name.

        :param name: slideshow name
        :type name: str
        """
        # Retrieve slideshow by its name. Stick to the current slideshow if
        # specified slideshow does not exist.
        new_root = self._slideshows.get(name, self.root)
        if new_root is not self.root:
            # Save play state and stop playing the current slideshow.
            cur_play_state = self.play_state
            self.stop()
            # Replace the root widget.
            Logger.info(f"Controller: Setting slideshow to '{name}'.")
            Window.add_widget(new_root)
            Window.remove_widget(self.root)
            self.root = new_root
            self.play_state = cur_play_state
            self.dispatch('on_state_change')

    @property
    def slideshows(self):
        """Return names of all slideshows.

        :return: list of slideshow names
        :rtype: list of str
        """
        return list(self._slideshows.keys())

    def touch(self):
        """Update last touch time stamp and prevent screen timeout in display motion mode."""
        # Update last touch time stamp.
        self._last_touch = time.time()
        # Return if display not in motion mode or slideshow stopped.
        if self.display_mode != DISPLAY_MODE.MOTION or self.play_state == PLAY_STATE.STOPPED: return
        # Cancel previously scheduled timeout event.
        if self._timeout_event is not None:
            self._timeout_event.cancel()
        # Restart playing the slideshow.
        self.play()
        # Schedule new timeout event.
        self._timeout_event = Clock.schedule_once(self.on_display_timeout, self._display_timeout)
        # Log next display timeout.
        next_timeout_asc = time.asctime(time.localtime(self._last_touch + self._display_timeout))
        Logger.debug(f"Controller: Controller has been touched. Next display timeout scheduled in {self._display_timeout} s at {next_timeout_asc}.")
