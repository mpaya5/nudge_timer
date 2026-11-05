"""Install Nudge for the current user on macOS, Windows or Linux.

Nothing here needs an administrator password: everything goes into the user's own
folders. Only the standard library is used, so the installer runs on a fresh Python.

    macOS    ~/Applications/Nudge.app          (find it in Launchpad or Spotlight)
    Windows  Start menu > Nudge                (a shortcut)
    Linux    the applications menu > Nudge     (a .desktop launcher)

The program itself is copied to a per-user folder, together with the reminders
(`data/`), which are never deleted by an update.
"""

import os
import platform
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from nudge import icon

APP_NAME = "Nudge"
APP_ITEMS = ("main.py", "nudge", "README.md")
NEEDED_PYTHON = (3, 8)
DOWNLOAD_PAGE = "https://www.python.org/downloads/"


class InstallError(Exception):
    """Something stopped the install. The message is written for a non-technical reader."""


@dataclass
class Plan:
    system: str
    app_dir: Path
    launchers: list = field(default_factory=list)

    @property
    def icons_dir(self):
        return self.app_dir / "icons"

    @property
    def main_py(self):
        return self.app_dir / "main.py"


def current_system():
    name = platform.system()
    return name if name in ("Darwin", "Windows") else "Linux"


def make_plan(system=None, home=None, env=None):
    """Where everything goes for this system. Pure: touches nothing."""
    system = system or current_system()
    home = Path(home) if home is not None else Path.home()
    env = os.environ if env is None else env
    if system == "Darwin":
        return Plan(
            system,
            home / "Library" / "Application Support" / APP_NAME,
            [home / "Applications" / f"{APP_NAME}.app"],
        )
    if system == "Windows":
        local = Path(env.get("LOCALAPPDATA") or home / "AppData" / "Local")
        roaming = Path(env.get("APPDATA") or home / "AppData" / "Roaming")
        menu = roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        return Plan(system, local / APP_NAME, [menu / f"{APP_NAME}.lnk"])
    share = Path(env.get("XDG_DATA_HOME") or home / ".local" / "share")
    return Plan(system, share / "nudge", [share / "applications" / "nudge.desktop"])


# --- is this computer ready? -------------------------------------------------

def tk_help(system):
    if system == "Linux":
        return (
            "Nudge needs the Tk window library, which is not installed. Install it with one of:\n"
            "    Ubuntu / Debian / Mint:  sudo apt install python3-tk\n"
            "    Fedora:                  sudo dnf install python3-tkinter\n"
            "    Arch / Manjaro:          sudo pacman -S tk\n"
            "then run this installer again."
        )
    return (
        "This Python does not include the window library Nudge needs.\n"
        f"Please install the free Python from {DOWNLOAD_PAGE}\n"
        "(the normal installer has everything included), then run this installer again."
    )


def python_problem(system=None):
    """Why this Python cannot run Nudge, in plain words, or None when all is well."""
    system = system or current_system()
    if sys.version_info < NEEDED_PYTHON:
        return (
            "This Python is too old for Nudge.\n"
            f"Please install the free Python from {DOWNLOAD_PAGE} and run this installer again."
        )
    try:
        import tkinter
    except ImportError:
        return tk_help(system)
    if tkinter.TkVersion < 8.6:
        return (
            "The window library on this Python is too old and would show an empty window.\n"
            f"Please install the free Python from {DOWNLOAD_PAGE} and run this installer again."
        )
    return None


# --- copying the program ----------------------------------------------------

def _copy_program(source, app_dir, log):
    app_dir.mkdir(parents=True, exist_ok=True)
    skip = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
    for item in APP_ITEMS:
        origin, target = source / item, app_dir / item
        if not origin.exists():
            raise InstallError(f"The installer is missing '{item}'. Please download Nudge again.")
        if origin.is_dir():
            if target.exists():
                shutil.rmtree(target)  # never leave files from an older version behind
            shutil.copytree(origin, target, ignore=skip)
        else:
            shutil.copy2(origin, target)
    log("  Copied the program")


