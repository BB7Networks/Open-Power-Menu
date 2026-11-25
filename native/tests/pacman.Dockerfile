# Build and install a distribution-specific pacman package on a disposable image.
# The runtime stage is intentionally independent of build and legacy Python tools.
ARG OPM_BASE_IMAGE=archlinux:base
ARG OPM_ARCH_SNAPSHOT=""
FROM ${OPM_BASE_IMAGE} AS build
ARG OPM_ARCH_SNAPSHOT
ARG OPM_SESSION_PROFILE=plasma67-x11
ENV OPM_SESSION_PROFILE=${OPM_SESSION_PROFILE}
RUN if [ -n "$OPM_ARCH_SNAPSHOT" ]; then \
        printf 'Server = https://archive.archlinux.org/repos/%s/$repo/os/$arch\n' "$OPM_ARCH_SNAPSHOT" > /etc/pacman.d/mirrorlist; \
    fi
# Archived large packages can stall for more than libalpm's ten-second
# low-speed threshold. Keep signatures/transactions intact; the CI job retains
# its overall deadline instead of treating that transfer stall as a test fail.
RUN pacman --disable-download-timeout -Syu --noconfirm --needed base-devel cmake ninja extra-cmake-modules \
    qt6-base qt6-declarative qt6-svg qt6-wayland kirigami kservice kconfig kde-cli-tools \
    dbus python pyside6 unzip xorg-server-xvfb xorg-xauth xorg-xprop xdotool xterm qt6-tools \
    plasma-desktop plasma-workspace kwin discover dolphin konsole systemsettings powerdevil plasma-nm print-manager \
    plasma-systemmonitor kinfocenter ksystemlog partitionmanager virt-manager krdc && \
    case "$OPM_SESSION_PROFILE" in \
        plasma67-x11) pacman --disable-download-timeout -S --noconfirm --needed kwin-x11 && command -v kwin_x11;; \
        manjaro-wayland) ! command -v kwin_x11;; \
        *) exit 1;; \
    esac && command -v kwin_wayland && \
    (getent passwd 1000 >/dev/null || useradd --uid 1000 --create-home builder)
# Qualify the primary Manjaro software manager as well as Discover. This is
# dependency setup in a disposable test image, never application runtime logic.
RUN . /etc/os-release && if [ "$ID" = manjaro ]; then \
      if pacman --disable-download-timeout -Si pamac-gtk >/dev/null 2>&1; then pacman --disable-download-timeout -S --noconfirm --needed pamac-gtk; \
      else pacman --disable-download-timeout -S --noconfirm --needed pamac-gtk3; fi; fi
