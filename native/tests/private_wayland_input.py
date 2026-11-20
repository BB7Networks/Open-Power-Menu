#!/usr/bin/env python3
"""Seed a real input serial on the private KWin test seat, never a desktop seat.

Qt 6.10 requires real Wayland input before granting a popup grab. QTest events
alone cannot supply that compositor serial. Send one harmless Shift press and
release via KWin's fake-input protocol, then wait for the compositor's roundtrip.
Only standalone-wayland.sh enables this helper on its freshly created socket.
"""
import os
from pathlib import Path
import socket
import struct

runtime = Path(os.environ['XDG_RUNTIME_DIR'])
expected = os.environ.get('OPM_TEST_PRIVATE_WAYLAND_SOCKET')
endpoint = runtime/os.environ['WAYLAND_DISPLAY']
assert expected == str(endpoint) and endpoint.name == 'opm-test-wayland'
assert runtime.parent == Path('/tmp') and runtime.name.startswith('opm-wayland.')
assert (runtime/'.opm-private-seat').read_text() == 'standalone-wayland fixture\n'
assert runtime.stat().st_uid == os.getuid() and runtime.stat().st_mode & 0o077 == 0


def number(value):
    return struct.pack('=I', value)


def string(value):
    value = value.encode()+b'\0'
    return number(len(value))+value+b'\0'*((-len(value)) % 4)


with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
    connection.settimeout(3)
    connection.connect(str(endpoint))

    def send(obj, opcode, data=b''):
        connection.sendall(struct.pack('=II', obj, ((len(data)+8) << 16) | opcode)+data)

    def read(length):
        result = b''
        while len(result) < length:
            chunk = connection.recv(length-len(result))
            if not chunk:
                raise RuntimeError('Private compositor disconnected')
            result += chunk
        return result

    available = []

    def roundtrip(callback):
        send(1, 0, number(callback))  # wl_display.sync
        while True:
            obj, header = struct.unpack('=II', read(8))
            opcode, length = header & 0xffff, header >> 16
            if length < 8 or length > 65536:
                raise RuntimeError('Invalid private Wayland message')
            data = read(length-8)
            if obj == 1 and opcode == 0:
                raise RuntimeError('Private Wayland protocol error: '+repr(data))
            if obj == 2 and opcode == 0:  # wl_registry.global
                name, size = struct.unpack('=II', data[:8])
                interface = data[8:8+size-1].decode()
                version = struct.unpack_from('=I', data, 8+((size+3)//4)*4)[0]
                available.append((name, interface, version))
            if obj == callback and opcode == 0:
                return

    send(1, 1, number(2))  # wl_display.get_registry
    roundtrip(3)
    name, interface, version = next(item for item in available if item[1] == 'org_kde_kwin_fake_input')
    assert version >= 4, 'Private KWin keyboard protocol is required'
    send(2, 0, number(name)+string(interface)+number(4)+number(4))  # registry.bind, version 4
    send(4, 0, string('OPM disposable test')+string('Native popup input-serial qualification'))
    send(4, 10, number(42)+number(1))  # KEY_LEFTSHIFT pressed
    send(4, 10, number(42)+number(0))  # KEY_LEFTSHIFT released
    roundtrip(5)
