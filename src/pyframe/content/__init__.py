"""Collection of classes to display content in slideshows.

Rendering of the following content is currently supported:

* Images via :class:`pyframe.content.SlideshowImage`
* Videos via :class:`pyframe.content.SlideshowVideo`
* Error messages via :class:`pyframe.content.ErrorMessage

Author: Bernd Kalbfuß
License: GNU General Public License v3 (GPLv3)
"""

from . base import ContentBase, ErrorMessage, LabeledContent
from . image import SlideshowImage
from . video import SlideshowVideo
