dashcam
=======

Overview
--------

This project facilitates taking dashcam video from compatible dashcams and producing timelapse summary videos from the
source content, with a GPS map overlay. This is primarily intended for my own personal use, and as such, may not be
compatible with any given environment other than my own.

Requirements
------------

The following external software packages are used:

* ExifTool
* FFmpeg
* VapourSynth

In addition, the following VapourSynth plugins are required:

* ffmpegsource
* fmtconv
* havsfunc

There are several Python dependencies, so it is recommended to create a virtualenv using poetry and to run any commands
from within that virtualenv.

In addition, access to an OpenStreetMap tile server is required to generate the GPS overlay map. Information about
potential providers or instructions to run your own tile server can be found at `<https://switch2osm.org/>`_.

Compatible Dashcams
-------------------

* VanTop V9H

Usage
-----

python -m dashcam <OpenStreetMap URL> <video directory>

Author
------

* Jason Lynch (Aexoden) <jason@calindora.com>
