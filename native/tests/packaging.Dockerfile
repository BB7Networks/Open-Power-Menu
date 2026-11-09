# Disposable Debian 13 build/test image, followed by a no-Python GUI runtime.
# The resulting ELF is a Debian 13 development artifact, not a universal package.
FROM debian:trixie-slim AS build
WORKDIR /src
COPY --chown=1000:1000 . /src
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake ninja-build g++ qt6-base-dev qt6-declarative-dev \
    libkf6service-dev libkf6config-dev kde-cli-tools dbus \
    qml6-module-org-kde-kirigami qml6-module-qtquick-controls \
    qml6-module-qtquick-dialogs qml6-module-qtquick-layouts \
    qml6-module-qtquick-window qml6-module-qtqml-workerscript \
    qt6-svg-plugins qt6-qpa-plugins qt6-wayland xvfb xauth systemd python3 python3-pyside6.qtdbus python3-pyside6.qtwidgets && rm -rf /var/lib/apt/lists/* && \
    useradd --uid 1000 --create-home builder
RUN chown builder:builder /src
USER 1000:1000
RUN umask 022 && cmake -S /src -B /tmp/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DOPM_BUILD_PACKAGE=ON -DOPM_INSTALL_TEST_HOOKS=ON && \
    cmake --build /tmp/build --parallel 2 && \
    ctest --test-dir /tmp/build --output-on-failure && \
    cmake --build /tmp/build --target native-bundle && \
    python3 native/tests/packaging.py --bundle /tmp/build/native-bundle --legacy /src/work/package-legacy -v && \
    cmake -S /src -B /tmp/build -DOPM_INSTALL_TEST_HOOKS=OFF && \
    cmake --build /tmp/build --target native-package --parallel 2

FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libqt6core6t64 libqt6dbus6 libqt6gui6 libqt6widgets6 libqt6qml6 libqt6quick6 \
    libqt6quickcontrols2-6 libkf6service6 libkf6configcore6 kde-cli-tools dbus \
    qml6-module-org-kde-kirigami qml6-module-qtquick-controls \
    qml6-module-qtquick-dialogs qml6-module-qtquick-layouts \
    qml6-module-qtquick-window qml6-module-qtqml-workerscript \
    qt6-svg-plugins qt6-qpa-plugins qt6-wayland && rm -rf /var/lib/apt/lists/* && \
    useradd --uid 1000 --create-home opm
COPY --from=build /tmp/build/native-bundle /opt/opm-bundle
COPY --chmod=0644 native/tests/package-runtime-smoke.sh /usr/local/libexec/opm-package-smoke.sh
RUN ! command -v python3 && ! command -v g++
USER 1000:1000
ENV LANG=C.UTF-8
CMD ["sh", "/usr/local/libexec/opm-package-smoke.sh"]
