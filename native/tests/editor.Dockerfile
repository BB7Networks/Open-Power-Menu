# Disposable Debian 13 build/test image, followed by a no-Python GUI runtime.
# The resulting ELF is a Debian 13 development artifact, not a universal package.
ARG OPM_DEB_IMAGE=debian:trixie-slim
FROM ${OPM_DEB_IMAGE} AS build
ARG OPM_SOURCE_COMMIT
ENV OPM_SOURCE_COMMIT=${OPM_SOURCE_COMMIT}
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake ninja-build g++ qt6-base-dev qt6-declarative-dev libxcb-xinput-dev \
    libkf6service-dev libkf6config-dev kde-cli-tools dbus \
    qml6-module-org-kde-kirigami qml6-module-qtquick-controls \
    qml6-module-qtquick-dialogs qml6-module-qtquick-layouts \
    qml6-module-qtquick-window qml6-module-qtqml-workerscript qml6-module-qttest \
    qt6-svg-plugins qt6-qpa-plugins qt6-wayland xvfb xauth xdotool x11-utils xterm \
    plasma-desktop plasma-workspace plasma-integration breeze kwin-x11 kwin-wayland \
    plasma-discover dolphin konsole systemsettings powerdevil plasma-nm print-manager \
    plasma-systemmonitor kinfocenter ksystemlog partitionmanager virt-manager krdc \
    python3 python3-pyside6.qtdbus python3-pyside6.qtgui && rm -rf /var/lib/apt/lists/* && \
    (getent passwd 1000 >/dev/null || useradd --uid 1000 --create-home builder)
WORKDIR /src
COPY --chown=1000:1000 CMakeLists.txt /src/
COPY --chown=1000:1000 native /src/native
COPY --chown=1000:1000 openpowermenu/data /src/openpowermenu/data
COPY --chown=1000:1000 assets /src/assets
COPY --chown=1000:1000 plasmoid /src/plasmoid
COPY --chown=1000:1000 tools/trace-x11-popup.py /src/tools/trace-x11-popup.py
RUN chown 1000:1000 /src
USER 1000:1000
ENV OPM_TEST_INPUT_MODULE=/tmp/build/native/nativeinput
RUN cmake -S /src -B /tmp/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DOPM_BUILD_EDITOR=ON -DOPM_BUILD_STANDALONE=ON && \
    cmake --build /tmp/build --parallel 2 && \
    cmake --install /tmp/build --prefix /tmp/stage
# CI runs editor-qualification.sh in this image, retains its raw /tmp evidence
# even on failure, and gates the independent runtime check on its exit status.
CMD ["sh", "/src/native/tests/editor-qualification.sh"]

FROM ${OPM_DEB_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends \
    libqt6core6t64 libqt6dbus6 libqt6gui6 libqt6qml6 libqt6quick6 \
    libqt6quickcontrols2-6 libkf6service6 libkf6configcore6 libxcb-xinput0 kde-cli-tools dbus \
    qml6-module-org-kde-kirigami qml6-module-qtquick-controls \
    qml6-module-qtquick-dialogs qml6-module-qtquick-layouts \
    qml6-module-qtquick-window qml6-module-qtqml-workerscript \
    qt6-svg-plugins qt6-qpa-plugins && rm -rf /var/lib/apt/lists/* && \
    (getent passwd 1000 >/dev/null || useradd --uid 1000 --create-home opm)
COPY --from=build /tmp/stage/bin/ /usr/local/bin/
COPY --chmod=0644 native/tests/editor-runtime-smoke.sh /usr/local/libexec/opm-editor-smoke.sh
RUN ! command -v python3 && ! command -v g++
USER 1000:1000
ENV LANG=C.UTF-8
CMD ["sh", "/usr/local/libexec/opm-editor-smoke.sh"]
