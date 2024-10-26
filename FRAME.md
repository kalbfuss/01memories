# Digital photo frame

## Building

Building your own digital photo frame is a nice project and actually not too difficult. This document provides some advice and considerations on how to achieve it. 

In essence, you only need the following components to build your own frame:

* Conventional picture frame
* Flat (portable) screen
* Linux-compatible single-board computer (SBC)
* Power supply for the screen and SBC
* Cables to connect everything

While in principle any flat screen with the necessary ports can be used, you probably want a very flat, portable monitor to keep the entire frame as flat as possible. The disadvantage is that portable screens are (still) limited in size. An advantage is that they can usually be powered via a USB-C connection. In my case I decided for the 17.3" FHD monitor [A1 MAX](https://www.arzopa.com/products/portable-monitor-17-3-100-srgb-1080p-fhd-hdr-ips-laptop-computer-display) from Arzopa.

I bought my picture frame from the local hardware store (500x4000 mm2) and had them cut a passepartout (photo mount) fitting the portable monitor.

<img src="doc/images/frame/frame%20-%20front.jpg" alt="home assistant - device" style="zoom:50%;" />

Mounting the screen into the frame requires a bit of craftman's skills, the necessary tools (drill, saw, file, sanding paper, screw driver) and materials (wooden board, screws). Double-sided tape helps to ensure proper fit of the passepartout onto the monitor. 

I used 3D printed blocks and small screws to fix the board to the frame, but wooden blocks would have done as well. The rest is cabling. Which exact cables are required evidently depends on the components you decided to use. 

In the end, the result does not have to be pretty from the rear as long as the screen is nicely centered and fitting the passepartout. Do not forget to clean the glass before re-assembling the screen!

<img src="doc/images/frame/frame%20-%20rear.jpg" alt="home assistant - device" style="zoom:50%;" />

Regarding the SBC, there are many options available these days - most of them ARM-based and thus in principle Linux compatible. Most important for our purpose is that the SBC is sufficiently flat to fit under the photo frame. This usually excludes boards with RJ45 or stacked USB A ports. The board should further be fanless and not produce too much heat. Potentially, you will have to limit the CPU frequency to achieve the latter.

For the local storage of files, the device should provide >16 GB of non-volatile memory in the form of an SD card or better eMMC flash memory. A USB memory stick will work as well if your SBC provides the necessary USB port.  If you plan to access remote repositories, the SBC evidently needs to be equipped with a Wifi chip for integration into your home network (recommended).

Finally, the SBC needs to be strong enough to process photos and videos on-the-fly. This requires sufficient computing power, hardware accelerated graphics (OpenGL ES support) and sufficient RAM (≥512 MB, but preferably ≥1 GB) since the texture of an unpacked photo with 4000x3000 pixels requires about 50MB of memory. For the fluent playback of videos the SBC should further provide hardware accelerated decoding and resizing capabilities, including the necessary **linux drivers**. Specifically the latter can be a challenge for ARM-based SBCs.

