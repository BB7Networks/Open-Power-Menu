# Disposable Debian 13 build/test image, followed by a no-Python GUI runtime.
# The resulting ELF is a Debian 13 development artifact, not a universal package.
ARG OPM_DEB_IMAGE=debian:trixie-slim
FROM ${OPM_DEB_IMAGE} AS build
ARG OPM_SOURCE_COMMIT
WORKDIR /src
COPY --chown=1000:1000 . /src
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake ninja-build g++ qt6-base-dev qt6-declarative-dev libxcb-xinput-dev \
    libkf6service-dev libkf6config-dev kde-cli-tools dbus \
    qml6-module-org-kde-kirigami qml6-module-qtquick-controls \
    qml6-module-qtquick-dialogs qml6-module-qtquick-layouts \
    qml6-module-qtquick-window qml6-module-qtqml-workerscript \
    plasma-workspace kwin-wayland unzip qt6-svg-plugins qt6-qpa-plugins qt6-wayland xvfb xauth systemd python3 python3-pyside6.qtdbus python3-pyside6.qtwidgets && rm -rf /var/lib/apt/lists/* && \
    (getent passwd 1000 >/dev/null || useradd --uid 1000 --create-home builder)
RUN chown 1000:1000 /src
USER 1000:1000
RUN cmake -S /src/work/package-rc1 -B /tmp/rc1-build -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DOPM_BUILD_PACKAGE=ON -DBUILD_TESTING=OFF -DOPM_SOURCE_COMMIT=2384a9d03947b9a2e5de8f0ef72ae57e556bc29c && \
    cmake --build /tmp/rc1-build --target native-bundle --parallel 2
RUN cmake -S /src/work/package-rc2 -B /tmp/rc2-build -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DOPM_BUILD_PACKAGE=ON -DBUILD_TESTING=OFF -DOPM_SOURCE_COMMIT=2f889df3e5b29f49611f8cf37f41f15e86cad7c1 && \
    cmake --build /tmp/rc2-build --target native-bundle --parallel 2
RUN umask 022 && cmake -S /src -B /tmp/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DOPM_BUILD_PACKAGE=ON -DOPM_INSTALL_TEST_HOOKS=ON -DOPM_SOURCE_COMMIT=${OPM_SOURCE_COMMIT} && \
    cmake --build /tmp/build --parallel 2 && \
    ctest --test-dir /tmp/build --output-on-failure --output-junit /tmp/packaging-tests.xml && \
    cmake --build /tmp/build --target native-bundle && \
    python3 native/packaging/prepare-ez.py --bundle /tmp/build/native-bundle --output /tmp/ez-test && unzip -q /tmp/ez-test/*.zip -d /tmp/ez-test/root && \
    python3 native/tests/packaging.py --bundle /tmp/build/native-bundle --legacy /src/work/package-legacy --rc1-bundle /tmp/rc1-build/native-bundle --rc2-bundle /tmp/rc2-build/native-bundle --ez /tmp/ez-test/root/* -v && \
    cmake -S /src -B /tmp/build -DOPM_INSTALL_TEST_HOOKS=OFF && \
    cmake --build /tmp/build --target native-package --parallel 2 && \
    python3 native/packaging/prepare-ez.py --bundle /tmp/build/native-bundle --output /tmp/ez-final && unzip -q /tmp/ez-final/*.zip -d /tmp/ez-final/root && \
    mkdir /tmp/qualification && cp /tmp/packaging-tests.xml /tmp/qualification/ && \
    xvfb-run -a sh native/tests/ez-desktop-smoke.sh /tmp/ez-final/root/* xcb /tmp/qualification && \
    dbus-run-session -- env OPM_WAYLAND_COMPOSITOR=kwin sh native/tests/standalone-wayland.sh sh native/tests/ez-desktop-smoke.sh /tmp/ez-final/root/* wayland /tmp/qualification && \
    cp /tmp/build/OpenPowerMenu-*.tar.gz /tmp/build/OpenPowerMenu-*.sha256 /tmp/ez-final/*.zip /tmp/ez-final/*.sha256 /tmp/qualification/ && \
    cp /tmp/build/native-bundle/bundle.json /tmp/qualification/ && \
    cp /etc/os-release /tmp/qualification/os-release && dpkg-query -W > /tmp/qualification/packages.txt && \
    printf '%s\n' "$OPM_SOURCE_COMMIT" > /tmp/qualification/SOURCE-COMMIT

FROM ${OPM_DEB_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends \
    libqt6core6t64 libqt6dbus6 libqt6gui6 libqt6widgets6 libqt6qml6 libqt6quick6 \
    libqt6quickcontrols2-6 libkf6service6 libkf6configcore6 libxcb-xinput0 kde-cli-tools dbus \
    qml6-module-org-kde-kirigami qml6-module-qtquick-controls \
    qml6-module-qtquick-dialogs qml6-module-qtquick-layouts \
    qml6-module-qtquick-window qml6-module-qtqml-workerscript \
    plasma-workspace qt6-svg-plugins qt6-qpa-plugins qt6-wayland && rm -rf /var/lib/apt/lists/* && \
    (getent passwd 1000 >/dev/null || useradd --uid 1000 --create-home opm)
COPY --from=build /tmp/build/native-bundle /opt/opm-bundle
COPY --from=build /tmp/ez-final/root/ /opt/opm-ez/
COPY --from=build /tmp/qualification /opt/opm-evidence
COPY --chmod=0644 native/tests/package-runtime-smoke.sh /usr/local/libexec/opm-package-smoke.sh
RUN ! command -v python3 && ! command -v g++ && \
    if bash /opt/opm-ez/*/install.sh --yes > /tmp/root-refusal.log 2>&1; then exit 1; fi && \
    grep -q 'without sudo' /tmp/root-refusal.log
USER 1000:1000
ENV LANG=C.UTF-8
CMD ["sh", "/usr/local/libexec/opm-package-smoke.sh"]
