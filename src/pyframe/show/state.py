"""Module providing saved state class."""

import datetime
import os
import yaml

from datetime import datetime

from kivy.logger import Logger


# Maximum age of state file in seconds. State files which are older will be ignored.
MAX_AGE = 120


class SavedState:
    """Saved state class

    Saves the state specified in a dictionary permanently in a YAML file.
    Restores the state upon initiation or request at a later point in time.
    Used to restore the previous state after unplanned termination of the
    application.

    The following properties are provided:
    
    display_state (str) - Current display state
    play_state (str) - Current play_state
    slideshow (str) - Current slideshow
    state (dict) - Current state (includes all previous items)
    """

    def __init__(self, filename, max_age=MAX_AGE):
        """Initialize state instance.
        
        If the file specified by filename exists and the timestamp is younger
        than max_age, the saved state is automatically restored.

        :param filename: name of state file
        :type filename: str
        :param max_age: maximum age of saved state in seconds. Defaults to MAX_AGE.
        :type max_age: int
        """
        self._state = dict()
        self._filename = filename
        
        # Attempt to restore
        self.restore_state(max_age)


    def __del__(self):
        """Destroy state instance.
        
        Deletes the YAML file storing the state. The file only remains in case of
        unplanned termination.
        """
        try:
            os.remove(self._filename)
        except OSError as e:
            Logger.error(f"SavedState: An error occurred while deleting the state file: {e}")


    def __repr__(self):
        """Return string representation of state dictionary.
        
        :return: string representation of state dictionary
        :rtype: str
        """
        return self._state.__repr__()


    def __str__(self):
        """Return YAML representation of state dictionary.
        
        :return: YAML representation of state dictionary
        :rtype: str
        """
        return yaml.dump(self._state)


    def restore_state(self, max_age=None):
        """Restore saved state.
        
        :param max_age: maximum age of saved state in seconds. Defaults to None.
        :type max_age: int
        """
        # Return if state file does not exist.
        if not os.path.isfile(self._filename):
            Logger.info("SavedState: No saved state available.")
            return
            
        # Load state from YAML file.
        try:
            with open(self._filename, "r") as file:
                Logger.info(f"SavedState: Loading saved state from file '{self._filename}'.")
                self._state = yaml.safe_load(file)
        except OSError as e:
            Logger.error(f"SavedState: An error occurred while reading the state file: {e}")
        except yaml.YAMLError as e:
            Logger.error(f"SavedState: An error occurred while parsing the state file: {e}")

        # Only consider saved state if younger than max_age.
        if 'last_updated' in self._state and max_age is not None:
            last_updated = datetime.fromisoformat(self._state['last_updated'])
            if (datetime.now() - last_updated).total_seconds() > max_age:
                Logger.info(f"SavedState: Saved state is older than {max_age} seconds and will be discarded.")
                self._state = dict()


    def save_state(self):
        """Save current state."""
        # Update timestamp.
        self.state['last_updated'] = datetime.now().isoformat()
        # Save state to YAML file.
        try:
            with open(self._filename, "w") as file:
                Logger.debug(f"SavedState: Saving state to file '{self._filename}'.")
                yaml.dump(self._state, file)
        except OSError as e:
            Logger.error(f"SavedState: An error occurred while writing the state file: {e}")


    def update(self, state):
        """ Update current state.
        
        Uses the dictionary update function to update the current state. This
        means that only changes need to be provided. Remaining parts of the
        state dictionary remain unchanged.

        :param state: new state
        :type state: dict
        """
        self._state.update(state)
        self.save_state()

    
    @property
    def display_state(self):
        """Return current display state.

        :return: display state
        :rtype: str
        """
        return self._state.get('display_state')


    @display_state.setter
    def display_state(self, value):
        """Set new display state.
        
        :param value: display state
        :type value: str
        """
        self.update({'display_state': value})


    @property
    def play_state(self):
        """Return current play state.

        :return: play state
        :rtype: str
        """        
        return self._state.get('play_state')


    @play_state.setter
    def play_state(self, value):
        """Set new play state.
        
        :param value: play state
        :type value: str
        """
        self.update({'play_state': value})


    @property
    def slideshow(self):
        """Return current slideshow.

        :return: slideshow
        :rtype: str
        """
        return self._state.get('slideshow')


    @slideshow.setter
    def slideshow(self, value):
        """Set new slideshow.
        
        :param value: slideshow
        :type value: str
        """
        self.update({'slideshow': value})


    @property
    def state(self):
        """Return current state.
        
        :return: state
        :rtype: dict
        """
        return self._state


    @state.setter
    def state(self, value):
        """Set new state.
        
        :param value: state
        :type value: dict
        """
        self._state = value
        self.save_state()