WORKDIR /src
COPY --chown=1000:1000 . /src
USER 1000:1000
ENV LANG=C.UTF-8
WORKDIR /src/work/pacman-source
RUN sha256sum -c SOURCE.sha256 && mkdir artifacts && \
    python /src/scripts/qualification_profiles.py --profile "$OPM_SESSION_PROFILE" --output artifacts/session-coverage.json && \
    pacman -Q > artifacts/packages.txt && makepkg --noconfirm --nocolor && \
    cp ./*.pkg.tar.zst SOURCE-COMMIT SOURCE.sha256 open-power-menu-source.tar.gz artifacts/ && \
    sha256sum ./*.pkg.tar.zst > artifacts/PACKAGE.sha256 && \
    cp src/build/OpenPowerMenu-*.tar.gz src/build/OpenPowerMenu-*.sha256 src/build/*.plasmoid artifacts/ && \
    python src/Open-Power-Menu/native/packaging/prepare-ez.py --allow-arch-test --bundle src/build/native-bundle --output /tmp/ez-final && unzip -q /tmp/ez-final/*.zip -d /tmp/ez-final/root && \
    cp /tmp/ez-final/*.zip /tmp/ez-final/*.sha256 artifacts/ && \
    cp /etc/os-release artifacts/os-release && pacman -Q > artifacts/packages.txt && \
    XDG_CURRENT_DESKTOP=KDE QT_QPA_PLATFORM=offscreen python src/Open-Power-Menu/native/tests/application_resolution.py \
      --probe src/build/native/native-application-probe --live-audit artifacts/applications.json && \
    printf '%s\n' 'Stable 2.1.0 preparation artifacts; publication not approved. Physical Plasma acceptance remains pending; new installs follow KDE; existing immediate preferences and explicit custom commands are preserved.' > artifacts/CANDIDATE.txt
# CI exercises the sealed EZ payload on both application platforms and every
# supported session. Plasma 6.8 uses a software buffer device passed only to
# that offline test container; Docker build steps have no render device.
# Test actual legacy migration and all transaction fault paths in a separate
# instrumented bundle. The already-built package/artifacts retain hooks OFF.
RUN cmake -S /src/work/package-rc1 -B /tmp/rc1-build -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DOPM_BUILD_PACKAGE=ON -DBUILD_TESTING=OFF -DOPM_SOURCE_COMMIT=2384a9d03947b9a2e5de8f0ef72ae57e556bc29c && \
    cmake --build /tmp/rc1-build --target native-bundle --parallel 2
RUN cmake -S /src/work/package-rc2 -B /tmp/rc2-build -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DOPM_BUILD_PACKAGE=ON -DBUILD_TESTING=OFF -DOPM_SOURCE_COMMIT=2f889df3e5b29f49611f8cf37f41f15e86cad7c1 && \
    cmake --build /tmp/rc2-build --target native-bundle --parallel 2
RUN cmake -S src/Open-Power-Menu -B src/build -DOPM_INSTALL_TEST_HOOKS=ON && \
    cmake --build src/build --target native-bundle --parallel 2 && \
    python src/Open-Power-Menu/native/packaging/prepare-ez.py --allow-arch-test --bundle src/build/native-bundle --output /tmp/ez-test && unzip -q /tmp/ez-test/*.zip -d /tmp/ez-test/root && \
    python src/Open-Power-Menu/native/tests/packaging.py --bundle src/build/native-bundle --legacy /src/work/package-legacy --rc1-bundle /tmp/rc1-build/native-bundle --rc2-bundle /tmp/rc2-build/native-bundle --ez /tmp/ez-test/root/* -v

FROM ${OPM_BASE_IMAGE} AS native-runtime
ARG OPM_ARCH_SNAPSHOT
ARG OPM_RUNTIME_PYTHON=absent
ENV OPM_TEST_RUNTIME_PYTHON=${OPM_RUNTIME_PYTHON}
RUN if [ -n "$OPM_ARCH_SNAPSHOT" ]; then \
        printf 'Server = https://archive.archlinux.org/repos/%s/$repo/os/$arch\n' "$OPM_ARCH_SNAPSHOT" > /etc/pacman.d/mirrorlist; \
    fi
RUN pacman --disable-download-timeout -Syu --noconfirm --needed qt6-base qt6-declarative qt6-svg qt6-wayland \
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
RUN --network=none sh /usr/local/libexec/opm-package-smoke.sh && printf 'passed\n' > /tmp/native-runtime-smoke

# Preserve the independent minimal runtime test before adding Plasma, whose
# distribution dependencies may include Python. OPM still requires no PySide6.
FROM native-runtime
USER 0:0
RUN pacman --disable-download-timeout -S --noconfirm --needed plasma-workspace && \
    python3 -c 'import importlib.util; assert importlib.util.find_spec("PySide6") is None' && \
    cp /tmp/native-runtime-smoke /opt/opm-artifacts/native-runtime-smoke && \
    pacman -Q > /opt/opm-artifacts/runtime-packages.txt
COPY --from=build /tmp/ez-final/root/ /opt/opm-ez/
ENV OPM_TEST_RUNTIME_PYTHON=distro
RUN if bash /opt/opm-ez/*/install.sh --yes > /tmp/root-refusal.log 2>&1; then exit 1; fi && \
    grep -q 'without sudo' /tmp/root-refusal.log
USER 1000:1000
CMD ["sh", "/usr/local/libexec/opm-package-smoke.sh"]
