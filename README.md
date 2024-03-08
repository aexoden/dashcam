# dashcam

## Overview

This project facilitates taking dashcam video from compatible dashcams and
producing timelapse summary videos from the source content, with a GPS map
overlay.

## Requirements

This project leverages [VapourSynth](https://www.vapoursynth.com) for much of
the video processing, and as such, has a somewhat complicated setup process. The
only supported usage method is Docker-based, which ensures that all necessary
dependencies are available.

Please see the `Dockerfile` for a list of current dependencies.

In addition, access to an OpenStreetMap tile server is required to generate the
GPS overlay map. Information about potential providers or instructions to run
your own tile server can be found at <https://switch2osm.org/>.

## Tested Compatible Dashcams

* VanTop H612T

## Usage

First, build the docker image:

`docker build -t dashcam .`

Assuming the image built correctly, use the application as follows:

`docker run -v "<video directory>:/work" -it dashcam <OpenStreetMap URL>`

Replace `<video directory>` with the path to a directory containing the raw
video files. Replace `<OpenStreetMap URL>` with the URL to an OpenStreetMap tile
server. The default is <http://localhost/hot> but this is unlikely to work
unless you happen to already be running a tile server.

## Author

* Jason Lynch (Aexoden) <jason@aexoden.com>