def _bring_over_reminders(source, app_dir, log):
    """If Nudge was used straight from the download folder, keep those reminders."""
    old, new = source / "data", app_dir / "data"
    if old.is_dir() and not new.exists():
        shutil.copytree(old, new, ignore=shutil.ignore_patterns("*.lock", "*.tmp", "nudge-demo-*"))
        log("  Kept the reminders you already had")


# --- one launcher per system ------------------------------------------------

def _write_icons(plan):
    plan.icons_dir.mkdir(parents=True, exist_ok=True)
    cache = {}

    def png_for(size):
        if size not in cache:
            cache[size] = icon.render_png(size)
        return cache[size]

    (plan.icons_dir / "nudge.png").write_bytes(png_for(256))
    if plan.system == "Darwin":
        (plan.icons_dir / "nudge.icns").write_bytes(icon.build_icns(png_for))
    elif plan.system == "Windows":
        (plan.icons_dir / "nudge.ico").write_bytes(icon.build_ico(png_for))


def _mac_app(plan, python):
    app = plan.launchers[0]
    if app.exists():
        shutil.rmtree(app)
    contents = app / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    (contents / "Resources").mkdir()
    script = contents / "MacOS" / APP_NAME
    script.write_text(
        "#!/bin/bash\n"
        f"cd {shlex.quote(str(plan.app_dir))} || exit 1\n"
        f"exec {shlex.quote(str(python))} {shlex.quote(str(plan.main_py))} \"$@\"\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    shutil.copy2(plan.icons_dir / "nudge.icns", contents / "Resources" / f"{APP_NAME}.icns")
    with open(contents / "Info.plist", "wb") as handle:
        plistlib.dump(
            {
                "CFBundleName": APP_NAME,
                "CFBundleDisplayName": APP_NAME,
                "CFBundleIdentifier": "app.nudge.reminders",
                "CFBundleExecutable": APP_NAME,
                "CFBundleIconFile": APP_NAME,
                "CFBundlePackageType": "APPL",
                "CFBundleShortVersionString": "1.0",
                "CFBundleVersion": "1",
                "LSMinimumSystemVersion": "10.13",
                "NSHighResolutionCapable": True,
            },
            handle,
        )


def _ps_quote(text):
    return "'" + str(text).replace("'", "''") + "'"


def _windows_shortcut(plan, python, run):
    link = plan.launchers[0]
    link.parent.mkdir(parents=True, exist_ok=True)
    python = Path(python)
    windowless = python.with_name("pythonw.exe")  # runs without a black console window
    target = windowless if windowless.exists() else python
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut(%s); "
        "$s.TargetPath = %s; $s.Arguments = %s; $s.WorkingDirectory = %s; "
        "$s.IconLocation = %s; $s.Description = 'Gentle break reminders'; $s.Save()"
    ) % (
        _ps_quote(link),
        _ps_quote(target),
        _ps_quote('"' + str(plan.main_py) + '"'),
        _ps_quote(plan.app_dir),
        _ps_quote(plan.icons_dir / "nudge.ico"),
    )
    if run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]):
        return
    # PowerShell is unavailable or blocked: a plain launcher file still works.
    fallback = link.with_suffix(".cmd")
    # Bytes, not text: text mode on Windows would turn "\r\n" into "\r\r\n".
    fallback.write_bytes(
        (
            "@echo off\r\n"
            f'cd /d "{plan.app_dir}"\r\n'
            f'start "" "{target}" "{plan.main_py}"\r\n'
        ).encode("utf-8")
    )
    plan.launchers.append(fallback)


def _desktop_quote(text):
    text = re.sub(r'(["`$\\])', r"\\\1", str(text))
    return '"' + text.replace("\\", "\\\\").replace("%", "%%") + '"'


