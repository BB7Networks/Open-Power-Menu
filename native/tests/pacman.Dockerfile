# Build and install a distribution-specific pacman package on a disposable image.
# The runtime stage is intentionally independent of build and legacy Python tools.
ARG OPM_BASE_IMAGE=archlinux:base
FROM ${OPM_BASE_IMAGE} AS build
RUN pacman -Syu --noconfirm --needed base-devel cmake ninja extra-cmake-modules \
    qt6-base qt6-declarative qt6-wayland kirigami kservice kconfig kde-cli-tools \
    dbus python pyside6 xorg-server-xvfb xorg-xauth && (getent passwd 1000 >/dev/null || useradd --uid 1000 --create-home builder)
WORKDIR /src
COPY --chown=1000:1000 . /src
USER 1000:1000
ENV LANG=C.UTF-8
WORKDIR /src/work/pacman-source
RUN sha256sum -c SOURCE.sha256 && makepkg --noconfirm --nocolor && \
    mkdir artifacts && \
    cp ./*.pkg.tar.zst SOURCE-COMMIT SOURCE.sha256 artifacts/ && \
    sha256sum ./*.pkg.tar.zst > artifacts/PACKAGE.sha256 && \
    cp src/build/OpenPowerMenu-*.tar.gz src/build/OpenPowerMenu-*.sha256 src/build/*.plasmoid artifacts/ && \
    cp /etc/os-release artifacts/os-release && pacman -Q > artifacts/packages.txt && \
    printf '%s\n' '2.1.0-dev development artifacts. Physical Plasma acceptance and explicit release approval are still required.' > artifacts/DEVELOPMENT-ONLY.txt
# Test actual legacy migration and all transaction fault paths in a separate
# instrumented bundle. The already-built package/artifacts retain hooks OFF.
RUN cmake -S src/Open-Power-Menu -B src/build -DOPM_INSTALL_TEST_HOOKS=ON && \
    cmake --build src/build --target native-bundle --parallel 2 && \
    python src/Open-Power-Menu/native/tests/packaging.py --bundle src/build/native-bundle --legacy /src/work/package-legacy -v

FROM ${OPM_BASE_IMAGE}
ARG OPM_RUNTIME_PYTHON=absent
ENV OPM_TEST_RUNTIME_PYTHON=${OPM_RUNTIME_PYTHON}
RUN pacman -Syu --noconfirm --needed qt6-base qt6-declarative qt6-wayland \
    kirigami kservice kconfig kde-cli-tools dbus && (getent passwd 1000 >/dev/null || useradd --uid 1000 --create-home opm)
COPY --from=build /src/work/pacman-source/artifacts /opt/opm-artifacts
RUN pacman -U --noconfirm /opt/opm-artifacts/*.pkg.tar.zst && \
    pacman -Q > /opt/opm-artifacts/runtime-packages.txt && \
    for tool in g++ cmake; do \
        if command -v "$tool" >/dev/null; then echo "Unexpected runtime tool: $tool" >&2; exit 1; fi; \
    done && \
    if [ "$OPM_RUNTIME_PYTHON" = absent ]; then \
        ! command -v python && ! command -v python3; \
    elif [ "$OPM_RUNTIME_PYTHON" = distro ]; then \
        python -c 'import importlib.util; assert importlib.util.find_spec("PySide6") is None'; \
    else exit 1; fi && \
    for binary in /usr/lib/open-power-menu-native/bundle/app/bin/*; do \
        libraries=$(ldd "$binary") || exit 1; \
        printf '%s\n%s\n' "$binary" "$libraries"; \
        case "$libraries" in *'not found'*) exit 1;; esac; \
    done
COPY --chmod=0644 native/tests/package-runtime-smoke.sh /usr/local/libexec/opm-package-smoke.sh
ENV LANG=C.UTF-8 OPM_TEST_BUNDLE=/usr/lib/open-power-menu-native/bundle OPM_TEST_SETUP=/usr/bin/open-power-menu-native-setup
USER 1000:1000
CMD ["sh", "/usr/local/libexec/opm-package-smoke.sh"]
