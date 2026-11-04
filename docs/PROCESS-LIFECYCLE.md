# Application lifecycle and resource accounting

## Findings

Both the widget's D-Bus `Run` method and standalone menu already used
`Popen(argv, close_fds=True, start_new_session=True)`. The backend's `Edit`
method used the same flags for the editor. The editor discovers applications
and prepares commands without launching them; the picker prefers native
`kioclient6 exec <desktop-file>`, then GIO where supported. The QML widget calls
the backend; its native launcher adapters activate the selected applet rather
than executing arbitrary command strings.

On Linux, `start_new_session` calls `setsid`: a launched command becomes the
leader of a new session and process group. It remains an OPM child until OPM
exits, and inherits the same systemd cgroup unless a desktop launcher or another
component moves it. Its display/session environment and user permissions are
inherited. Seeing an application below OPM in a process tree is expected and
does not establish that OPM consumes the application's CPU or owns its lifetime.

KDE's process backend explicitly accumulates descendant CPU usage into ancestor
totals. Its application model also groups processes by cgroup and aggregates
attributes. Grouped CPU/memory figures therefore need to be distinguished from
the backend PID's own CPU time and resident memory. This explains a plausible
cause of the workstation observation; the exact System Monitor view, versions,
and cgroup placement on those workstations still need to be recorded. A desktop
helper may activate a process with a different parent than a direct command.

## Defects reproduced and corrections

The original long-lived backend left an exited, directly launched command in
`Z` state until another `Popen` or backend exit. Python only opportunistically
cleans up discarded `Popen` objects. This was reproduced with a harmless child
that recorded its PID and exited while the real backend stayed alive.

The original children also inherited standard streams. In a supervisor/test
capturing backend output, a long-running child can retain those pipe endpoints
after the backend exits. That delays EOF for the reader and couples the child's
I/O to a backend-owned stream, even though the backend itself can exit.

The shared `launching.py` helper retains argv execution, `close_fds` and detached
sessions, and connects standard input/output/error to `/dev/null`. Exec failures
still reach the backend error path or the standalone menu's error dialog.
Commands that need visible output should explicitly launch a terminal. Desktop
environment variables, D-Bus activation and normal user permissions are preserved.

The backend retains child handles and polls them once per second **only while
children remain**, stopping the reaper timer when all have finished. It never
signals applications during idle shutdown or backend restart. The standalone
menu returns immediately after launching; its process exit transfers child
ownership to the OS. No double-fork, systemd dependency or privilege wrapper was
added.

## What the automated checks establish

`tests/test_launching.py` verifies real PID/PPID/SID/process-group relationships,
literal arguments, closed unrelated descriptors, detached standard streams,
exec failure and reaping. `tests/test_qt_runtime.py` exercises the actual Qt
standalone menu and D-Bus backend with a harmless CPU/heartbeat workload.

The workload keeps progressing after normal backend termination, `SIGKILL`,
normal Qt idle exit, and the ownership-checked installed-backend upgrade stop
followed by replacement backend startup and Ping.
For the idle test only, a QTimer subclass shortens the production five-minute
interval; the service's actual idle-shutdown path remains in use. The standalone
test selects a real QAction through Qt's event delivery and verifies progress
after the popup closes. Tests also verify no child keeps captured backend output
open, an exited child disappears from `/proc`, and invalid command keys cannot
launch a program. A one-second sample records CPU and RSS separately for the
backend and the dummy workload without applying timing-sensitive thresholds.

One cloud sample recorded 0.00 CPU seconds / 25,952,256 RSS bytes for the backend
and 0.09 CPU seconds / 8,650,752 RSS bytes for the child over one second. Both
remained in the same cgroup while their own PID usage differed. These are a
single Linux-container observation, not a performance guarantee or a measurement
of the workstations' System Monitor display.

## Limits and systemd scopes

`setsid` does not protect an application from an external **cgroup-wide** stop,
user logout, session teardown, OOM policies or explicit group kills. The current
installer stops only the verified backend PID; it does not stop its cgroup.
No live Plasma user service manager is available in the cloud test environment.

Do not introduce `systemd-run --user --scope` on ancestry evidence alone. It
changes launch semantics, may be unavailable on other systems, and scopes are
normally synchronous unless deliberately detached. Evaluate application units,
desktop activation and `KillMode` on a real Plasma/systemd session before adding
a scope policy. There is no demonstrated need for one to survive the backend's
current PID-only shutdown. The remaining accounting presentation may still
benefit from native desktop application units; that is a separate live-tested
improvement, not a claimed fix here.

For workstation acceptance, compare the backend PID's `/proc/<pid>/stat`,
`/proc/<pid>/status` and `/proc/<pid>/cgroup` with its child. Record System
Monitor's selected view and columns. Use the dummy workload, not a real scrub.

References:

- [Python subprocess options](https://docs.python.org/3/library/subprocess.html#popen-constructor)
- [KDE descendant CPU totals](https://github.com/KDE/libksysguard/blob/master/processcore/processes.cpp)
- [KDE cgroup application model](https://github.com/KDE/libksysguard/blob/master/processcore/cgroup_data_model.cpp)
- [systemd KillMode](https://www.freedesktop.org/software/systemd/man/latest/systemd.kill.html)