def _linux_launcher(plan, python, run):
    entry = plan.launchers[0]
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        "Comment=Gentle break reminders\n"
        f"Exec={_desktop_quote(python)} {_desktop_quote(plan.main_py)}\n"
        f"Path={plan.app_dir}\n"
        f"Icon={plan.icons_dir / 'nudge.png'}\n"
        "Terminal=false\n"
        "Categories=Utility;\n",
        encoding="utf-8",
    )
    entry.chmod(0o755)
    run(["update-desktop-database", str(entry.parent)])  # optional; harmless when missing


def _quiet_run(args):
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


# --- public entry points ----------------------------------------------------

def install(source, python=None, system=None, home=None, env=None, run=None, log=print):
    """Copy Nudge into place and add it to the system's app list. Returns the Plan."""
    plan = make_plan(system, home, env)
    source = Path(source).resolve()
    python = python or sys.executable
    run = run or _quiet_run
    if source == plan.app_dir.resolve():
        raise InstallError(
            "This is already the installed copy. Run the installer from the downloaded folder instead."
        )
    if not (source / "main.py").is_file() or not (source / "nudge").is_dir():
        raise InstallError("The installer must stay inside the Nudge folder. Please download Nudge again.")
    log(f"Installing {APP_NAME}...")
    try:
        _copy_program(source, plan.app_dir, log)
        _bring_over_reminders(source, plan.app_dir, log)
        _write_icons(plan)
        if plan.system == "Darwin":
            _mac_app(plan, python)
        elif plan.system == "Windows":
            _windows_shortcut(plan, python, run)
        else:
            _linux_launcher(plan, python, run)
    except OSError as problem:
        raise InstallError(
            f"Nudge could not be installed ({problem.strerror or problem}). "
            "Check that your disk has free space and try again."
        )
    log("  Added Nudge to your apps")
    return plan


def uninstall(system=None, home=None, env=None, remove_data=False, log=print):
    """Remove Nudge. Reminders are kept unless `remove_data` is set. Returns the Plan."""
    plan = make_plan(system, home, env)
    log(f"Removing {APP_NAME}...")
    launchers = list(plan.launchers)
    if plan.system == "Windows":
        launchers.append(plan.launchers[0].with_suffix(".cmd"))
    for launcher in launchers:
        if launcher.is_dir():
            shutil.rmtree(launcher, ignore_errors=True)
        elif launcher.exists():
            launcher.unlink()
    if plan.app_dir.exists():
        if remove_data:
            shutil.rmtree(plan.app_dir, ignore_errors=True)
        else:
            for item in APP_ITEMS + ("icons",):
                target = plan.app_dir / item
                if target.is_dir():
                    shutil.rmtree(target, ignore_errors=True)
                elif target.exists():
                    target.unlink()
            try:
                plan.app_dir.rmdir()  # only works when no reminders are left behind
            except OSError:
                pass
    log("  Removed the program")
    if not remove_data and (plan.app_dir / "data").exists():
        log(f"  Your reminders were kept in: {plan.app_dir / 'data'}")
    return plan


def open_installed(plan, python=None):
    """Start the freshly installed app. Failing to do so is not an error."""
    python = python or sys.executable
    try:
        if plan.system == "Darwin":
            subprocess.Popen(["open", str(plan.launchers[0])])
        elif plan.system == "Windows":
            os.startfile(str(plan.launchers[0]))  # noqa: only exists on Windows
        else:
            subprocess.Popen(
                [python, str(plan.main_py)],
                cwd=str(plan.app_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        return True
    except (OSError, AttributeError):
        return False


def where_to_find_it(plan):
    if plan.system == "Darwin":
        return "Open it from Launchpad, or press Command+Space and type Nudge."
    if plan.system == "Windows":
        return "Open it from the Start menu: press the Windows key and type Nudge."
    return "Open it from your applications menu: search for Nudge."
