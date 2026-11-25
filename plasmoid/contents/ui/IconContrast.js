.pragma library

// Mask the stock monochrome glyphs that can become white-on-white with a
// dark system icon palette. Other/free-form theme icons keep their colors.
// The list intentionally excludes colorful app icons (system-file-manager,
// battery, utilities-system-monitor, preferences-system, user-desktop).
var monochrome = [
    "view-list-details", "computer", "network-wired", "network-wireless",
    "drive-harddisk", "preferences-devices-printer",
    "preferences-desktop-remote-desktop", "system-search", "network-server",
    "system-shutdown", "system-lock-screen", "system-log-out",
    "system-reboot", "system-suspend", "system-suspend-hibernate"
];

function shouldMask(appearance, iconName) {
    if (appearance !== "aero-light" || typeof iconName !== "string" || !iconName)
        return false;
    // Never tint custom PNG, SVG, URLs or image resource paths.
    if (iconName.indexOf("/") !== -1 || iconName.indexOf("\\") !== -1 ||
        iconName.indexOf(":") !== -1)
        return false;
    return iconName.endsWith("-symbolic") || monochrome.indexOf(iconName) !== -1;
}
