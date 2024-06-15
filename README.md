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

I currently own and test the following two dashcams:

### VanTop H612T

Other cameras from VanTop (or perhaps cameras from other brands that use similar
electronics) may also be compatible, but I am unable to test those. This
particular camera obfuscates its GPS data, so deobfuscation is performed before
generating the final output.

### Mercylion Front 4K (Novatek)

This camera is based on a standard Novatek image processor. Other cameras also
using Novatek processors may be compatible, but again, I am unable to test this.
From my research, some cameras based on Novatek processors obfuscate their GPS
data, but my model does not, so the script currently performs no deobfuscation.

## Usage

First, build the docker image:

`docker build -t dashcam .`

Assuming the image built correctly, use the application as follows:

`docker run -v "<video directory>:/work" -it dashcam -c <Camera Type> <OpenStreetMap URL>`

Replace `<video directory>` with the path to a directory containing the raw
video files. Replace `<OpenStreetMap URL>` with the URL to an OpenStreetMap tile
server. The default is <http://localhost/hot> but this is unlikely to work
unless you happen to already be running a tile server. Replace `<Camera Type>`
with either `novatek` or `vantop` as appropriate.

## Contribution

While this software is primarily intended for my own personal use, I am not
opposed to third-party contributions to either fix bugs, add support for
additional camera models, or to add additional features.

I'm particularly unhappy with the way I've currently added support for the
Novatek camera, so the entire GPS module is a strong candidate for refactoring.
As the software works as-is for my use case, I am personally unlikely to do much
development work.

## Author

* Jason Lynch (Aexoden) <jason@aexoden.com>
