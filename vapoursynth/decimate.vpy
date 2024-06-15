from vapoursynth import core, YUV

import havsfunc as haf

# Load the source videos
video = core.ffms2.Source(source=source)

if map_source != 'None':
    map = core.ffms2.Source(source=map_source)

# Scale from 4k 4:2:0 to 1080p 4:4:4
video = video.fmtc.resample(w=1920, h=1080, css="444")

# Decimate the frames by 4
video = video[::4]

# Convert to the desired target FPS
video = core.std.AssumeFPS(video, fpsnum=60, fpsden=1)

# Add the map overlay
if map_source != 'None':
    map = map.fmtc.matrix(mat="601", col_fam=YUV, bits=16)
    map = map.fmtc.resample(css="444")
    video = haf.Overlay(video, map, 1528, 848)

# Output the video
video = video.fmtc.bitdepth(bits=10)
video.set_output()
