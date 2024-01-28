"""Module providing Pyframe slideshow application."""

import copy
import kivy.app
import logging
import os.path
import repository.local
import repository.webdav
import subprocess
import signal
import sys
import time
import traceback
import yaml

#from importlib import import_module
from repository import ConfigError, Index, Repository, UuidError, check_param, check_valid_required

from kivy.base import ExceptionManager, stopTouchApp
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.logger import Logger, LOG_LEVELS

from .slideshow import Slideshow
from .scheduler import Scheduler
from .controller import Controller, DISPLAY_MODE, DISPLAY_STATE, PLAY_STATE
from .mqtt import MqttInterface

from ..common import _create_repositories, _configure_logging, _load_config, _load_index


def signal_handler(sig, frame):
    """Close application after SIGINT and SIGTERM signals."""
    Logger.warn(f"App: Signal '{signal.strsignal(sig)}' received. Preparing for safe exit.")
    app.close()
    stopTouchApp()


def run_app():
    """Start slideshow."""
    # Catch interrupt and term signals and exit gracefully.
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    # Run slideshow.
    app = App()
    app.run()
    # Clean up and exit.
    app.close()
    stopTouchApp()


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
    """Pyframe slideshow application."""

    # Required and valid configuration parameters
    CONF_REQ_KEYS = {'display_mode', 'display_state', 'display_timeout', 'enable_exception_handler', 'enable_mqtt', 'enable_logging', 'enable_scheduler', 'index', 'log_level', 'log_dir', 'repositories', 'slideshows', 'window_position', 'window_size'} | Slideshow.CONF_REQ_KEYS
    CONF_VALID_KEYS = {'cache', 'index_update_at', 'index_update_interval', 'mqtt', 'schedule' } | CONF_REQ_KEYS | Slideshow.CONF_VALID_KEYS


    def _create_slideshows(self):
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
                raise ConfigError(f"Error in the configuration of slideshow '{name}'. {e}", config)

        # Exit application if no valid slideshows have been defined.
        if len(self._slideshows.items()) == 0:
            raise ConfigError("Exiting application as no valid slideshows have been defined.")


    def _init_display(self):
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

        # Set window position.
        value = config['window_position']
        if type(value) is list and len(value) == 2 and value[0] >= 0 and value[1] >= 0:
            Window.left = value[0]
            Window.top = value[1]
        elif value == "auto":
            pass
        else:
            raise ConfigError(f"Invalid value '{value}' for parameter 'window_position' specified. Valid values are [left, top] and 'auto'.", config)

        # Set window size.
        value = config['window_size']
        if type(value) is list and len(value) == 2 and value[0] > 0 and value[1] > 0:
            Window.size = (value)
        elif value == "full":
            Window.fullscreen = 'auto'
        else:
            raise ConfigError(f"Invalid value '{value}' for parameter 'window_size' specified. Valid values are [width, height] and 'full'.", config)
        # Disable display of mouse cursor
        Window.show_cursor = False


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
        self._config = _load_config()
        # Check the configuration for valid and required parameters.
        check_valid_required(self._config, self.CONF_VALID_KEYS, self.CONF_REQ_KEYS)

        # Configure logging.
        _configure_logging(self._config, "pyframe.log")
        # Load/create index.
        self._index = _load_index(self._config)
        # Create repositories from configuration.
        _create_repositories(self._config, self._index)
        # Create slideshows.
        self._create_slideshows()

        # Make first slideshow the main root widget.
        self.root = next(iter(self._slideshows.values()))

        # Create mqtt interface if configured and activated.
        value = self._config.get('enable_mqtt')
        if 'mqtt' in self._config and (value == "on" or value is True):
            try:
                self._mqtt_interface = MqttInterface(self._config['mqtt'], self)
            except ConfigError as e:
                raise ConfigError(f"Error in the MQTT interface configuration. {e}", e.config)
            except Exception as e:
                raise Exception(f"MQTT: {e}")

        # Initialize display
        self._init_display()

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
#        subprocess.run("/usr/bin/xset dpms force off", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
