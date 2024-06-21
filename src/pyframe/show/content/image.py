"""Module providing slideshow image class."""

from kivy.graphics import PushMatrix, PopMatrix, Rotate, Color, Rectangle
from kivy.logger import Logger
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from .base import LabeledContent


class SlideshowImage(LabeledContent):
    """Image slideshow widget.

    Loads the image from the specified File and starts playing it as soon as the
    widget becomes visible. The image is scaled to fit the entire widget,
    respecting the aspect ratio.
    """

    def __init__(self, file, config):
        """Initialize slideshow image instance.

        :param file: Repository file instance for the image to be displayed.
        :type file: repository.File
        :param config: Dictionary with the following entries:
            rotation: Angle in degrees (int) by which the image is rotated clockwise.
            bgolor: Canvas background color (list(3)) for areas, which are not covered by the image.
            resize: Mode (str) for resizing of images. Must equal "fit" or "fill".
        :type config: dict
        """
        super().__init__(file, config)
        # Calculate total rotation from image rotation and rotation configured for the slideshow.
        # To avoid negative values and values beyond 360°, we additionally apply a modulo operation.
        self._rotation = (file.rotation - config['rotation']) % 360
        self._bgcolor = config['bg_color']
        self._resize = config['resize']
        # Create and add image widget
        self._image = Image(source=file.source, mipmap=True)
        self.add_widget(self._image, len(self.children))
        # Call update_canvas method when the size of the widget changes.
        self.bind(size=self.update_canvas)

    def update_canvas(self, *args):
        """Update canvas when the size of the widget changes."""
        # Clear before and after groups of image canvas.
        self._image.canvas.before.clear()
        self._image.canvas.after.clear()

        # Fill canvas with background color.
        with self._image.canvas.before:
            Color(*self._bgcolor)
            Rectangle(pos=(0, 0), size=self.size)

        # Determine aspect ratios of image slideshow widget (this widget)
        # and image.
        widget_ratio = self.width/self.height
        image_ratio = self._image.image_ratio
        # Correct image aspect ratio for image rotation. i.e. aspect ratio
        # corresponds to the ratio after rotation.
        if abs(self._rotation) == 90 or abs(self._rotation == 270):
            image_ratio = 1/image_ratio

        # Tranform image to fill the image slideshow widget. Only images with
        # the same orientation will be resized to fill the widget. Images with a
        # different orientation will be resized to fit the widget.
        if self._resize == "fill":

            # Determine maximum dimension for widget with landscape orientation.
            if widget_ratio > 1:
                # Determine required maximum dimension for the rotation
                # transformation based on aspect ratios.
                if widget_ratio > image_ratio and image_ratio > 1:
                    max_dim = self.width
                elif widget_ratio <= image_ratio and image_ratio >= 1:
                    max_dim = round(self.height*image_ratio)
                elif widget_ratio >= image_ratio and image_ratio <= 1:
                    max_dim = self.height
                else:  # widget_ratio < image_ratio and image_ratio < 1
                    max_dim = round(self.width/image_ratio)
            # Determine maximum dimension for widget with portrait orientation.
            else:  # widget_ratio <= 1:
                if widget_ratio > image_ratio and image_ratio > 1:
                    max_dim = round(self.height*image_ratio)
                    # max_dim = self.width
                elif widget_ratio <= image_ratio and image_ratio >= 1:
                    max_dim = self.width
                    # max_dim = round(self.height*image_ratio)
                elif widget_ratio >= image_ratio and image_ratio <= 1:
                    # max_dim = self.height
                    max_dim = round(self.width/image_ratio)
                else:  # widget_ratio < image_ratio and image_ratio < 1
                    # max_dim = round(self.width/image_ratio)
                    max_dim = self.height

            # Set size of image widget to square with maximum dimension
            self._image.size = (max_dim, max_dim)
            # Adjust position of image widget within slideshow image widget
            # to center rotated image.
            self._image.x = round(self.x + (self.width - max_dim)/2)
            self._image.y = round(self.y + (self.height - max_dim)/2)

            # Apply rotation if not zero
            if self._rotation != 0:
                with self._image.canvas.before:
                    PushMatrix()
                    Rotate(angle=self._rotation, origin=self._image.center, axis=(0, 0, 1))
                with self._image.canvas.after:
                    PopMatrix()

        # Default is to fit the image to the canvas
        else:  # self._resize == "fit"

            # Resize and rotate the image if required.
            if self._rotation != 0:
                # Determine required maximum dimension for the rotation
                # transformation based on aspect ratios.
                if widget_ratio > image_ratio and image_ratio > 1:
                    max_dim = round(self.height*image_ratio)
                elif widget_ratio <= image_ratio and image_ratio >= 1:
                    max_dim = self.width
                elif widget_ratio >= image_ratio and image_ratio <= 1:
                    max_dim = self.height
                else:  # widget_ratio < image_ratio and image_ratio < 1
                    max_dim = round(self.width/image_ratio)

                # Set size of image widget to square with maximum dimension
                self._image.size = (max_dim, max_dim)
                # Adjust position of image widget within slideshow image widget
                # to center rotated image.
                self._image.x = round(self.x + (self.width - max_dim)/2)
                self._image.y = round(self.y + (self.height - max_dim)/2)

                # Apply rotation.
                with self._image.canvas.before:
                    PushMatrix()
                    Rotate(angle=self._rotation, origin=self._image.center, axis=(0, 0, 1))
                with self._image.canvas.after:
                    PopMatrix()

            # Set size of image widget to size of image slideshow widget (this
            # widget) otherwise and let image widget do the scaling.
            else:  # self._rotation == 0:
                self._image.size = self.size

            # Log debug information
#            Logger.debug(f"Image uuid: {self._file.uuid}")
#            Logger.debug(f"Image type: {self._file.type}")
#            Logger.debug(f"Image source: {self._file.source}")
#            Logger.debug(f"Image orientation: {self._file.orientation}")
#            Logger.debug(f"Image rotation: {self._file.rotation}")
#            Logger.debug(f"Total rotation: {self._rotation}")
#            Logger.debug(f"Widget width: {self.width}")
#            Logger.debug(f"Widget height: {self.height}")
#            Logger.debug(f"Widget aspect ratio: {widget_ratio}")
#            Logger.debug(f"max_dim: {max_dim}")
#            Logger.debug(f"Image width: {self._image.width}")
#            Logger.debug(f"Image height: {self._image.height}")
#            Logger.debug(f"Image aspect ratio: {image_ratio}")
#            Logger.debug(f"Image x: {self._image.x}")
#            Logger.debug(f"Image y: {self._image.y}")
#            Logger.debug(f"Image center: {self._image.center}")
