"""Module providing slideshow scheduler."""

import schedule
import subprocess

from kivy.clock import Clock
from kivy.logger import Logger, LOG_LEVELS
from schedule import ScheduleValueError

from repository import ConfigError, check_param, check_valid_required

from .controller import DISPLAY_MODE, PLAY_STATE


class Scheduler:
    """Slideshow scheduler.

    The slideswhow scheduler implements a simple, YAML/dict configurable
    scheduler for the display of slideshow during certain periods.
    The scheduler uses the python schedule package [1]. The run_pending method
    of the default scheduler is triggered by the Kivy Clock.
    Scheduling is event based. Events can be be used to turn the display on or
    off and select the slideshow to be displayed.

    [1] https://github.com/dbader/schedule
    """

    # Required and valid configuration parameters
    CONF_REQ_KEYS = {'time'}
    CONF_VALID_KEYS = {'display_mode', 'display_timeout', 'play_state', 'slideshow'} | CONF_REQ_KEYS

    def __init__(self, config, app):
        """ Initialize scheduler instance.

        :param config: Scheduler configuration from the corresponding
            configuration file section.
        :type config: dict
        :param app: Pyframe application
        :type app: pyframe.App
        :raises: ConfigError
        """
        self._app = app
        self._event = None

        # Build schedule from configuration
        Logger.info("Scheduler: Building schedule from configuration.")
        for event, event_config in config.items():

            try:
                # Check the configuration for valid and required parameters.
                check_valid_required(event_config, self.CONF_VALID_KEYS, self.CONF_REQ_KEYS)
                # Check parameter values.
                check_param('display_mode', event_config, required=False, options={ item.value for item in DISPLAY_MODE })
                check_param('play_state', event_config, required=False, options={ item.value for item in PLAY_STATE })
                check_param('slideshow', event_config, required=False, options=self._app.slideshows)
                check_param('display_timeout', event_config, required=False, is_int=True, gr=0)
                # Schedule event.
                schedule.every().day.at(event_config['time']).do(self.on_event, event, event_config)
                Logger.info(f"Scheduler: Event '{event}' scheduled at '{event_config['time']}'.")
            # Catch all configuration and schedule errors.
            except (ConfigError, TypeError, ScheduleValueError) as e:
                raise ConfigError(f"Error in the configuration of event '{event}'. {e}", event_config)

        # Turn display off
        self._app.display_off()
        # Set clock interval and callback function.
        self.run_pending(0)

    def on_event(self, event, config):
        """Handle scheduled events."""
        Logger.info(f"Scheduler: Event '{event}' fired.")
        # Set display mode if specified.
        display_mode = config.get('display_mode')
        if display_mode is not None:
            self._app.display_mode = display_mode
        # Set display timeout if specified.
        display_timeout = config.get('display_timeout')
        if display_timeout is not None:
            self._app.display_timeout = display_timeout
        # Set slideshow if specified, turn display on and start playing.
        slideshow = config.get('slideshow')
        if slideshow is not None:
            self._app.slideshow = slideshow
        # Set display state if specified.
        play_state = config.get('play_state')
        if play_state is not None:
            self._app.play_state = play_state

    def run_pending(self, dt):
        """Run pending schedule jobs."""
        schedule.run_pending()
        self._event = Clock.schedule_once(self.run_pending, schedule.idle_seconds())

    def stop(self):
        """Stop scheduler."""
        if self._event is not None:
            self._event.cancel()
            self._event = None
