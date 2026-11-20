#pragma once
#include <QProcessEnvironment>
#include <QString>

namespace Opm {
struct EditorEnvironment {
    QProcessEnvironment environment;
    QString source;
    QString error;
};
// Query the current session each time; never cache display/authentication state.
EditorEnvironment editorEnvironment(const QProcessEnvironment &base, const QString &requester = {},
                                    bool smokeTest = false);
void reportEditorStartup(const QString &destination, const QString &token, const QString &error);
int coordinateEditor(int argc, char **argv);
inline constexpr char editorReady[] = "OPM_EDITOR_FIRST_FRAME_V1";
} // namespace Opm
