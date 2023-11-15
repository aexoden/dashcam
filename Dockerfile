# Use Arch Linux as the base
FROM ghcr.io/greyltc-org/archlinux-aur
RUN pacman -Syu --noconfirm

# Install dependencies
RUN aur-install \
    ffmpeg \
    ffms2 \
    perl-image-exiftool \
    python \
    python-mercantile \
    python-pillow \
    python-requests \
    schedtool \
    ttf-liberation \
    vapoursynth \
    vapoursynth-plugin-adjust \
    vapoursynth-plugin-fmtconv \
    vapoursynth-plugin-havsfunc \
    vapoursynth-plugin-mvtools

# Create user
RUN useradd -ms /bin/bash app_user
USER app_user

# Copy files
COPY . /home/app_user/dashcam

# Set up execution
VOLUME ["/work"]
WORKDIR /home/app_user/dashcam

# Work around exiftool being installed to a weird location
ENV PATH="/usr/bin/vendor_perl:$PATH"

ENTRYPOINT ["schedtool", "-B", "-n", "19", "-e", "/usr/bin/python", "-m", "dashcam", "/work"]
CMD ["http://localhost/hot"]
