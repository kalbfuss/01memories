"""Collection of classes to generate slideshows.

Provides :class:`slideshow.Slideshow` to generate slideshows of supported
content. Rendering of the following content is currently supported:

* Images via :class:`slideshow.SlideshowImage`
* Videso via :class:`slideshow.SlideshowVideo`

Author: Bernd Kalbfuß
License: t.b.d.
"""

from .common import APPLICATION_NAME, APPLICATION_DESCRIPTION, VERSION, PROJECT_NAME
from .mylogging import Handler
from .indexer import Indexer
from .controller import Controller, DISPLAY_MODE, DISPLAY_STATE, PLAY_STATE
from .scheduler import Scheduler
from .slideshow import Slideshow
from .mqtt import MqttInterface
from .app import App
