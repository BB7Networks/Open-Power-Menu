# Rolling distro qualification, not a claim that Arch binaries run on Manjaro.
FROM archlinux:base-devel
RUN pacman -Syu --noconfirm --needed cmake ninja qt6-base qt6-declarative qt6-svg qt6-wayland kirigami kservice kconfig kde-cli-tools dbus python xorg-server-xvfb xorg-xauth && \
    useradd --uid 1000 --create-home builder
WORKDIR /src
COPY --chown=1000:1000 . /src
USER 1000:1000
RUN cmake -S . -B /tmp/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DOPM_BUILD_PACKAGE=ON && \
    cmake --build /tmp/build --parallel 2 && \
    QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software ctest --test-dir /tmp/build --output-on-failure && \
    cmake --build /tmp/build --target native-package && \
    ldd /tmp/build/native/open-power-menu-native && \
    ldd /tmp/build/native/open-power-menu-editor && \
    ldd /tmp/build/native/open-power-menu-standalone
CMD ["sh", "-c", "QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software ctest --test-dir /tmp/build --output-on-failure"]
