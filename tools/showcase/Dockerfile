# Documentation-only capture seat. It never changes the production build graph.
FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake ninja-build g++ qt6-base-dev qt6-declarative-dev libxcb-xinput-dev \
    libkf6service-dev libkf6config-dev kde-cli-tools dbus \
    qml6-module-org-kde-kirigami qml6-module-qtquick-controls \
    qml6-module-qtquick-dialogs qml6-module-qtquick-layouts \
    qml6-module-qtquick-window qml6-module-qtqml-workerscript qml6-module-qttest \
    qt6-svg-plugins qt6-qpa-plugins qt6-wayland xvfb xauth xdotool x11-utils xterm \
    plasma-desktop plasma-workspace plasma-integration breeze kwin-x11 \
    plasma-discover dolphin konsole systemsettings powerdevil plasma-nm print-manager \
    plasma-systemmonitor kinfocenter ksystemlog partitionmanager krdc fonts-noto-core \
    python3 python3-pyside6.qtdbus python3-pyside6.qtgui python3-pil unzip util-linux && \
    rm -rf /var/lib/apt/lists/* && useradd --uid 1000 --create-home builder
USER 1000:1000
ENV LANG=C.UTF-8
WORKDIR /src
# Mount the reviewed source read-only and a separate owned output directory.
CMD ["sleep", "infinity"]
