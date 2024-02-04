"""Module providing slideshow video class."""

from kivy.graphics import PushMatrix, PopMatrix, Rotate, Color, Rectangle
from kivy.logger import Logger
from kivy.uix.video import Video
from kivy.uix.widget import Widget

from .base import LabeledContent


class SlideshowVideo(LabeledContent):
    """Video slideshow widget.

    Loads the video from the specified File and starts playing it as soon as the
    widget becomes visible. The video is scaled to fit the entire widget,
    respecting the aspect ratio.
    """

    def __init__(self, file, config):
        """Initialize slideshow video instance.

        :param file: Repository file instance for the video to be displayed.
        :type file: repository.File
        :param config: Dictionary with the following entries:
            rotation: Angle in degrees (int) by which the video is rotated clockwise.
            bgolor: Canvas background color (list(3)) for areas, which are not covered by the video.
            resize: Mode (str) for resizing of videos. Must equal "fit" or "fill".
        :type config: dict
        """
        super().__init__(file, config)
        # Calculate total rotation from image rotation and rotation configured for the slideshow.
        # To avoid negative values and values beyond 360°, we additionally apply a modulo operation.
        self._rotation = (file.rotation - config['rotation']) % 360
        self._bgcolor = config['bg_color']
        self._resize = config['resize']
        self._video = Video(source=file.source, state='stop', allow_stretch=True, options={'eos': 'loop'})
        self.add_widget(self._video, len(self.children))
        # Call update_canvas method when the size of the widget changes.
        self.bind(size=self.update_canvas)
        # Call autoplay method when the widget becomes visible/invisible.
        self.bind(parent=self.autoplay)

    def autoplay(self, *args):
        """Start/stop playing the video when the widget becomes visible/invisible."""
        if self.parent is None:
            self.stop()
        else:
            self.play()

    def play(self):
        """Start playing content."""
        self._video.state = 'play'

    def stop(self):
        """Stop playing content."""
        self._video.state = 'stop'

    def update_canvas(self, *args):
        """Update canvas when the size of the widget changes."""
        # Clear before and after groups of video canvas.
        self._video.canvas.before.clear()
        self._video.canvas.after.clear()

        # Fill canvas with background color.
        with self._video.canvas.before:
            Color(*self._bgcolor)
            Rectangle(pos=(0, 0), size=self.size)

        # Determine widget and video aspect ratios.
        widget_ratio = self.width/self.height
        # We need to rely on the file meta data in this case since the Kivy
        # video class does not have a video_ratio attribute and the
        # dimensions of the video widget have not been adjusted yet.
        if self._file.width > 0 and self._file.height > 0:
            video_ratio = self._file.width/self._file.height
        else:
            video_ratio = 16/9
        # Correct video aspect ratio for video rotation. i.e. aspect ratio
        # corresponds to the ratio after rotation.
        if abs(self._rotation) == 90 or abs(self._rotation == 270):
            video_ratio = 1/video_ratio

        # Tranform video to fill the video slideshow widget. Only videos with
        # the same orientation will be resized to fill the widget. Videos with a
        # different orientation will be resized to fit the widget.
        if self._resize == "fill":

            # Determine maximum dimension for widget with landscape orientation.
            if widget_ratio > 1:
                # Determine required maximum dimension for the rotation
                # transformation based on aspect ratios.
                if widget_ratio > video_ratio and video_ratio > 1:
                    max_dim = self.width
                elif widget_ratio <= video_ratio and video_ratio >= 1:
                    max_dim = round(self.height*video_ratio)
                elif widget_ratio >= video_ratio and video_ratio <= 1:
                    max_dim = self.height
                else:  # widget_ratio < video_ratio and video_ratio < 1
                    max_dim = round(self.width/video_ratio)
            # Determine maximum dimension for widget with portrait orientation.
            else:  # widget_ratio <= 1:
                if widget_ratio > video_ratio and video_ratio > 1:
                    max_dim = round(self.height*video_ratio)
                    # max_dim = self.width
                elif widget_ratio <= video_ratio and video_ratio >= 1:
                    max_dim = self.width
                    # max_dim = round(self.height*video_ratio)
                elif widget_ratio >= video_ratio and video_ratio <= 1:
                    # max_dim = self.height
                    max_dim = round(self.width/video_ratio)
                else:  # widget_ratio < video_ratio and video_ratio < 1
                    # max_dim = round(self.width/video_ratio)
                    max_dim = self.height

            # Set size of video widget to square with maximum dimension
            self._video.size = (max_dim, max_dim)
            # Adjust position of video widget within slideshow video widget
            # to center rotated video.
            self._video.x = round(self.x + (self.width - max_dim)/2)
            self._video.y = round(self.y + (self.height - max_dim)/2)

            # Apply rotation if not zero
            if self._rotation != 0:
                with self._video.canvas.before:
                    PushMatrix()
                    Rotate(angle=self._rotation, origin=self._video.center, axis=(0, 0, 1))
                with self._video.canvas.after:
                    PopMatrix()

        # Default is to fit the video to the canvas
        else:  # self._resize == "fit"

            # Rotate canvas if required.
            if (self._rotation != 0):
                # Determine required maximum dimension for the rotation
                # transformation based on aspect ratios.
                if widget_ratio > video_ratio and video_ratio > 1:
                    max_dim = round(self.height*video_ratio)
                elif widget_ratio <= video_ratio and video_ratio >= 1:
                    max_dim = self.width
                elif widget_ratio >= video_ratio and video_ratio <= 1:
                    max_dim = self.height
                else:  # widget_ratio < video_ratio and video_ratio < 1
                    max_dim = round(self.width/video_ratio)

                # Set size video widget to square with maximum dimension
                self._video.size = (max_dim, max_dim)
                # Adjust position of video widget within slideshow video widget
                # to center rotated video.
                self._video.x = round(self.x + (self.width - max_dim)/2)
                self._video.y = round(self.y + (self.height - max_dim)/2)

                # Apply rotation.
                with self._video.canvas.before:
                    PushMatrix()
                    Rotate(angle=self._rotation, origin=self._video.center, axis=(0, 0, 1))
                with self._video.canvas.after:
                    PopMatrix()
            else:
                self._video.size = self.size

        # Log debug information
#       Logger.debug(f"Video uuid: {self._file.uuid}")
#       Logger.debug(f"Video type: {self._file.type}")
#       Logger.debug(f"Video source: {self._file.source}")
#       Logger.debug(f"Video orientation: {self._file.orientation}")
#       Logger.debug(f"Video rotation: {self._file.rotation}")
#       Logger.debug(f"Total rotation: {self._rotation}")
#       Logger.debug(f"Widget width: {self.width}")
#       Logger.debug(f"Widget height: {self.height}")
#       Logger.debug(f"Widget aspect ratio: {widget_ratio}")
#       Logger.debug(f"max_dim: {max_dim}")
#       Logger.debug(f"Video width: {self._video.width}")
#       Logger.debug(f"Video height: {self._video.height}")
#       Logger.debug(f"Video aspect ratio: {video_ratio}")
#       Logger.debug(f"Video x: {self._video.x}")
#       Logger.debug(f"Video y: {self._video.y}")
#       Logger.debug(f"Video center: {self._video.center}")
