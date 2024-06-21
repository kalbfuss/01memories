# Digital Memories (01memories) #

Digital Memories is a Python-based digital photo frame application. It is capable of displaying photos and playing videos from local storage as well as WebDAV and [rclone](https://rclone.org) repositories.

Digital Memories has been designed to run slideshows from image and video repositories with several thousand files. No conversion is required. Files remain in your repositories and fully under your control.

Files in slideshows can be dynamically arranged and filtered based on their metadata (EXIF and IPTC metadata supported). Slideshows can be run continuously or scheduled.

Digital Memories supports reverse geocoding based on GPS data in the EXIF tag, using the geopy library and Photon geocoder (essentially OpenStreetMap).

Digital Memories optionally integrates with [Home Assistant](https://www.home-assistant.io/) via [MQTT](https://mqtt.org). Integration allows the display to be motion activated after coupling of the Digital Memories device with a motion sensor.

Digital Memories is being developed by [Bernd Kalbfuss (aka langweiler)](https://github.com/kalbfuss) and is published under the [General Public License version 3](LICENSE.md). The latest source code is available on [GitHub](https://github.com/kalbfuss/01memories).

Instructions for building your own digital photo frame can be found [here](FRAME.md).

## Dependencies ##

Digital Memories requires [Python 3](https://python.org) to run. It has been developed with Python version 3.10 on Ubuntu Linux, but may run with earlier versions and on different operating systems.

Digital Memories requires the following Python packages to be installed:

- exifread
- ffmpeg-python
- geopy
- IPTCInfo3
- Kivy
- paho-mqtt
- pillow
- pyyaml
- rclone-python
- schedule
- SQLAlchemy
- webdavclient3

All packages are available on [pypi.org](https://pypi.org) and can be installed using the "pip install" (or "pip3 install") command. Where possible/available, packages should be installed using the distribution package manager (e.g  "apt" on Debian/Ubuntu).

Digital Memories further requires the following (non-Python) libraries to be installed:

- libxslt1.1
- libmtdev1
- libsqlite3-0
- libsdl2-2.0-0
- ffmpeg

Libraries should be installed using the distribution package manager.

Note that Digital Memories requires the X windows system and a desktop environment to be installed. Digital Memories will in principle also run under Wayland, but the display will not be turned off automatically since Wayland does fully implement the "xset" command.

## Installation

Digital Memories is still in early development. The easiest way to install the latest version is to clone the GitHub repository using the *git* client. After having installed the *git* client, installation of Digital Memories becomes as simple as:

```bash
$ git clone git@github.com:kalbfuss/01memories.git
```

The command installs the Digital Memories sources in the sub-directory "pyframe" within the current working directory. Digital Memories can be updated to the latest version by changing into the "pyframe" directory and issuing the following command:

```bash
$ cd pyframe
$ git pull origin master
```

At this stage of the project you should not expect the configuration syntax to be stable. Please, have a look at the documentation after each update and adjust the configuration as necessary.

## Configuration

The Digital Memories application is configured via a single YAML configuration file. The file is named "config.yaml" and must be stored in the current (working) directory. The following sections provide examples for configuration and the documentation of all parameters.

A lot of effort has gone into configuration checks. The application should warn you in the event of invalid configurations immediately after startup. It is thus safe to explore the various configuration options. Under no circumstances is Digital Memories going to modify any of your image or video files.

### Examples

#### Simple configuration

In this example, we want to continuously show all files stored in a local directory. For this purpose, we configure a single local repository ("Local storage"). Our files are stored under the relative path "./local/photos". We further define a single slideshow ("Favorites") containing all files from the repository.  Files are shown in a random sequence for a duration of 60 s.

Per (application) default settings, the repository is indexed once after start of the application. The slideshow includes photos and videos. The slideshow starts playing after start of the application and the display is always on.

```yaml
repositories:
  # Local repository with our favorite photos and videos.
  Local storage:
    type: local
    root: ./local/photos

slideshows:
  # Slideshow with our favorite photos and videos.
  Favorites:
    repositories: Local storage
    pause: 60
    sequence: random
```

#### Advanced configuration

In this example, we want to show our most recent photos stored in the cloud in the period from 8:00 to 10:00 and our favorite photos, which are stored locally, in the period from 18:00 to 20:00. Since we are not necessarily at home in the evening, we want the display to be motion activated during this time.

Firstly, we define two (enabled) repositories: A local repository ("Local storage") with files stored under the relative path "./local/photos" and a WebDAV repository ("Cloud storage") with files stored in the cloud. The third repository ("Test repository") used for testing has been disabled. Per the repository default settings, the index of the local repository is updated at the start of the application and every 24 hours. The index of the cloud repository is updated daily at 23:00.

Secondly, we define two slideshows: The first slideshow ("Favorites") includes files tagged as "favorites" from the local repository. Files are shown for a duration of 60 s. The second slideshow ("Recent") includes the 200 most recent files from the cloud repository, which are not tagged as "vacation" or "favorites". We further limit files to "images". Files are sorted by the creation date in ascending order. Per the slideshow defaults, images are shown for a duration of 180 s.

The slideshow defaults further ensure that files tagged as "private" are always excluded. Files are labeled with their description from the file metadata (if available) and labels are shown for a duration of 60 s at the start and the end of each file. Since the display is installed in vertical orientation, we rotate the content by -90° and limit content to files in portrait orientation.

Thirdly, we define a schedule to show the second slideshow ("Recent") in the time from 8:00 to 10:00 and the first slideshow ("Favorites") in the time from 18:00 to 20:00. In the first case, the display is always on. In the second case, the display is motion activated with a timeout interval of 300 s.

Finally, since we run Home Assistant and need the MQTT remote control for the motion activation feature, we configure an MQTT client connection. For the motion activation feature to function properly, we further have to link the touch button with a motion sensor in Home Assistant (see [motion activation](#Motion activation)).

```yaml
repositories:
  # Local repository with our favorite photos and videos.
  Local storage:
    type: local
    root: ./local/photos
  # WebDAV repository with the latest photos from our smartphone.
  Cloud storage:
    type: webdav
    url: https://mycloud.mydomain.org
    root: /remote.php/webdav/photos
    user: pyframe
    password: <password>
    index_update_at: "23:00"
  # Test repository, which has been disabled.
  Test repository:
    type: local
    root: ./local/test
    enabled: false

# Repository defaults
index_update_interval: 24

slideshows:
  # Slideshow with our favorite photos and videos.
  Favorites:
    repositories: Local storage
    pause: 60
    tags: favorites
  # Slideshow with most recent photos from our smartphone.
  Recent:
    repositories: Cloud storage
    excluded_tags:
      - vacation
      - favorites
    types: images
    most_recent: 200
    order: date
    direction: descending

# Slideshow defaults
always_excluded_tags: private
label_content: description
label_mode: auto
label_duration: 30
orientation: portrait
pause: 180
rotation: -90

schedule:
  # Play the slideshow "Recent" in the period from 8:00 to 10:00.
  morning start:
    time: "08:00"
    slideshow: Recent
    display_mode: static
    play_state: playing
  morning stop:
    time: "10:00"
    play_state: stopped
  # Play the slideshow "Favorites" in the period from 18:00 to 20:00.
  # Activate the display by motion.
  evening start:
    time: "18:00"
    slideshow: Favorites
    display_mode: motion
    display_timeout: 300
    play_state: playing
  evening stop:
    time: "20:00"
    play_state: stopped

mqtt:
  host: mqtt.local
  user: pyframe
  password: <my password>
  device_name: My Digital Memories somwhere in the house
```

### Application

The following parameters are used to configure the application.

#### Basic

| Parameter       | Description                                                  |
| :-------------- | :----------------------------------------------------------- |
| window_size     | The size of the window provided as *[width, height]*. A value of "full" enables full screen mode. The default is "full". |
| display_mode    | The following display modes are supported. The default is "static".<br/>- *static*: The display is always on if a slideshow is paused or playing and off if a slideshow is stopped.<br/> - *motion*: The display is turned on and the slideshow starts playing in the presence of motion (i.e. *touch* events). The slideshow is paused and the display turned off in the absence of motion after the display timeout interval. |
| display_timeout | The time in seconds after which the slideshow is paused and screen turned off in the absence of motion. The default is 300 seconds. |

#### Advanced

Parameters in this section will likely not have to be modified by the majority of users.

| Parameter                | Description                                                  |
| :----------------------- | :----------------------------------------------------------- |
| index                    | The index database file. The path may be absolute or relative to the current working directory. The default is "./index.sqlite". |
| cache                    | The directory in which files can be cached (used by WebDAV and rclone repositories). The directory path may be absolute or relative to the current working directory. The directory can be shared by multiple repositories. **Do not** use directory in which you store files as cache directory. The default is "./cache". |
| enable_exception_handler | Set to *true* in order to enable the generic exception handler. The generic exception handler prevents the application from exiting unexpectedly. Exceptions are logged, but the execution continues. The default is *false*. |
| enable_scheduler         | Set to *false* in order to disable the scheduler. The scheduler is disabled even in the presence of a *schedule* configuration section. The default is *true*. |
| enable_mqtt              | Set to *false* in order to disable the MQTT client. The client is disabled even in the presence of an *mqtt* configuration section. The default is *true* |
| enable_logging           | Set to *false* in order to disable logging. The default is *true*. |
| log_level                | The log level, which can be set to *debug*, *info*, *warning*, or *error*. The default is "warning". |
| log_dir                  | The directory to which log files are written. The directory path may be absolute or relative to the current working directory. The default is "./log". |

### Repositories

Digital Memories supports the configuration of one or multiple file repositories. Repositories are configured in the *repositories* section of the configuration file. The section is required and must contain at least a single, valid repository definition. Repository parameter defaults may be provided as global parameters.  The example below provides a typical *repositories* configuration section.

```yaml
...
repositories:
  # Local repository with our favorite photos and videos.
  Local storage:
    type: local
    root: ./local/photos
  # WebDAV repository with the latest photos from our smartphone.
  Cloud storage:
    type: webdav
    url: https://mycloud.mydomain.org
    root: /remote.php/webdav/photos
    user: pyframe
    password: <password>
  # Test repository, which has been disabled.
  Test repository:
    type: local
    root: ./local/test
    enabled: false

# Repository defaults
index_update_interval: 24
...
```

The following parameters are used to configure repositories.

#### General

| Parameter             | Description                                                  |
| :-------------------- | :----------------------------------------------------------- |
| type                  | The following repository types are supported. A values must be provided.<br/> - *local*: Repository with files on the local file system. **Note:** Even if referred to as *local*, files may be stored on a network share as long as the network is mounted and integrated into the file system hierarchy (e.g. "/mnt/photos").<br/>- *rclone*: Repository with files on an rclone remote. The remote must have been configured before using the "rclone config" command or directly in the rclone configuration file.<br /> - *webdav*: Repository with files on a WebDAV accessible site (e.g. ownCloud or NextCloud). |
| index_update_interval | Interval in hours at which the metadata index for the repository is updated. If zero, the index is only updated once after start of the application. The default ist 0. Do not use in combination with *index_update_at*. |
| index_update_at       | The time at which the metadata index for the repository is updated. The index is updated once per day. Do not use in combination with *index_update_interval*. |
| enabled               | Set to *false* in order to disable the repository. The default is *true*. |

#### Local repositories

Only a single parameter is required for the definition of local repositories.

| Parameter | Description |
| :-------- | :---------- |
| root      | The repository root directory. Root directories may be absolute or relative to the current working directory. Files in sub-folders will be included in the repository. A value must be provided.|

#### Rclone repositories

Like for local repositories, only a single parameter is required for the definition of rclone repositories. However, the rclone remote must have been configured before. Digital Memories currently does not provide any functionality to configure rclone remotes.

| Parameter | Description                                                  |
| :-------- | :----------------------------------------------------------- |
| root      | The rclone remote and root directory (e.g. "mycloud:/photos/"). Files in sub-folders will be included in the repository. A value must be provided. |

#### WebDAV repositories

As a minimum, the parameters *url*, *user* and *password* need to be specified for the definition of a WebDAV repository.

| Parameter | Description |
| :-------- | :---------- |
| url       | The URL of the WebDAV server. Use "https://" protocol prefix for secure connections. A value must be provided. |
| user      | Login name. A value must be provided.|
| password  | Login password. A value must be provided.|
| root      | The root directory relative to the URL. For ownCloud WebDAV access, the root directoy typically starts with "/remote.php/webdav". The default is */*. |

### Slideshows

Digital Memories supports the configuration of one or multiple slideshows. Slideshows are configured in the *slideshows* section of the configuration file. The section is required and must contain at least a single, valid slideshow definition. The first slideshow is the default slideshow. Slideshow parameter defaults may be provided as global parameters. The example below provides a typical *slideshows* configuration section.

```yaml
...
slideshows:
  # Slideshow with our favorite photos and videos.
  Favorites:
    repositories: Local storage
    pause: 60
    tags: favorites
  # Slideshow with most recent photos from our smartphone.
  Recent:
    repositories: Cloud storage
    excluded_tags:
      - vacation
      - favorites
    types: images
    most_recent: 200
    order: date
    direction: descending

# Slideshow defaults
always_excluded_tags: private
label_content: description
label_mode: auto
label_duration: 30
orientation: portrait
pause: 180
rotation: -90
...
```

The following parameters are used to configure slideshows.

#### General parameters

| Parameter       | Description |
| :-------------- | :---------- |
| bg_color        | The background color used to fill empty areas, provided as *[r, g, b]*. The default is *[1, 1, 1]* (white).|
| label_content   | The following content based on file meta data is supported. The default is "full".<br/> - *description:* only image description<br/> - *short:* image description, location, and creation date<br/> - *full:* image description, location, creation date and tags, file name and repository |
| label_duration  | Duration in seconds for which labels are shown. The default is 60. |
| label_font_size |The relative font size of labels, expressed as percentage of the shortest file dimension. The default is 0.08.|
| label_mode|The following label modes are supported. The default is "off".<br/> - *auto:* Labels are shown at the beginning and end of a file for the *label_duration*.<br/> - *off:* Labels are never shown. <br/> - *on:* Labels are always shown.|
| label_padding   | The relative padding of labels, expressed as percentage of the shortest file dimension. The default is 0.03.|
| pause           | The delay in seconds until the next file is shown. The default is 300. |
| resize          | The following resize modes are supported. The default is "fill".<br/> - *fit:* The slideshow content is zoomed to fit the screen as good as possible. Empty areas are filled with the background color.<br/> - *fill:* The slideshow content is zoomed and cropped to completely fill the screen. Note that images which do not have the same orientation as the screen are not zoomed and cropped, but only fit to the screen. |
| rotation        | The angle by which slideshow content is rotated clockwise. Useful for picture frames/screens, which are installed in non-standard orientation. The default is 0.|

#### Filter criteria

The following parameters control the files included in a slideshow and the sequence in which they are shown. The default is to include all files from all repositories. Files are sorted by their name in ascending order.

| Parameter            | Description                                                  |
| :------------------- | :----------------------------------------------------------- |
| repositories         | The repositories from which files shall be shown. The default is to show files from all repositories. |
| orientation          | Valid orientations are *portrait* or *landscape*. The default is to include either orientation. |
| types                | Supported file types are *images* and *videos*. May be a single value or list of values. The default is to include all file types. |
| tags                 | File tags, which shall be included. May be a single value or list of values. The default is to include all tags **and** untagged files. If set, untagged files are excluded. |
| excluded_tags        | File tags, which shall be excluded. May be a single value or list of values. The default is not to exclude any tags. |
| always_excluded_tags | Same as *excluded_tags*, but not overwritten by an *excluded_tags* statement. Use in the slideshow default configuration to exclude certain tags in all slideshows (e.g. private content). |
| most_recent          | Files in the slideshow are limited to the *most_recent* number of files based on the creation date **after** application of all other filter criteria. |
| order                | The sort order in which files are shown. The default is "name".<br/> - *date:* Files are sorted by their creation date.<br/> - *name:* Files are sorted by their name.<br/> - *random:* Files are shown in a random sequence.<br/> - *smart*: A short sequence with random starting point, sorted by date in ascending order. |
| direction            | Valid sort directions are *ascending* or *descending*. The default is "ascending". Ignored if random order is configured. |
| smart_limit          | The (maximum) number of files in a smart sequence. If the *smart_time* criterion is not met, the sequence may be shorter. The default is 10. |
| smart_time           | The maximum time allowed in-between subsequent files of a smart sequence in hours. If exceeded, the sequence is terminated early and a new sequence initiated. The default is 24. |

### Schedule

Digital Memories supports the configuration of a schedule. The schedule allows to alter the application behavior at predefined points in time. The schedule is configured in the optional *schedule* section of the configuration file. The schedule may contain one or multiple events. The schedule is disabled if the configuration section is missing. The example below provides a typical *schedule* configuration section.

```yaml
schedule:
  # Play the slideshow "Recent" in the period from 8:00 to 10:00.
  morning start:
    time: "08:00"
    slideshow: Recent
    display_mode: static
    play_state: playing
  morning stop:
    time: "10:00"
    play_state: stopped
  # Play the slideshow "Favorites" in the period from 18:00 to 20:00.
  # Activate the display by motion.
  evening start:
    time: "18:00"
    slideshow: Favorites
    display_mode: motion
    display_timeout: 30
    play_state: playing
  evening stop:
    time: "20:00"
    play_state: stopped
```

The following parameters are used to configure events in the schedule.

| Parameter       | Description                                                  |
| :-------------- | :----------------------------------------------------------- |
| time            | The time of the event. A value must be provided. Always specify in quotation marks. ***Note:*** Hours and minutes <10 must be preceded by a 0, i.e. "08:03" and never "8:3". |
| slideshow       | Selected slideshow. If no slideshow is specified, the previous or default slideshow is assumed. |
| play_state      | Valid play states are *paused*, *playing* and *stopped*. The play state remains unchanged if no value is provided. The default is "stopped". |
| display_mode    | The following display modes are supported. The display mode remains unchanged if no value is provided. The default is "static".<br/> - *static*: The display is always on if a slideshow is paused or playing and off if a slideshow is stopped.<br/> - *motion*: The display is turned on and the slideshow starts playing in the presence of motion. The slideshow is paused and the display turned off in the absence of motion after the display timeout interval. |
| display_timeout | The time in seconds after which the slideshow is paused and screen turned off in the absence of motion. The display timeout remains unchanged if no value is provided. The default is 300. |

### MQTT

Digital Memories implements an MQTT client, which registers the device with an MQTT broker. The MQTT configuration is provided in the optional *mqtt* section of the configuration file. MQTT support is disabled if the configuration section is missing. The example below provides a typical *mqtt* configuration section.

```yaml
...
mqtt:
  host: <hostname of MQTT broker>
  user: <login name>
  password: <my password>
  device_name: My Digital Memories somwhere in the house
...
```

The following parameters are used to configure the MQTT client.

| Parameter    | Description |
| :----------- | :---------- |
| host         | Hostname of the MQTT broker. A value must be specified.|
| port         | Connection port of MQTT broker. The default is 8883 (standard for secure connections).|
| tls          | The following values are supported. The default is *true*.<br/> - *true*: A TLS-encrypted secure connection is used.<br/> - *false*: A non-encrypted connection is used.|
| tls_insecure | The following values are supported. The default is *false*.<br/> - *true*: Insecure TLS connections with non-trusted certificates are permitted.<br/> - *false*: Only secure connections with trusted certificates are permitted.|
| user         | Login name. A value must be provided.|
| password     | Login password. A value must be provided.|
| device_id    | The Digital Memories device ID. The default is "pyframe". **Note** The device ID must be unique. A different value must be specified if multiple Pyframe instances connect to the same broker. |
| device_name  | The human friendly device name. The default is  to use the *device_id*.|

## Running

Once Digital Memories has been configured, you can change into the Digital Memories directory and start the application with the following command:

```bash
$ python3 pyframe.py
```

In recent distributions you may have to use "python" instead of "python3". Unless configured otherwise, Digital Memories is going to create an index database "index.sqlite" and directory "./log" for log files in the Digital Memories directory. If WebDAV or rclone repositories are configured, Digital Memories will further create a directory "./cache" for temporary storage of downloaded files.

For convenience you can install the following script, which will allow you to start the Digital Memories application from anywhere (even SSH sessions). The placeholders <your user> and <your Digital Memories directory> evidently need to be replaced with the proper values prior to running the script.

**/usr/local/bin/start-pyframe**

```bash
#!/bin/sh

USER=<your user>
SRC=<your pyframe directory>
# May be python or python3 depending on your distribution
PYTHON=/usr/bin/python3

# Set authority file and active display in case we are starting this script from an SSH session.
export XAUTHORITY=/home/$USER/.Xauthority
export DISPLAY=:0

# Change to pyframe source directory
cd $SRC
# Start pyframe
if [ $(/usr/bin/whoami) = 'root' ]; then
	/usr/sbin/runuser -u langweiler -- $PYTHON pyframe.py
else
	$PYTHON  pyframe.py
fi
```

If you intend to run Digital Memories as *systemd* service, you can optionally create a second script for clean up after termination. In this example, we turn off the screen (works only under X11, not Wayland).

**/usr/local/bin/stop-pyframe**

```bash
#!/bin/sh

USER=<your user>

# Set authority file and active display in case we are starting this script from an SSH session.
export XAUTHORITY=/home/$USER/.Xauthority
export DISPLAY=:0

# Turn backlight off.
/usr/bin/xset dpms force off
```

Both scripts should be owned by *root.root* and need to be executable (mode 750).

If you want to start Digital Memories automatically during system boot, you can do so by configuring it in your desktop session manager. Alternatively, you can register a *systemd* service via a unit file. Below is an example for a unit file, which uses the two scripts we created before.

**/etc/systemd/system/pyframe.service**

```ini
[Unit]
Description=Digital Memories photo frame
Wants=graphical.target
After=graphical.target

[Service]
Type=simple
ExecStart=/usr/local/bin/start-pyframe
ExecStop=/usr/local/bin/stop-pyframe
User=root
Group=root
Restart=always

[Install]
WantedBy=default.target
```

The *Wants* and *After* statements make sure that we are in graphical mode and that the service is only started after the graphical system has been launched. The *ExecStop* script is optional as stated above. It is not required to stop the Digital Memories service. The *Restart* statement ensures that Digital Memories is restarted after unexpected exit. The *WantedBy* statement allows to start the service automatically at boot time.

Make sure the unit file belongs to *root.root*, is readable by the owner and group and writable by the owner only (mode 640). Afterwards you can start the service and verify the successful start via the following commands:

```bash
$ sudo systemctl start pyframe
$ sudo systemctl status pyframe
```

To enable automatic start of the service during boot time issue the following command:

```bash
$ sudo systemctl enable pyframe
```

Make sure to additionally configure *autologin* for the user under which you intend to run Digital Memories. Steps for configuration depend on the graphical system and Linux distribution. Under *Armbian* you can use the "armbian-config" tool. On *Raspberry Pi OS*, the "raspi-config" tool will do. For other systems/distributions consult the corresponding documentation.

## Home Assistant

### General setup

Digital Memories implements basic support for integration with the [Home Assistant](https://www.home-assistant.io/) home automation system. Integration is achieved through the built-in Home Assistant [MQTT integration](https://www.home-assistant.io/integrations/mqtt/). As an additional pre-requisite, an MQTT broker must be installed (e.g. [Eclipse Mosquitto](https://mosquitto.org/)).

After the Digital Memories MQTT client has been correctly configured and a connection to the MQTT broker established, Digital Memories should automatically appear as a new device in Home Assistant. The device supports several push buttons and configuration selections, which allow you to control Digital Memories from remote. The device further provides a *file sensor*, whose value is identical to the UUID of the currently displayed file.

![home assistant - device](docs/images/readme/home%20assistant%20-%20device.png)

In addition, the *file sensor* provides selected file metadata as sensor attributes.

![home assistant - file](docs/images/readme/home%20assistant%20-%20file.png)

### Motion activation

For motion activation of the display, the *touch button* of the Digital Memories device needs to be coupled to a motion sensor via an automation. Every time motion is detected, the *touch button* is pressed by the automation. Pressing the touch button activates the display and resets the display timeout counter.

![home assistant - automation](docs/images/readme/home%20assistant%20-%20automation.png)
