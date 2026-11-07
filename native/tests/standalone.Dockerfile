# Isolated native build and no-Python/no-compiler runtime acceptance.
FROM debian:trixie-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake ninja-build g++ qt6-base-dev dbus && rm -rf /var/lib/apt/lists/* && \
    useradd --uid 1000 --create-home builder
WORKDIR /src
COPY --chown=1000:1000 CMakeLists.txt /src/
COPY --chown=1000:1000 native /src/native
COPY --chown=1000:1000 openpowermenu/data /src/openpowermenu/data
RUN chown builder:builder /src
USER 1000:1000
RUN cmake -S . -B /tmp/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DOPM_BUILD_STANDALONE=ON && \
    cmake --build /tmp/build --parallel 2 && \
    ctest --test-dir /tmp/build --output-on-failure && \
    cmake --install /tmp/build --prefix /tmp/stage
FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libqt6widgets6 qt6-qpa-plugins qt6-wayland dbus && rm -rf /var/lib/apt/lists/*
COPY --from=build /tmp/stage/bin/ /usr/local/bin/
COPY native/tests/standalone-runtime-smoke.sh /smoke.sh
ENV LANG=C.UTF-8
# Root only inside this disposable image, to simulate a missing runtime library.
CMD ["sh", "/smoke.sh"]
