"""Module providing slideshow content base widget."""

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from datetime import datetime
from math import ceil


class ContentBase(Widget):
    """Slideshow content base widget.

    Base class defining standard interface for slideshow content widgets.
    """

    def __init__(self, file, config):
        """Initialize slideshow content base instance."""
        super().__init__()
        self._file = file
        self._config = config

    @property
    def config(self):
        """Return content configuration.

        :return: configuration passed to the constructor
        :rtype: dict
        """
        return self._config

    @property
    def file(self):
        """Return linked repository file.

        Note that the value None may be returned in cases where no valid file
        is linked to the content widget.

        :return: linked repository file
        :rtype: repository.file
        """
        return self._file

    def play(self):
        """Start playing content."""
        pass

    def stop(self):
        """Stop playing content."""
        pass


class ErrorMessage(ContentBase):
    """Slideshow error message widget."""

    def __init__(self, message, config):
        """Initialize the slideshow message instance."""
        super().__init__(None, config)
        self._message = message
        self._bgcolor = config['bg_color']

        # Determine label color based on background color.
        lcolor = Color(*self._bgcolor)
        if lcolor.v > 0.5:
            lcolor.hsv = [ 0, 0, 0 ]
        else:
            lcolor.hsv = [ 0, 0, 1 ]

        # Create label for error message.
        self._label = Label(markup=True, halign="center", valign="center", color=lcolor.rgba, font_blended=True, text=message)
        self.add_widget(self._label)
        # Call update_canvas method after the widget's size has been set.
        self.bind(size=self.update_canvas)

    def update_canvas(self, *args):
        """Update canvas when the size of the widget changes.

        Fills canvas with the background color and adjusts the label position,
        size, font size and padding.
        """
        # Clear canvas and fill with background color.
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self._bgcolor)
            Rectangle(pos=(0, 0), size=self.size)

        # Position and resize label.
        self._label.pos = (self.x, self.y)
        self._label.size = (self.width, self.height)
        self._label.text_size = self._label.size
        # Set font size and padding of label.
        font_size = round(self.config.get('label_font_size', 0.05) * self.height)
        self._label.font_size = font_size
        padding = round(self.config.get('label_padding', 0.05) * self.width)
        self._label.padding = (padding, padding)

    @property
    def message(self):
        """Return message text.

        :return: message text
        :rtype: str
        """
        return self._message


class LabeledContent(ContentBase):
    """Slideshow labeled content base widget.

    Base class for slideshow image and video widgets. Provides basic
    functionality for labeling.
    """

    def __init__(self, file, config):
        """Initialize the labeled content instance."""
        super().__init__(file, config)

        self._events = list()

        # Create and add white (foreground) and black (shadow) labels.
        self._wlabel = Label(markup=True, halign="right", valign="bottom", color=(1, 1, 1, 1), font_blended=True)
        self._blabel = Label(markup=True, halign="right", valign="bottom", color=(0, 0, 0, 1))
        self.add_widget(self._blabel)
        self.add_widget(self._wlabel)
        # Set the label text.
        mode = config.get('label_mode', "off")
        if mode is True or mode == "on" or mode == "auto":
            label = self.label
            self._wlabel.text = label
            self._blabel.text = label
        # Call _adjust_label method after the widget's size has been set.
        self.bind(size=self.adjust_label)

#    def __del__(self):
#        """Delete the labeled content instance."""
#        # Cancel any clock events.
#        while self._events:
#            event = self._events.pop()
#            event.cancel()

    def adjust_label(self, *args):
        """Adjust label when the widget becomes visible and its size is set."""
        # Set font size.
        font_size = round(self.config.get('label_font_size', 0.05) * min(self.height, self.width))
        self._wlabel.font_size = font_size
        self._blabel.font_size = font_size
        # Set padding.
        padding = round(self.config.get('label_padding', 0.05) * min(self.height, self.width))
        self._wlabel.padding = (padding, padding)
        self._blabel.padding = (padding, padding)
        # Resize labels.
        offset = ceil(0.03*font_size)
        self._wlabel.pos = (self.x, self.y + offset)
        self._wlabel.size = (self.width - offset, self.height)
        self._wlabel.text_size = self._wlabel.size
        self._blabel.pos = (self.x + offset, self.y)
        self._blabel.size = (self.width - offset, self.height - offset)
        self._blabel.text_size = self._blabel.size
        # Schedule events to turn labels off and on.
        mode = self.config.get('label_mode', "on")
        pause = self.config.get('pause')
        duration = self.config.get('label_duration', 24)
        if mode == "auto" and pause is not None and 2*duration < pause:
            self._events.append(Clock.schedule_once(self.label_off, duration))
            self._events.append(Clock.schedule_once(self.label_on, pause - duration))

    def label_off(self, dt=0):
        "Turn label off."
        self._wlabel.text = ""
        self._blabel.text = ""

    def label_on(self, dt=0):
        "Turn label on."
        self._wlabel.text = self.label
        self._blabel.text = self.label

    @property
    def config(self):
        """Return content configuration.

        :return: configuration passed to the constructor
        :rtype: dict
        """
        return self._config

    @property
    def file(self):
        """Return linked repository file.

        :return: linked repository file
        :rtype: repository.file
        """
        return self._file

    @property
    def label(self):
        """Return label text.

        The label text is built from properties and meta data of the linked
        file. Text creation can be controlled via the configuration.

        :return: label text
        :rtype: str
        """
        label = str()
        label_content = self.config.get('label_content', "short")
        # Add description and separate if available.
        description = self.file.description
        if description:
            label= f"[b]{description}[/b] · "
        # Return if only description requested.
        if label_content == "description": return
        # Add shortened geopgraphical location (if available)
        location = self.file.location
        if location is not None:
            location, _, country = str.rpartition(location, ",")
            location, _, region = str.rpartition(location, ",")
            location, _, city = str.rpartition(location, ",")
            # Dirty hack to replace lengthy
            if city == "":
                label = label + f"{country.strip()} · "
            else:
                label = label + f"{city.strip()}, {country.strip()} · "
        # Format and append creation date.
        if label_content == "short":
            date_str = self.file.creation_date.strftime("%Y-%m-%d")
        else:
            date_str = self.file.creation_date.strftime("%Y-%m-%d %H:%M")
        label = label + f"{date_str}"
        # Return if only short label requested.
        if label_content == "short": return label
        # Format and append tags if any.
        if self.file.tags:
            label = label + " ·[i]" + "".join(f" #{tag}" for tag in self.file.tags) + "[/i]"
        # Append file and repository uuid.
        label = label + f" · {self.file.uuid} [i]in[/i] {self.file.rep.uuid}"
        return label

    def on_parent(self, *largs):
        """Unschedule all clock events upon loss of parent.

        Callback function for parent property change events. Cancels all
        scheduled clock events if widget is removed from parent, i.e. parent
        is set to None.
        """
        # Cancel any clock events.
        if self.parent is None:
            while self._events:
                event = self._events.pop()
                event.cancel()
