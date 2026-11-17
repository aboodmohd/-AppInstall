"""Read-only, source-aware Discover categories and featured picks (v1.8).

Categories come from provider/AppStream fields only, never guessed from
package names. Only Flathub's live popular collection is ranked Featured.
"""
import re

CATEGORY_ORDER = (
    "Internet", "Graphics", "Office", "Development", "Games",
    "Multimedia", "Education", "Science", "Utilities", "System", "Other",
)
_ALIASES = {
    "Internet": ("internet", "network", "webbrowser", "browser", "email",
                 "chat", "instantmessaging", "communication", "social"),
    "Graphics": ("graphics", "2dgraphics", "3dgraphics", "photography",
                 "rastergraphics", "vectorgraphics", "imageprocessing"),
    "Office": ("office", "wordprocessor", "spreadsheet", "presentation",
               "productivity", "finance", "publishing"),
    "Development": ("development", "ide", "debugger", "programming",
                    "texteditor", "revisioncontrol", "building"),
    "Games": ("game", "games", "actiongame", "arcadegame", "boardgame",
              "cardgame", "logicgame", "puzzlegame", "roleplaying",
              "simulation", "strategygame"),
    "Multimedia": ("audiovideo", "multimedia", "audio", "video", "music",
                   "player", "recorder", "midi", "audiovideoediting"),
    "Education": ("education", "teaching", "learning", "languages"),
    "Science": ("science", "math", "physics", "chemistry", "biology",
                "astronomy", "geography"),
    "Utilities": ("utility", "utilities", "accessories", "archiving",
                  "compression", "calculator", "filemanager", "filetools"),
    "System": ("system", "settings", "monitor", "filesystem",
               "security", "hardware"),
}
_LOOKUP = {alias: group for group, aliases in _ALIASES.items() for alias in aliases}


def category_for(row):
    """Map an actual provider category, using Other for missing/unknown."""
    if not isinstance(row, dict):
        return "Other"
    value = row.get("category", "")
    if not isinstance(value, str):
        return "Other"
    # Existing DEB/RPM browse rows used distro names as a source label.
    if value.strip().casefold() in ("debian 13", "fedora 44"):
        return "Other"
    for token in re.split(r"[,;/|]+", value[:140]):
        key = re.sub(r"[\s_-]+", "", token).casefold()
        if key in _LOOKUP:
            return _LOOKUP[key]
    return "Other"


def categories_for(rows):
    found = {category_for(row) for row in rows}
    return ["All"] + [x for x in CATEGORY_ORDER if x in found]


def filtered_rows(rows, selected):
    if selected == "All":
        return list(rows)
    if selected not in CATEGORY_ORDER:
        return []
    return [row for row in rows if category_for(row) == selected]


def featured_rows(rows, source, query="", limit=6):
    """Only live Flatpak popular browsing is featured, never search or DEB/RPM."""
    if source != "Flatpak" or str(query).strip() or limit <= 0:
        return []
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or row.get("source", "Flatpak") != "Flatpak":
            continue
        key = row.get("providerKey")
        if not isinstance(key, str) or not key.startswith("flatpak:") or key in seen:
            continue
        seen.add(key)
        result.append(row)
        if len(result) >= min(6, limit):
            break
    return result
