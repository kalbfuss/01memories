"""Pyframe main module.

Author: Bernd Kalbfuss
License: GNU General Public License v3 (GPLv3)
"""

import argparse
import os


# Use gl4es wrapper if available
if 'LD_LIBRARY_PATH' in os.environ:
    os.environ['LD_LIBRARY_PATH'] = f"{ os.environ['LD_LIBRARY_PATH'] }:/usr/lib/gl4es/"
else:
    os.environ['LD_LIBRARY_PATH'] = "/usr/lib/gl4es/"
# Use gstreamer for playing video
os.environ['KIVY_VIDEO'] = "gstplayer"


# Parse arguments
parser = argparse.ArgumentParser(description='01 memories digital photo frame application.')
parser.add_argument('command', type=str, choices = ['show', 'index'])
parser.add_argument('items', type=str, nargs='*')
parser.add_argument('--rebuild', action='store_const', const=True, default=False)
args = parser.parse_args()


# Start slideshow application.
if args.command == 'show':
    from .show import run_app
    run_app()
# Start repository indexer.
elif args.command == 'index':
    from .index import run_indexer
    run_indexer(args.items, args.rebuild)
else:
    parser.print_help()
