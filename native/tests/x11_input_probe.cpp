// Read-only XI2 evidence on the keyboard fixture's private X server. Never
// installed, never changes XKB, focus, grabs or autorepeat configuration.
#include <QCoreApplication>
#include <QDateTime>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSocketNotifier>
#include <QTimer>
#include <cstdio>
#include <cstdlib>
#include <xcb/xcb.h>
#include <xcb/xinput.h>

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    if (qEnvironmentVariable("OPM_PRIVATE_X11_EVIDENCE") != qEnvironmentVariable("DISPLAY") ||
        !qEnvironmentVariable("DISPLAY").startsWith(':')) return 2;
    auto *connection = xcb_connect(nullptr, nullptr);
    if (xcb_connection_has_error(connection)) return 3;
    const auto *extension = xcb_get_extension_data(connection, &xcb_input_id);
    if (!extension || !extension->present) return 4;
    auto *version = xcb_input_xi_query_version_reply(connection,
        xcb_input_xi_query_version(connection, 2, 2), nullptr);
    if (!version || version->major_version < 2 ||
        (version->major_version == 2 && version->minor_version < 2)) return 5;
    free(version);
    struct Mask { xcb_input_event_mask_t header; uint32_t mask; } mask = {
        {XCB_INPUT_DEVICE_ALL_MASTER, 1},
        XCB_INPUT_XI_EVENT_MASK_RAW_KEY_PRESS | XCB_INPUT_XI_EVENT_MASK_RAW_KEY_RELEASE};
    const auto root = xcb_setup_roots_iterator(xcb_get_setup(connection)).data->root;
    auto *error = xcb_request_check(connection,
        xcb_input_xi_select_events_checked(connection, root, 1, &mask.header));
    if (error) { free(error); return 6; }
    auto focus = [&] {
        auto *reply = xcb_get_input_focus_reply(connection, xcb_get_input_focus(connection), nullptr);
        const auto window = reply ? reply->focus : XCB_WINDOW_NONE;
        free(reply);
        return window;
    };
    auto write = [&](QJsonObject row) {
        row["time_ms"] = QDateTime::currentMSecsSinceEpoch();
        row["focus"] = double(focus());
        const auto bytes = QJsonDocument(row).toJson(QJsonDocument::Compact);
        std::printf("%s\n", bytes.constData()); std::fflush(stdout);
    };
    QSocketNotifier notifier(xcb_get_file_descriptor(connection), QSocketNotifier::Read);
    auto drain = [&] {
        while (auto *event = xcb_poll_for_event(connection)) {
            if ((event->response_type & 127) == XCB_GE_GENERIC) {
                const auto *raw = reinterpret_cast<xcb_input_raw_key_press_event_t *>(event);
                if (raw->extension == extension->major_opcode &&
                    (raw->event_type == XCB_INPUT_RAW_KEY_PRESS || raw->event_type == XCB_INPUT_RAW_KEY_RELEASE))
                    write({{"event", raw->event_type == XCB_INPUT_RAW_KEY_PRESS ? "press" : "release"},
                        {"scan", int(raw->detail)}, {"server_time", double(raw->time)},
                        {"source", int(raw->sourceid)},
                        {"repeat", bool(raw->flags & XCB_INPUT_KEY_EVENT_FLAGS_KEY_REPEAT)}});
            }
            free(event);
        }
        if (xcb_connection_has_error(connection)) {
            write({{"event", "server-disconnected"}}); app.exit(7);
        }
    };
    QObject::connect(&notifier, &QSocketNotifier::activated, &app, drain);
    xcb_window_t previous = XCB_WINDOW_NONE;
    QTimer timer;
    QObject::connect(&timer, &QTimer::timeout, &app, [&] {
        auto current = focus();
        if (current != previous) { previous = current; write({{"event", "focus"}}); }
        // A synchronous read-only reply can queue XI2 events in libxcb without
        // leaving bytes on its socket. Drain that queue as well as FD wakeups.
        drain();
    });
    timer.start(20);
    write({{"event", "ready"}});
    const int result = app.exec();
    xcb_disconnect(connection);
    return result;
}