In my photo frame project, I finally decided to go with a [Radxa Zero](https://wiki.radxa.com/Zero) after initial failures with a Rasperry Pi Zero (insufficient memory and computing power) and a Banana Pi Zero (missing/incomplete hardware acceleration/driver support).  Further details are provided in the section below. The Raspberry Pi Zero 2 and Raspberry Pi 4 might have been viable options, too, but were not available at the time of construction.

<img src="doc/images/frame/radxa%20zero.jpg" alt="home assistant - device" style="zoom:25%;" />

Every screen and computer require power. Overall, the problem is not too difficult to solve as long as you have a power outlet behind the frame. Otherwise, you will have to live with a cable on the wall.

If you have a power outlet behind the frame, the challenge is to remain as flat as possible. An elegant solution to the problem is the [sCharge 12W](https://www.smart-things.com/de/produkte/scharge-12w-usb-c-unterputz-stromversorgung/) power supply from Smart Things, which integrates into the wall. The power of 12W has proven sufficient to supply the A1 Max monitor and Radxa Zero SBC.

<img src="doc/images/frame/power%20supply.jpg" alt="home assistant - device" style="zoom: 25%;" />

## Radxa Zero ##

While in principle, *01memories* runs on any computer with *Python 3* and the necessary libraries and packages installed, we typically want to run it on a single-board computer (SBC) that is strong enough to process photo files and play videos on-the-fly.

An ARM-based SBC, which is fit for the task, is the [Radxa Zero](https://wiki.radxa.com/Zero). It comes with a quad-core ARM Cortex-A53 CPU, 4 GB of RAM, and up to 128 GB eMMC. It further supports OpenGL ES 3.2 and is equipped with an onboard Wifi chip. Still, it is not bigger than a Raspberry Pi Zero and thus well suited for integration into a digital photo frame.

In theory, the Radxa Zero also provides a video processing unit for hardware accelerated decoding. Unfortunately, driver support was broken at the time of writing. Luckily, the CPU is strong enough to achieve software decoding and scaling with reasonable frame rates for full HD videos.

The following sections provide a rough overview of required steps to prepare the Radxa Zero for installation of *01memories*.

### Linux installation and basic configuration ###

Firstly, we install the latest version of Ubuntu-based Armbian, which can be downloaded from the [Armbian](https://www.armbian.com) homepage. Select the flavor which comes with the XFCE desktop environment pre-installed.

Write the image to a suitable SD card and boot the system. You will be asked to create a first user, who has *sudo* privilige. Afterwards, we start the Armbian configuration tool:

```
$ sudo armbian-config
```

In the tool, we adjust the following settings as required:

* Language and locale
* Keyboard layout
* Hostname
* WLAN configuration

We further enable SSH login for remote maintenance work. Finally, we install Armbian to eMMC using the respective function in the System sub-menu of the configuration tool.  Afterwards we switch the computer off, remove the SD card and power the computer on again. 

After successful boot, we login with the previously created user and upgrade all pre-installed packages on the device:

```
$ sudo apt-get update
$ sudo apt-get upgrade
```

Keep old configuration files if asked (default setting). Afterwards you will likely have to reboot the device, again. 

### Security

After the reboot we install the uncomplicated firewall (optional, but recommended) and allow for SSH access:

```
$ sudo apt install ufw
$ sudo ufw allow OpenSSH
$ sudo ufw enable
```

To prevent brute force attacks via SSH, I further recommended to install *fail2ban*:

```
$ sudo apt install fail2ban
```

### Disable hardware decoding

At the time of writing, hardware decoding for Amlogic Meson SoCs was unfortunately broken. To avoid segmentation faults upon playing of videos, it is necessary to blacklist the kernel module *medon_vdec*. Afterwards, videos are played using software decoding. That is not perfect, but still better than crashing *01memories* repeatedly.

In order to blacklist the *meson_vdec* kernel module, edit the following file and append the line underneath.

**/etc/modprobe.d/blacklist-radxa-zero.conf**

```
...
blacklist meson_vdec
```

Next time the system is booted, the *meson_vdec* kernerl module should no longer be loaded. You can verify by issuing the following command:

```
$ lsmod | grep meson_vdec
```

### Installing Python ###

Now that the system has been prepared, we install *Python 3* and some of the required packages via the system package manager:

```
$ sudo apt install python3 python3-pip python3-kivy python3-sqlalchemy python3-yaml python3-exifread ffmpeg gstreamer1.0-libav
```

Remaining dependencies will be automatically installed by *pip* later.

### Creating a dedicated user

It is good practice to create a dedicated user for running the *01memories* application with minimal privileges. Issue the following commands to create the user *frame*:

```
$ sudo adduser frame
```

To enable access to video decoding/encoding hardware we add user frame to the *video* group:

```
$ sudo usermod -aG video frame
```

### Configuring the  X Window System

Next, we configure the X Window System. Most importantly, we want the system to autologin with user *frame*. Assuming that we use the Light Display Manager (LightDM), this can be achieved by adjusting the content of the following file as shown underneath: 

**/etc/lightdm/lightdm.conf.d/22-armbian-autologin.conf**

```
[Seat:*]
autologin-user=frame
autologin-user-timeout=0
user-session=xfce
```

Screen resolution is normally detected automatically. If auto-detection fails, e.g. is lower than the maximum resolution of the screen, you can set the resolution manually by adjusting the configuration in the following file:

**/etc/X11/xorg.conf**

```
Section "Device"
    Identifier  "DRM Graphics Acclerated"
    ## Use modesetting and glamor
    Driver      "modesetting"
    Option      "AccelMethod"    "glamor"     ### "glamor" to enable 3D acceleration, "none" to disable.
    Option      "DRI"            "2"
    Option      "Dri2Vsync"      "true"
    Option      "TripleBuffer"   "True"
	## End glamor configuration
EndSection

Section "Screen"
    Identifier "Default Screen"
    SubSection "Display"
        Depth 24
        Modes     "3840x2160" "1920x1080"
    EndSubSection
EndSection
```

The file may not exist. In this case you have to create it.

Afterwards we reboot the system. The Window System should login automatically as user frame. As the last step we disable the screen saver in the respective configuration menu.

### Installing 01memories ###

For installation of *01memories, we open a terminal and issue the following command:

```
$ pip3 install --break-system-packages 01memories
```

This will install *01memories* including all required dependencies.  Afterwards the application can be started with the following command:

```
$ ~/.local/bin/01memories show
```

The configuration goes into the file *~/.config/01memories/config.yaml*. Have a look at the *01memories* documentation ([README](README.md)) for configuration examples and a complete reference of configuration settings.

Finally, we add *01memories* to the session using the respective configuration dialog and make sure it is started automatically after login.

### Known limitations

- ***Missing/incomplete video processing unit (VPU) support*** – The VPU of the Amlogic S905Y2 CPU is in principle supported by a Video4Linux driver. Unfortunately, ffmpeg produces a segmentation fault when forcing it to use the decoder. See the following [ticket](https://trac.ffmpeg.org/ticket/10290) for details.

- ***Missing Display Data Channel/Command Interface (DCC/CI) support*** – The brightness (amongst other things) of external screens can usually be adjusted via the DCC/CI interface (an I<sup>2</sup>C-based interface). Unfortunately, the Designware HDMI driver used by the Radxa Zero does not seem to implement the necessary services. See the following [ticket](https://github.com/rockowitz/ddcutil/issues/307) for details. The brightness of the screen can thus not be adjusted via Software.