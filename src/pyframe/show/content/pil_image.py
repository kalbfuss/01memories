"""Module providing slideshow image class using PIL for image loading and manipulation."""

import random

from kivy.animation import Animation
from kivy.graphics import Color, Rectangle
from kivy.graphics.texture import Texture
from kivy.graphics.transformation import Matrix
from kivy.logger import Logger
from kivy.uix.image import Image
from kivy.uix.scatter import Scatter

from PIL import Image as PilImage

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
        self._rotation = (config['rotation'] - file.rotation) % 360
        self._bgcolor = config['bg_color']
        self._resize = config['resize']
        self._pause = config['pause']
        # Create nested image and scatter widgets.
        self._image = Image()
        self._scatter = Scatter()
        self._scatter.add_widget(self._image)
        self.add_widget(self._scatter, len(self.children))

        if(config['enable_animation']):
            # Initial values for zoom animation.
            self._zoom = 1.0
            self._anchor = (0, 0)
            # Create zoom animation.            
            self._animation = Animation(_zoom=config['max_zoom'], duration=config['pause'], t='in_out_sine')
            self._animation.bind(on_progress=self.on_progress)
            self._animation.start(self)
        
        # Call update_canvas method when the size of the widget changes.
        self.bind(size=self.update_canvas)


    def on_progress(self, *args):
        """Adjust zoom level for the next animation frame."""
        # Reset transformation matrix
        self._scatter.transform = Matrix().identity()
        # Apply new zoom factor
        matrix = Matrix().scale(self._zoom, self._zoom, self._zoom)
        self._scatter.apply_transform(matrix, anchor=self._anchor)        


    def update_canvas(self, *args):
        """Update canvas when the size of the widget changes."""

        # Adjust image size to parent widget size.
        self._image.size = self.size

        # Clear before and after groups of image canvas.
        self._image.canvas.before.clear()
        self._image.canvas.after.clear()

        # Fill image canvas with background color.
        with self._image.canvas.before:
            Color(*self._bgcolor)
            Rectangle(pos=(0, 0), size=self.size)

        # Load image with PIL.
        pil_image = PilImage.open(self._file.source)
        #pil_image = pil_image.transpose(PilImage.Transpose.FLIP_TOP_BOTTOM)

        # Rotate image as required.
        if self._rotation == 90:
            pil_image = pil_image.transpose(PilImage.Transpose.ROTATE_90)
        elif self._rotation == 180:
            pil_image = pil_image.transpose(PilImage.Transpose.ROTATE_180)
        elif self._rotation == 270:
            pil_image = pil_image.transpose(PilImage.Transpose.ROTATE_270)
        
        # Determine aspect ratios of image slideshow widget (this widget)
        # and image.
        widget_ratio = self.width/self.height
        image_ratio = pil_image.width/pil_image.height 

        # Tranform image to fill the image slideshow widget. Only images with
        # the same orientation will be resized to fill the widget. Images with
        # a different orientation will be resized to fit the widget.
        if self._resize == "fill":
            if widget_ratio >= image_ratio and image_ratio >= 1:
                self._image.fit_mode = "cover"
                width = self.width
                height = int(self.width/image_ratio)
            elif widget_ratio >= image_ratio and image_ratio < 1:
                self._image.fit_mode = "contain"
                width = int(image_ratio * self.height)
                height = self.height
            elif widget_ratio < image_ratio and image_ratio >= 1:
                self._image.fit_mode = "cover"
                width = int(image_ratio * self.height)
                height = self.height
            else:
                self._image.fit_mode = "contain"
                width = self.width
                height = int(self.width/image_ratio)
        
        # Default is to fit the image to the canvas
        else:  # self._resize == "fit"
            self._image.fit_mode = "contain"
            if widget_ratio >= image_ratio:
                width = int(image_ratio * self.height)
                height = self.height
            else:
                width = self.width
                height = int(self.width/image_ratio)

        # Resize PIL image.
        pil_image = pil_image.resize((width, height), PilImage.Resampling.LANCZOS)

        # Create texture from PIL image and assign to Kivy image widget.
        texture = Texture.create(size=(pil_image.width, pil_image.height), mipmap=False)
        texture.blit_buffer(pil_image.tobytes(), colorfmt='rgb', bufferfmt='ubyte')
        texture.flip_vertical()
        self._image.texture = texture

        # Set anchor for the zoom animation.
        if self._config['enable_animation']:
            # Widget and image have same orientation.
            if (widget_ratio >= 1 and image_ratio >= 1) or (widget_ratio < 1 and image_ratio < 1):
                self._anchor = (random.randint(0, self.width), random.randint(int(self.height/2), self.height))
            # Widget has landscape and image portrait orientation.
            elif widget_ratio >= 1 and image_ratio < 1:
                self._anchor = (int(self.width/2), random.randint(int(self.height/2), self.height))
            # Widget has portrait and image landscape orientation.
            elif widget_ratio < 1 and image_ratio >= 1:
                self._anchor = (random.randint(0, self.width), int(self.height/2))


        # Log debug information
#        Logger.debug(f"Image uuid: {self._file.uuid}")
#        Logger.debug(f"Image type: {self._file.type}")
#        Logger.debug(f"Image source: {self._file.source}")
#        Logger.debug(f"Image orientation: {self._file.orientation}")
#        Logger.debug(f"Image rotation: {self._file.rotation}")
#        Logger.debug(f"Total rotation: {self._rotation}")
#        Logger.debug(f"Widget width: {self.width}")
#        Logger.debug(f"Widget height: {self.height}")
#        Logger.debug(f"Widget aspect ratio: {widget_ratio}")
#        Logger.debug(f"max_dim: {max_dim}")
#        Logger.debug(f"Image width: {self._image.width}")
#        Logger.debug(f"Image height: {self._image.height}")
#        Logger.debug(f"Image aspect ratio: {image_ratio}")
#        Logger.debug(f"Image x: {self._image.x}")
#        Logger.debug(f"Image y: {self._image.y}")
#        Logger.debug(f"Image center: {self._image.center}")
