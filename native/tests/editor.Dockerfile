# Disposable Debian 13 build/test image, followed by a no-Python GUI runtime.
# The resulting ELF is a Debian 13 development artifact, not a universal package.
FROM debian:trixie-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake ninja-build g++ qt6-base-dev qt6-declarative-dev \
    libkf6service-dev libkf6config-dev kde-cli-tools dbus \
    qml6-module-org-kde-kirigami qml6-module-qtquick-controls \
    qml6-module-qtquick-dialogs qml6-module-qtquick-layouts \
    qml6-module-qtquick-window qml6-module-qtqml-workerscript \
    qt6-qpa-plugins && rm -rf /var/lib/apt/lists/* && \
    useradd --uid 1000 --create-home builder
WORKDIR /src
COPY --chown=1000:1000 CMakeLists.txt /src/
COPY --chown=1000:1000 native /src/native
COPY --chown=1000:1000 openpowermenu/data /src/openpowermenu/data
COPY --chown=1000:1000 plasmoid/contents/ui /src/plasmoid/contents/ui
RUN chown builder:builder /src
USER 1000:1000
RUN cmake -S /src -B /tmp/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DOPM_BUILD_EDITOR=ON && \
    cmake --build /tmp/build --parallel 2 && \
    ctest --test-dir /tmp/build --output-on-failure && \
    cmake --install /tmp/build --prefix /tmp/stage

FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libqt6core6t64 libqt6dbus6 libqt6gui6 libqt6qml6 libqt6quick6 \
    libqt6quickcontrols2-6 libkf6service6 libkf6configcore6 kde-cli-tools dbus \
    qml6-module-org-kde-kirigami qml6-module-qtquick-controls \
    qml6-module-qtquick-dialogs qml6-module-qtquick-layouts \
    qml6-module-qtquick-window qml6-module-qtqml-workerscript \
    qt6-qpa-plugins && rm -rf /var/lib/apt/lists/* && \
    useradd --uid 1000 --create-home opm
COPY --from=build /tmp/stage/bin/ /usr/local/bin/
COPY --chmod=0644 native/tests/editor-runtime-smoke.sh /usr/local/libexec/opm-editor-smoke.sh
RUN ! command -v python3 && ! command -v g++
USER 1000:1000
ENV LANG=C.UTF-8
CMD ["sh", "/usr/local/libexec/opm-editor-smoke.sh"]
