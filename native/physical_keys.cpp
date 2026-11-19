#include "physical_keys.hpp"
#include <QGuiApplication>
#include <QSocketNotifier>
#include <xcb/xcb.h>
#include <xcb/xinput.h>
#include <cstdlib>

namespace Opm {
void PhysicalPresses::press(quint32 scan, quint32 time, quint16 source, bool repeat) {
    if (scan < 8 || scan > 255) return;
    const quint64 identity = (quint64(source) << 32) | scan;
    const bool wasDown = down.contains(identity) || unknownDown.contains(scan);
    down.insert(identity);
    if (!collecting || repeat || wasDown) return;
    if (presses.size() == 512) presses.dequeue(); // Overflow loses permission, never invents it.
    presses.enqueue({scan, time});
}
void PhysicalPresses::release(quint32 scan, quint16 source) {
    down.remove((quint64(source) << 32) | scan);
    unknownDown.remove(scan);
    navigation.remove(scan);
}
KeyAdmission PhysicalPresses::take(quint32 scan, quint32 time, bool arrow) {
    if (!collecting) return KeyAdmission::Reject;
    for (qsizetype i = 0; i < presses.size(); ++i) {
        if (presses[i].scan != scan || presses[i].time != time) continue;
        presses.removeAt(i);
        if (arrow) navigation.insert(scan);
        return KeyAdmission::Press;
    }
    if (arrow && navigation.contains(scan)) {
        for (quint64 identity : down)
            if (quint32(identity) == scan) return KeyAdmission::NavigationRepeat;
    }
    return KeyAdmission::Reject;
}

struct PhysicalKeys::X11 {
    xcb_connection_t *connection = nullptr;
    std::unique_ptr<QSocketNotifier> notifier;
    PhysicalPresses presses;
    int opcode = -1;
    bool valid = false;
    explicit X11() {
        int screen = 0;
        connection = xcb_connect(nullptr, &screen);
        if (xcb_connection_has_error(connection)) return;
        const auto *extension = xcb_get_extension_data(connection, &xcb_input_id);
        if (!extension || !extension->present) return;
        opcode = extension->major_opcode;
        auto *version = xcb_input_xi_query_version_reply(connection,
            xcb_input_xi_query_version(connection, 2, 2), nullptr);
        if (!version) return;
        const bool supported = version->major_version > 2 || (version->major_version == 2 && version->minor_version >= 2);
        free(version);
        if (!supported) return;
        auto screens = xcb_setup_roots_iterator(xcb_get_setup(connection));
        while (screen-- && screens.rem) xcb_screen_next(&screens);
        if (!screens.rem) return;
        struct Mask { xcb_input_event_mask_t header; uint32_t mask; } masks[] = {
            {{XCB_INPUT_DEVICE_ALL_MASTER, 1}, XCB_INPUT_XI_EVENT_MASK_RAW_KEY_PRESS | XCB_INPUT_XI_EVENT_MASK_RAW_KEY_RELEASE},
            {{XCB_INPUT_DEVICE_ALL, 1}, XCB_INPUT_XI_EVENT_MASK_HIERARCHY}
        };
        auto *error = xcb_request_check(connection,
            xcb_input_xi_select_events_checked(connection, screens.data->root, 2, &masks[0].header));
        if (error) { free(error); return; }
        valid = true;
        snapshot();
        if (!valid) return;
        notifier = std::make_unique<QSocketNotifier>(xcb_get_file_descriptor(connection), QSocketNotifier::Read);
        QObject::connect(notifier.get(), &QSocketNotifier::activated, notifier.get(), [this] { drain(); });
    }
    ~X11() { notifier.reset(); if (connection) xcb_disconnect(connection); }
    void snapshot() {
        auto *map = xcb_query_keymap_reply(connection, xcb_query_keymap(connection), nullptr);
        if (!map) { fail(); return; }
        QSet<quint32> held;
        for (quint32 key = 8; key < 256; ++key)
            if (quint8(map->keys[key / 8]) & (1u << (key % 8))) held.insert(key);
        free(map);
        presses.snapshot(held);
    }
    void fail() {
        valid = false;
        presses.collect(false);
        if (notifier) notifier->setEnabled(false);
    }
    void drain() {
        if (!valid) return;
        while (auto *event = xcb_poll_for_event(connection)) {
            if ((event->response_type & 127) == XCB_GE_GENERIC) {
                const auto *raw = reinterpret_cast<xcb_input_raw_key_press_event_t *>(event);
                if (raw->extension == opcode) {
                    if (raw->event_type == XCB_INPUT_RAW_KEY_PRESS)
                        presses.press(raw->detail, raw->time, raw->sourceid, raw->flags & XCB_INPUT_KEY_EVENT_FLAGS_KEY_REPEAT);
                    else if (raw->event_type == XCB_INPUT_RAW_KEY_RELEASE)
                        presses.release(raw->detail, raw->sourceid);
                    else if (raw->event_type == XCB_INPUT_HIERARCHY) snapshot();
                }
            }
            free(event);
        }
        if (xcb_connection_has_error(connection)) fail();
    }
    void synchronize() {
        if (!valid) return;
        // Read-only server ordering barrier: raw input travels on our own
        // connection, independently of Qt's socket notifier. No timed wait,
        // focus operation, XKB setting, grab, or core-event look-ahead heuristic.
        auto *reply = xcb_get_input_focus_reply(connection, xcb_get_input_focus(connection), nullptr);
        if (!reply) { fail(); return; }
        free(reply);
        drain();
    }
};

PhysicalKeys::PhysicalKeys(QObject *parent) : QObject(parent) {
    if (QGuiApplication::platformName() == "xcb") x11 = std::make_unique<X11>();
}
PhysicalKeys::~PhysicalKeys() = default;
bool PhysicalKeys::ready() const { return !x11 || x11->valid; }
void PhysicalKeys::setActive(bool value) {
    if (value == active) return;
    if (x11) {
        x11->synchronize(); // Drain input that preceded opening before collecting.
        x11->presses.collect(value && x11->valid);
    }
    navigation.clear();
    // Do not clear held keys on focus transfer, closure, or reopening. On
    // Wayland a release outside our windows is unobservable: remain closed to
    // that key until a real (non-repeat) release is received in our windows.
    active = value;
}
KeyAdmission PhysicalKeys::press(const QKeyEvent &event) {
    if (!ready()) return KeyAdmission::Reject;
    const bool arrow = event.key() == Qt::Key_Up || event.key() == Qt::Key_Down;
    if (x11) {
        if (!active) return KeyAdmission::Reject;
        x11->synchronize();
        if (!x11->valid) return KeyAdmission::Reject;
        return x11->presses.take(event.nativeScanCode(), quint32(event.timestamp()), arrow);
    }
    const bool down = held.contains(event.key());
    held.insert(event.key());
    if (!active) return KeyAdmission::Reject;
    if (!down && !event.isAutoRepeat()) {
        if (arrow) navigation.insert(event.key());
        return KeyAdmission::Press;
    }
    return arrow && navigation.contains(event.key()) ? KeyAdmission::NavigationRepeat : KeyAdmission::Reject;
}
void PhysicalKeys::release(const QKeyEvent &event) {
    // Core X11 releases include synthetic repeat releases, even when Qt calls
    // them fresh. Only the separate XI2 stream can rearm the X11 ledger.
    if (x11 || event.isAutoRepeat()) return;
    held.remove(event.key());
    navigation.remove(event.key());
}
} // namespace Opm
