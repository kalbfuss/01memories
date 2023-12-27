"""Module providing Pyframe controller interface."""

from abc import ABC, abstractmethod
from enum import Enum


class DISPLAY_MODE(str, Enum):
    MOTION = "motion"
    STATIC = "static"

class DISPLAY_STATE(str, Enum):
    OFF = "off"
    ON = "on"

class PLAY_STATE(str, Enum):
    PAUSED = "paused"
    PLAYING = "playing"
    STOPPED = "stopped"


class Controller(ABC):
    """Pyframe controller.

    Provides interface for the control of photo frames. The class is abstract
    and needs to be implemented by the inheriting class.
    """

    @property
    @abstractmethod
    def current_file(self):
        """Return the current repository file.

        :return: current file
        :rtype: repository.File
        """
        pass

    @property
    @abstractmethod
    def display_mode(self):
        """Return display mode.

        See enumeration DISPLAY_MODE for possible values.

        :return: display mode
        :rtype: str
        """
        pass

    @display_mode.setter
    @abstractmethod
    def display_mode(self, mode):
        """Set display mode.

        See enumeration DISPLAY_MODE for possible values.

        :param mode: display mode
        :type mode: str
        """
        pass

    @abstractmethod
    def display_on(self):
        """Turn display on."""
        pass

    @abstractmethod
    def display_off(self):
        """Turn display off."""
        pass

    @property
    @abstractmethod
    def display_state(self):
        """Return display state.

        See enumeration DISPLAY_STATE for possible values.

        :return: display state
        :rtype: str
        """
        pass

    @display_state.setter
    @abstractmethod
    def display_state(self, state):
        """Set display state.

        See enumeration DISPLAY_STATE for possible values.

        :param state: display state
        :type mode: str
        """
        pass

    @property
    @abstractmethod
    def display_timeout(self):
        """Return display timeout.

        :return: display timeout in seconds
        :rtype: int
        """
        pass

    @display_timeout.setter
    @abstractmethod
    def display_timeout(self, timeout):
        """Set display timeout.

        :param timeout: display timeout in seconds
        :type timeout: int
        """
        pass

    @abstractmethod
    def next(self):
        """Change to next file in slideshow."""
        pass

    @abstractmethod
    def pause(self):
        """Pause playing the current slideshow."""
        pass

    @abstractmethod
    def play(self):
        """Start playing the current slideshow."""
        pass

    @property
    @abstractmethod
    def play_state(self):
        """Return play state.

        See enumeration PLAY_STATE for possible values.

        :return: play state
        :rtype: str
        """
        pass

    @play_state.setter
    @abstractmethod
    def play_state(self, state):
        """Set play state.

        See enumeration PLAY_STATE for possible values.

        :param mode: play state
        :type mode: str
        """
        pass

    @abstractmethod
    def previous(self):
        """Change to previous file in slideshow."""
        pass

    @property
    @abstractmethod
    def slideshow(self):
        """Return name of the current slideshow.

        :return: name of slideshow
        :rtype: str
        """
        pass

    @slideshow.setter
    @abstractmethod
    def slideshow(self, name):
        """Set current slideshow by its name.

        :param name: name of slideshow
        :type name: str
        """
        pass

    @property
    @abstractmethod
    def slideshows(self):
        """Return names of all slideshows.

        :return: list of slideshow names
        :rtype: list of str
        """
        pass

    @abstractmethod
    def stop(self, force=False):
        """Stop playing the current slideshow."""
        pass

    @abstractmethod
    def touch(self):
        """Touch to prevent screen timeout."""
        pass
