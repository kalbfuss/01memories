"""Module providing saved state class."""

import datetime
import os
import tempfile
import yaml

from datetime import datetime

from kivy.logger import Logger

from .controller import DISPLAY_STATE, PLAY_STATE


# Maximum age of state file in seconds. State files which are older will be ignored.
MAX_AGE = 120


def enum_representer(dumper, data):
    """Represent enumeration as string.
    
    :param dumper: YAML dumper
    :type dumper: yaml.Dumper
    :param data: enumeration
    :type data: enum
    :return: YAML representation of enumeration
    :rtype: yaml.Node
    """
    return dumper.represent_scalar('!enum', f"{data.__class__.__name__}.{data.name}")

def enum_constructor(loader, node):
    """Construct enumeration from string.
    
    :param loader: YAML loader
    :type loader: yaml.Loader
    :param node: YAML node
    :type node: yaml.Node
    :return: enumeration
    :rtype: enum
    """
    value = loader.construct_scalar(node)
    Logger.info(f"State: Constructing enumeration value from '{value}.'")
    enum_name, member_name = value.split('.')
    return globals()[enum_name][member_name]

yaml.add_representer(DISPLAY_STATE, enum_representer)
yaml.add_representer(PLAY_STATE, enum_representer)
yaml.add_constructor('!enum', enum_constructor)


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

    def __init__(self):
        """Initialize state instance.
        
        If the file specified by filename exists and the timestamp is younger
        than max_age, the saved state is automatically restored.

        :param filename: name of state file
        :type filename: str
        :param max_age: maximum age of saved state in seconds. Defaults to MAX_AGE.
        :type max_age: int
        """
        self._state = dict()
        self._filename = os.path.join(tempfile.gettempdir(), f"pyframe.state.{os.getuid()}")
    

    def __del__(self):
        """Destroy state instance.
        
        Deletes the YAML file storing the state. The file only remains in case 
        of unplanned termination.
        """
        try:
            os.remove(self._filename)
        except OSError as e:
            Logger.error(f"State: An error occurred while deleting the state file: {e}")

    def restore_state(self, max_age=MAX_AGE):
        """Restore saved state.
        
        :param max_age: maximum age of saved state in seconds. Defaults to 
          MAX_AGE.
        :type max_age: int
        """
        # Return if state file does not exist.
        if not os.path.isfile(self._filename):
            Logger.info("State: No saved state available.")
            return
            
        # Load state from YAML file.
        try:
            with open(self._filename, "r") as file:
                Logger.info(f"State: Loading saved state from file '{self._filename}'.")
                self._state = yaml.load(file, Loader=yaml.Loader)
                Logger.info(f"State: The following state was restored: {self._state}")
        except OSError as e:
            Logger.error(f"State: An error occurred while reading the state file: {e}")
        except yaml.YAMLError as e:
            Logger.error(f"State: An error occurred while parsing the state file: {e}")

        # Only consider saved state if younger than max_age.
        if 'last_updated' in self._state and max_age is not None:
            last_updated = datetime.fromisoformat(self._state['last_updated'])
            if (datetime.now() - last_updated).total_seconds() > max_age:
                Logger.info(f"State: Saved state is older than {max_age} seconds and will be discarded.")
                self._state = dict()

    def save_state(self):
        """Save current state."""
        # Update timestamp.
        self.state['last_updated'] = datetime.now().isoformat()
        # Save state to YAML file.
        try:
            with open(self._filename, "w") as file:
                Logger.info(f"State: Saving state to file '{self._filename}'.")
                yaml.dump(self._state, file)
        except OSError as e:
            Logger.error(f"State: An error occurred while writing the state file: {e}")

    def _update_value(self, state):
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
    def _display_state(self):
        """Return current display state.

        :return: display state
        :rtype: str
        """
        return self._state.get('display_state')


    @_display_state.setter
    def _display_state(self, value):
        """Set new display state and save it.
        
        :param value: display state
        :type value: str
        """
        self._update_value({'display_state': value})

    @property
    def _play_state(self):
        """Return current play state.

        :return: play state
        :rtype: str
        """        
        return self._state.get('play_state')


    @_play_state.setter
    def _play_state(self, value):
        """Set new play state and save it.
        
        :param value: play state
        :type value: str
        """
        self._update_value({'play_state': value})

    @property
    def _slideshow(self):
        """Return current slideshow.

        :return: slideshow
        :rtype: str
        """
        return self._state.get('slideshow')

    @_slideshow.setter
    def _slideshow(self, value):
        """Set new slideshow and save it.
        
        :param value: slideshow
        :type value: str
        """
        self._update_value({'slideshow': value})

    @property
    def state(self):
        """Return current state.
        
        :return: state
        :rtype: dict
        """
        return self._state


    @state.setter
    def state(self, value):
        """Set new state and save it.
        
        :param value: state
        :type value: dict
        """
        self._state = value
        self.save_state()