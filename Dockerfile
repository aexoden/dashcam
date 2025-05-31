# Use Debian Linux as the base
FROM debian:trixie-slim

# Set up repositories
RUN apt-get update
RUN apt-get install -y wget
RUN wget https://www.deb-multimedia.org/pool/main/d/deb-multimedia-keyring/deb-multimedia-keyring_2024.9.1_all.deb
RUN apt-get install -y ./deb-multimedia-keyring_2024.9.1_all.deb

# Copy files
COPY dmo.sources /etc/apt/sources.list.d
COPY . /home/app_user/dashcam

# Install dependencies
RUN apt-get update
RUN apt-get full-upgrade -y

RUN apt-get install -y \
    ffmpeg \
    fonts-liberation \
    libimage-exiftool-perl \
    python3 \
    python3-mercantile \
    python3-pillow \
    python3-pip \
    python3-requests \
    python3-vapoursynth-adjust \
    python3-vapoursynth-havsfunc \
    python3-vapoursynth-mvsfunc \
    schedtool \
    vapoursynth \
    vapoursynth-ffms2 \
    vapoursynth-fmtconv \
    vapoursynth-mvtools

# Create user
RUN useradd -ms /bin/bash app_user
USER app_user

# Set up execution
VOLUME ["/work"]
WORKDIR /home/app_user/dashcam

# Work around exiftool being installed to a weird location
ENV PATH="/usr/bin/vendor_perl:$PATH"

ENTRYPOINT ["schedtool", "-B", "-n", "19", "-e", "/usr/bin/python3", "-m", "dashcam", "/work"]
CMD ["http://localhost/hot"]
