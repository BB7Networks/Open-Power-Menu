# Developer smoke image: a runtime without Python, PySide6, a compiler or QML.
# Build the executable on Debian 13 before copying it into this image.
FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libqt6core6t64 libqt6dbus6 dbus && rm -rf /var/lib/apt/lists/*
COPY open-power-menu-native /usr/local/bin/open-power-menu-native
RUN ! command -v python3 && ! command -v g++ && \
    useradd --uid 1000 --no-create-home --home-dir /tmp --shell /usr/sbin/nologin opm
USER 1000:1000
ENV XDG_CONFIG_HOME=/tmp/opm-native-config LANG=C.UTF-8
CMD ["open-power-menu-native", "--check"]
