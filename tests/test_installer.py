"""The installer: where things go, what gets written, updating, removing, and the icon.

Everything runs against temporary folders, never the real ones. Windows and Linux
installs are checked by building their files here; the commands that only exist on
those systems (PowerShell, os.startfile) are replaced by recorders.
"""

import os
import plistlib
import shutil
import struct
import subprocess
import sys
import tempfile
import tkinter as tk
import unittest
import zlib
from pathlib import Path
from unittest import mock

from helpers import HAS_TK, GuiCase, needs_tk

from nudge import icon, installer

ROOT = Path(__file__).resolve().parent.parent


def quiet(_message):
    pass


class FakeDownload(unittest.TestCase):
    """A temporary copy of the project, a temporary home folder, and a recorder for system commands."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.home = base / "home"
        self.home.mkdir()
        self.source = base / "Downloads" / "Nudge"
        shutil.copytree(
            ROOT, self.source,
            ignore=shutil.ignore_patterns("data", "__pycache__", ".git", "*.pyc", ".coverage"),
        )
        self.env = {}
        self.commands = []
        self.run_ok = True

    def run_command(self, args):
        self.commands.append(args)
        return self.run_ok

    def install(self, system, **kwargs):
        python = kwargs.pop("python", "/usr/bin/fake python3")
        return installer.install(
            self.source, python=python, system=system, home=self.home,
            env=self.env, run=self.run_command, log=quiet, **kwargs,
        )

    def uninstall(self, system, **kwargs):
        return installer.uninstall(system=system, home=self.home, env=self.env, log=quiet, **kwargs)


class WhereThingsGoTests(FakeDownload):
    def test_mac_uses_the_users_applications_folder(self):
        plan = installer.make_plan("Darwin", self.home, self.env)
        self.assertEqual(plan.launchers, [self.home / "Applications" / "Nudge.app"])
        self.assertEqual(plan.app_dir, self.home / "Library" / "Application Support" / "Nudge")

    def test_windows_uses_the_start_menu_and_local_app_data(self):
        self.env = {"LOCALAPPDATA": str(self.home / "L"), "APPDATA": str(self.home / "R")}
        plan = installer.make_plan("Windows", self.home, self.env)
        self.assertEqual(plan.app_dir, self.home / "L" / "Nudge")
        menu = self.home / "R" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        self.assertEqual(plan.launchers, [menu / "Nudge.lnk"])

    def test_windows_without_the_usual_variables_still_has_sensible_folders(self):
        plan = installer.make_plan("Windows", self.home, {})
        self.assertEqual(plan.app_dir, self.home / "AppData" / "Local" / "Nudge")

    def test_linux_follows_the_xdg_folders_and_falls_back_to_local_share(self):
        plan = installer.make_plan("Linux", self.home, {})
        self.assertEqual(plan.app_dir, self.home / ".local" / "share" / "nudge")
        self.assertEqual(plan.launchers, [self.home / ".local" / "share" / "applications" / "nudge.desktop"])
        custom = installer.make_plan("Linux", self.home, {"XDG_DATA_HOME": str(self.home / "xdg")})
        self.assertEqual(custom.app_dir, self.home / "xdg" / "nudge")

    def test_nothing_needs_an_administrator(self):
        for system in ("Darwin", "Windows", "Linux"):
            plan = installer.make_plan(system, self.home, {})
            for path in [plan.app_dir] + plan.launchers:
                self.assertTrue(str(path).startswith(str(self.home)), f"{system}: {path}")

    def test_unknown_systems_are_treated_like_linux(self):
        with mock.patch("platform.system", return_value="FreeBSD"):
            self.assertEqual(installer.current_system(), "Linux")
        for name in ("Darwin", "Windows"):
            with mock.patch("platform.system", return_value=name):
                self.assertEqual(installer.current_system(), name)


class IsThisComputerReadyTests(unittest.TestCase):
    def test_a_ready_computer_has_no_problem(self):
        if not HAS_TK:
            self.skipTest("Tk cannot start here")
        fake = mock.Mock(TkVersion=9.1)
        with mock.patch.dict(sys.modules, {"tkinter": fake}):
            self.assertIsNone(installer.python_problem("Darwin"))

    def test_missing_tk_gets_help_that_fits_the_system(self):
        with mock.patch.dict(sys.modules, {"tkinter": None}):
            linux = installer.python_problem("Linux")
            mac = installer.python_problem("Darwin")
            windows = installer.python_problem("Windows")
        self.assertIn("apt install python3-tk", linux)
        self.assertIn("dnf install python3-tkinter", linux)
        self.assertIn("pacman -S tk", linux)
        for text in (mac, windows):
            self.assertIn("python.org/downloads", text)
            self.assertNotIn("sudo", text)

    def test_an_old_tk_is_refused_because_it_shows_an_empty_window(self):
        with mock.patch.dict(sys.modules, {"tkinter": mock.Mock(TkVersion=8.5)}):
            problem = installer.python_problem("Darwin")
        self.assertIn("empty window", problem)
        self.assertIn("python.org/downloads", problem)

    def test_an_old_python_is_refused(self):
        with mock.patch.object(sys, "version_info", (3, 6, 0)):
            self.assertIn("too old", installer.python_problem("Darwin"))

    def test_no_message_mentions_commands_a_beginner_cannot_run_on_mac_or_windows(self):
        for system in ("Darwin", "Windows"):
            self.assertNotIn("brew", installer.tk_help(system))
            self.assertNotIn("pip", installer.tk_help(system))


class RefusesOldTkTests(unittest.TestCase):
    """Installing under a Tk too old to draw windows must stop with advice, never half-install."""

    def test_the_command_line_installer_stops_before_touching_anything(self):
        with tempfile.TemporaryDirectory() as folder:
            fake_tk = Path(folder) / "fake"
            fake_tk.mkdir()
            (fake_tk / "tkinter.py").write_text("TkVersion = 8.5\n")
            env = dict(os.environ, HOME=folder, PYTHONPATH=str(fake_tk))
            out = subprocess.run([sys.executable, str(ROOT / "install.py"), "--no-launch"],
                                 capture_output=True, text=True, env=env, timeout=60)
            self.assertEqual(out.returncode, 1)
            self.assertIn("python.org/downloads", out.stderr)
            plan = installer.make_plan("Darwin", Path(folder), {})
            for place in [plan.app_dir] + plan.launchers:
                self.assertFalse(place.exists(), f"{place} must not be created")
            self.assertFalse((Path(folder) / "Applications").exists())


class MacInstallTests(FakeDownload):
    def test_builds_a_real_app_bundle(self):
        plan = self.install("Darwin")
        app = plan.launchers[0]
        self.assertTrue((app / "Contents" / "Info.plist").is_file())
        info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
        self.assertEqual(info["CFBundleName"], "Nudge")
        self.assertEqual(info["CFBundleExecutable"], "Nudge")
        self.assertEqual(info["CFBundlePackageType"], "APPL")
        self.assertTrue((app / "Contents" / "Resources" / "Nudge.icns").is_file())
        script = app / "Contents" / "MacOS" / "Nudge"
        self.assertTrue(os.access(script, os.X_OK), "the launcher must be executable")

    def test_the_launcher_runs_the_installed_copy_with_the_chosen_python(self):
        plan = self.install("Darwin", python="/opt/py thon/bin/python3")
        text = (plan.launchers[0] / "Contents" / "MacOS" / "Nudge").read_text()
        self.assertIn("'/opt/py thon/bin/python3'", text, "paths with spaces must be quoted")
        self.assertIn(shlex_quote(str(plan.main_py)), text)
        self.assertIn(shlex_quote(str(plan.app_dir)), text)

    def test_the_launcher_script_is_valid_shell(self):
        plan = self.install("Darwin", python="/opt/it's here/python3")
        script = plan.launchers[0] / "Contents" / "MacOS" / "Nudge"
        checked = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_the_icon_file_is_a_real_icns(self):
        plan = self.install("Darwin")
        data = (plan.launchers[0] / "Contents" / "Resources" / "Nudge.icns").read_bytes()
        self.assertEqual(data[:4], b"icns")
        self.assertEqual(struct.unpack(">I", data[4:8])[0], len(data))

    def test_installing_twice_replaces_the_app_without_leftovers(self):
        plan = self.install("Darwin")
        (plan.launchers[0] / "Contents" / "old-file").write_text("x")
        self.install("Darwin")
        self.assertFalse((plan.launchers[0] / "Contents" / "old-file").exists())


def shlex_quote(text):
    import shlex
    return shlex.quote(text)


class WindowsInstallTests(FakeDownload):
    def setUp(self):
        super().setUp()
        self.env = {"LOCALAPPDATA": str(self.home / "L"), "APPDATA": str(self.home / "R")}

    def test_creates_a_start_menu_shortcut_through_powershell(self):
        plan = self.install("Windows", python="C:\\Python313\\python.exe")
        self.assertEqual(len(self.commands), 1)
        command = self.commands[0]
        self.assertEqual(command[0], "powershell")
        script = command[-1]
        self.assertIn("CreateShortcut", script)
        self.assertIn(str(plan.launchers[0]), script)
        self.assertIn('"' + str(plan.main_py) + '"', script, "the program path is quoted for spaces")
        self.assertIn("nudge.ico", script)
        self.assertIn(str(plan.app_dir), script)

    def test_prefers_the_windowless_python_so_no_black_console_appears(self):
        python = self.home / "py" / "python.exe"
        python.parent.mkdir()
        python.write_text("")
        (python.parent / "pythonw.exe").write_text("")
        self.install("Windows", python=str(python))
        self.assertIn(str(python.parent / "pythonw.exe"), self.commands[0][-1])

    def test_uses_python_itself_when_there_is_no_windowless_one(self):
        self.install("Windows", python="C:\\Nowhere\\python.exe")
        self.assertIn("C:\\Nowhere\\python.exe", self.commands[0][-1])

    def test_quotes_in_paths_cannot_break_the_powershell_script(self):
        self.install("Windows", python="C:\\O'Brien\\python.exe")
        self.assertIn("O''Brien", self.commands[0][-1])

    def test_falls_back_to_a_plain_launcher_if_powershell_is_blocked(self):
        self.run_ok = False
        plan = self.install("Windows", python="C:\\Python313\\python.exe")
        cmd = plan.launchers[0].with_suffix(".cmd")
        self.assertTrue(cmd.is_file())
        raw = cmd.read_bytes()
        self.assertIn(b"\r\n", raw)
        self.assertNotIn(b"\r\r", raw, "no doubled carriage returns")
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""), "every line ends the Windows way")
        text = raw.decode("utf-8")
        self.assertIn(str(plan.main_py), text)
        self.assertIn(cmd, plan.launchers)

    def test_writes_a_real_ico_file(self):
        plan = self.install("Windows")
        data = (plan.icons_dir / "nudge.ico").read_bytes()
        reserved, kind, count = struct.unpack("<HHH", data[:6])
        self.assertEqual((reserved, kind, count), (0, 1, len(icon.ICO_SIZES)))
        length, offset = struct.unpack("<II", data[6 + 8:6 + 16])
        self.assertEqual(offset + length, offset + len(data[offset:offset + length]))
        self.assertEqual(data[offset:offset + 8], b"\x89PNG\r\n\x1a\n")

    def test_uninstall_also_removes_the_fallback_launcher(self):
        self.run_ok = False
        plan = self.install("Windows")
        self.uninstall("Windows")
        for launcher in plan.launchers:
            self.assertFalse(launcher.exists())


class LinuxInstallTests(FakeDownload):
    def entry(self, plan):
        return plan.launchers[0].read_text(encoding="utf-8")

    def test_creates_a_menu_entry(self):
        plan = self.install("Linux", python="/usr/bin/python3")
        text = self.entry(plan)
        self.assertTrue(text.startswith("[Desktop Entry]\n"))
        for line in ("Type=Application", "Name=Nudge", "Terminal=false", "Categories=Utility;"):
            self.assertIn(line, text.splitlines())
        self.assertIn(f"Icon={plan.icons_dir / 'nudge.png'}", text)
        self.assertTrue((plan.icons_dir / "nudge.png").is_file())
        self.assertTrue(os.access(plan.launchers[0], os.X_OK))

    def test_the_command_is_quoted_so_spaces_do_not_split_it(self):
        plan = self.install("Linux", python="/home/ana maria/py/bin/python3")
        exec_line = [row for row in self.entry(plan).splitlines() if row.startswith("Exec=")][0]
        self.assertTrue(exec_line.startswith('Exec="/home/ana maria/py/bin/python3" "'), exec_line)
        self.assertTrue(exec_line.endswith('main.py"'), exec_line)

    def test_special_characters_are_escaped_in_the_command(self):
        self.assertEqual(installer._desktop_quote('a"b'), '"a\\\\"b"')
        self.assertEqual(installer._desktop_quote("100%"), '"100%%"')
        self.assertEqual(installer._desktop_quote("a$b"), '"a\\\\$b"')

    def test_asks_the_desktop_to_refresh_its_menu_but_does_not_need_it(self):
        self.run_ok = False
        plan = self.install("Linux")
        self.assertEqual(self.commands[0][0], "update-desktop-database")
        self.assertTrue(plan.launchers[0].is_file())

    def test_works_when_the_applications_folder_does_not_exist_yet(self):
        plan = installer.make_plan("Linux", self.home, {})
        self.assertFalse(plan.launchers[0].parent.exists())
        self.install("Linux")
        self.assertTrue(plan.launchers[0].is_file())


class WhatGetsCopiedTests(FakeDownload):
    def test_the_program_and_its_pictures_are_copied_but_not_tests_or_caches(self):
        plan = self.install("Linux")
        for name in ("main.py", "README.md", "nudge/app.py", "nudge/sound.py", "nudge/installer.py",
                     "nudge/assets/icon-256.png"):
            self.assertTrue((plan.app_dir / name).is_file(), name)
        self.assertFalse((plan.app_dir / "tests").exists())
        self.assertFalse(list(plan.app_dir.rglob("__pycache__")))

    def test_the_installed_copy_starts(self):
        plan = self.install("Linux")
        out = subprocess.run([sys.executable, str(plan.main_py), "--help"], capture_output=True, text=True,
                             cwd=str(self.home), timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("--demo", out.stdout)

    def test_an_update_replaces_old_program_files_but_never_touches_reminders(self):
        plan = self.install("Linux")
        (plan.app_dir / "nudge" / "left_over.py").write_text("old")
        (plan.app_dir / "data").mkdir(exist_ok=True)
        (plan.app_dir / "data" / "state.json").write_text('{"mine": true}')
        (plan.app_dir / "data" / "sounds").mkdir()
        (plan.app_dir / "data" / "sounds" / "bell.wav").write_bytes(b"x")
        (self.source / "main.py").write_text((self.source / "main.py").read_text() + "\n# newer\n")
        self.install("Linux")
        self.assertFalse((plan.app_dir / "nudge" / "left_over.py").exists())
        self.assertIn("# newer", (plan.app_dir / "main.py").read_text())
        self.assertEqual((plan.app_dir / "data" / "state.json").read_text(), '{"mine": true}')
        self.assertEqual((plan.app_dir / "data" / "sounds" / "bell.wav").read_bytes(), b"x")

    def test_reminders_used_before_installing_are_carried_over_once(self):
        (self.source / "data" / "sounds").mkdir(parents=True)
        (self.source / "data" / "state.json").write_text('{"old": 1}')
        (self.source / "data" / "sounds" / "bell.wav").write_bytes(b"w")
        (self.source / "data" / "nudge.lock").write_text("123")
        plan = self.install("Linux")
        self.assertEqual((plan.app_dir / "data" / "state.json").read_text(), '{"old": 1}')
        self.assertTrue((plan.app_dir / "data" / "sounds" / "bell.wav").is_file(), "added sounds come along")
        self.assertFalse((plan.app_dir / "data" / "nudge.lock").exists(), "a stale lock must not come along")
        (self.source / "data" / "state.json").write_text('{"old": 2}')
        self.install("Linux")
        self.assertEqual((plan.app_dir / "data" / "state.json").read_text(), '{"old": 1}',
                         "the installed copy's reminders win after the first install")

    def test_a_fresh_install_without_old_data_starts_empty(self):
        plan = self.install("Linux")
        self.assertFalse((plan.app_dir / "data").exists())


class RefusalTests(FakeDownload):
    def test_cannot_install_the_installed_copy_over_itself(self):
        plan = self.install("Linux")
        with self.assertRaises(installer.InstallError) as caught:
            installer.install(plan.app_dir, system="Linux", home=self.home, env=self.env,
                              run=self.run_command, log=quiet)
        self.assertIn("already the installed copy", str(caught.exception))

    def test_a_folder_that_is_not_nudge_is_refused(self):
        empty = Path(self._tmp.name) / "elsewhere"
        empty.mkdir()
        with self.assertRaises(installer.InstallError):
            installer.install(empty, system="Linux", home=self.home, env=self.env, run=self.run_command, log=quiet)
        self.assertFalse(installer.make_plan("Linux", self.home, self.env).app_dir.exists())

    def test_a_missing_piece_is_reported_in_plain_words(self):
        (self.source / "README.md").unlink()
        with self.assertRaises(installer.InstallError) as caught:
            self.install("Linux")
        self.assertIn("README.md", str(caught.exception))
        self.assertIn("download Nudge again", str(caught.exception))

    def test_a_disk_problem_becomes_a_friendly_message(self):
        with mock.patch("shutil.copytree", side_effect=OSError(28, "No space left on device")):
            with self.assertRaises(installer.InstallError) as caught:
                self.install("Linux")
        self.assertIn("No space left", str(caught.exception))
        self.assertIn("try again", str(caught.exception))


class UninstallTests(FakeDownload):
    def test_removes_the_launcher_and_the_program_but_keeps_reminders(self):
        for system in ("Darwin", "Linux"):
            with self.subTest(system=system):
                plan = self.install(system)
                (plan.app_dir / "data").mkdir(exist_ok=True)
                (plan.app_dir / "data" / "state.json").write_text("keep me")
                self.uninstall(system)
                for launcher in plan.launchers:
                    self.assertFalse(launcher.exists())
                self.assertFalse((plan.app_dir / "main.py").exists())
                self.assertFalse((plan.app_dir / "nudge").exists())
                self.assertEqual((plan.app_dir / "data" / "state.json").read_text(), "keep me")

    def test_can_remove_everything_including_reminders(self):
        plan = self.install("Linux")
        (plan.app_dir / "data").mkdir(exist_ok=True)
        (plan.app_dir / "data" / "state.json").write_text("x")
        self.uninstall("Linux", remove_data=True)
        self.assertFalse(plan.app_dir.exists())

    def test_leaves_no_empty_folder_when_there_were_no_reminders(self):
        plan = self.install("Linux")
        self.uninstall("Linux")
        self.assertFalse(plan.app_dir.exists())

    def test_tells_the_person_where_their_reminders_are(self):
        plan = self.install("Linux")
        (plan.app_dir / "data").mkdir(exist_ok=True)
        messages = []
        installer.uninstall(system="Linux", home=self.home, env=self.env, log=messages.append)
        self.assertTrue(any(str(plan.app_dir / "data") in line for line in messages), messages)

    def test_uninstalling_something_that_is_not_installed_is_harmless(self):
        for system in ("Darwin", "Windows", "Linux"):
            self.uninstall(system)
            self.uninstall(system)

    def test_reinstalling_after_uninstalling_brings_the_reminders_back(self):
        plan = self.install("Linux")
        (plan.app_dir / "data").mkdir(exist_ok=True)
        (plan.app_dir / "data" / "state.json").write_text("mine")
        self.uninstall("Linux")
        self.install("Linux")
        self.assertEqual((plan.app_dir / "data" / "state.json").read_text(), "mine")
        self.assertTrue(plan.launchers[0].exists())


class OpeningTests(FakeDownload):
    def test_mac_opens_the_app_bundle(self):
        plan = installer.make_plan("Darwin", self.home, {})
        with mock.patch("subprocess.Popen") as popen:
            self.assertTrue(installer.open_installed(plan))
        self.assertEqual(popen.call_args[0][0], ["open", str(plan.launchers[0])])

    def test_windows_opens_the_shortcut(self):
        plan = installer.make_plan("Windows", self.home, {})
        with mock.patch.object(os, "startfile", create=True) as start:
            self.assertTrue(installer.open_installed(plan))
        start.assert_called_once_with(str(plan.launchers[0]))

    def test_linux_starts_the_program_detached_from_the_installer(self):
        plan = installer.make_plan("Linux", self.home, {})
        with mock.patch("subprocess.Popen") as popen:
            self.assertTrue(installer.open_installed(plan, python="/usr/bin/python3"))
        self.assertEqual(popen.call_args[0][0], ["/usr/bin/python3", str(plan.main_py)])
        self.assertTrue(popen.call_args[1]["start_new_session"])

    def test_failing_to_open_is_not_an_error(self):
        for system in ("Darwin", "Windows", "Linux"):
            plan = installer.make_plan(system, self.home, {})
            with mock.patch("subprocess.Popen", side_effect=OSError("nope")), \
                    mock.patch.object(os, "startfile", create=True, side_effect=OSError("nope")):
                self.assertFalse(installer.open_installed(plan))

    def test_each_system_is_told_where_to_find_the_app(self):
        texts = {
            s: installer.where_to_find_it(installer.make_plan(s, self.home, {}))
            for s in ("Darwin", "Windows", "Linux")
        }
        self.assertIn("Launchpad", texts["Darwin"])
        self.assertIn("Start menu", texts["Windows"])
        self.assertIn("applications menu", texts["Linux"])


class IconTests(unittest.TestCase):
    def decode(self, data):
        """Read a PNG back into rows of RGBA values, checking every checksum on the way."""
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        position, pieces, header = 8, [], None
        while position < len(data):
            length, kind = struct.unpack(">I4s", data[position:position + 8])
            body = data[position + 8:position + 8 + length]
            crc = struct.unpack(">I", data[position + 8 + length:position + 12 + length])[0]
            self.assertEqual(crc, zlib.crc32(kind + body) & 0xFFFFFFFF, kind)
            if kind == b"IHDR":
                header = struct.unpack(">IIBBBBB", body)
            if kind == b"IDAT":
                pieces.append(body)
            position += 12 + length
        width, height, depth, color_type = header[:4]
        self.assertEqual((depth, color_type), (8, 6))
        raw = zlib.decompress(b"".join(pieces))
        stride = width * 4 + 1
        rows = []
        for y in range(height):
            self.assertEqual(raw[y * stride], 0)
            line = raw[y * stride + 1:(y + 1) * stride]
            rows.append([tuple(line[i:i + 4]) for i in range(0, len(line), 4)])
        return rows

    def test_the_picture_is_a_valid_png_of_the_requested_size(self):
        for size in (16, 32, 64, 128):
            with self.subTest(size=size):
                data = icon.render_png(size)
                self.assertEqual(icon.png_size(data), (size, size))
                rows = self.decode(data)
                self.assertEqual((len(rows), len(rows[0])), (size, size))

    def test_the_corners_are_see_through_and_the_middle_is_solid(self):
        rows = self.decode(icon.render_png(128))
        self.assertEqual(rows[0][0][3], 0)
        self.assertEqual(rows[127][127][3], 0)
        self.assertEqual(rows[64][64][3], 255)
        self.assertEqual(rows[20][64][3], 255, "the top of the square is filled")

    def test_the_four_dots_use_the_colors_of_the_four_built_in_reminders(self):
        from nudge.models import KINDS
        rows = self.decode(icon.render_png(256))
        centre, ring = 128, int(0.285 * 256)
        spots = {"water": (centre, centre - ring), "walk": (centre + ring, centre),
                 "rest": (centre, centre + ring), "stretch": (centre - ring, centre)}
        for kind, (x, y) in spots.items():
            expected = tuple(int(KINDS[kind]["color"][i:i + 2], 16) for i in (1, 3, 5))
            self.assertEqual(rows[y][x][:3], expected, kind)

    def test_edges_are_smooth_not_jagged(self):
        rows = self.decode(icon.render_png(64))
        partial = {px[3] for row in rows for px in row if 0 < px[3] < 255}
        self.assertGreater(len(partial), 5)

    def test_tiny_sizes_are_rejected(self):
        with self.assertRaises(ValueError):
            icon.render_png(4)

    def test_png_size_rejects_other_data(self):
        with self.assertRaises(ValueError):
            icon.png_size(b"GIF89a" + b"0" * 30)

    def test_the_icns_holds_every_size_macos_asks_for(self):
        data = icon.build_icns(lambda size: icon.render_png(size) if size <= 64 else b"\x89PNG\r\n\x1a\n" + b"0" * size)
        self.assertEqual(data[:4], b"icns")
        position, found = 8, []
        while position < len(data):
            code, length = struct.unpack(">4sI", data[position:position + 8])
            found.append(code)
            position += length
        self.assertEqual(position, len(data))
        self.assertEqual(found, [code for code, _ in icon.ICNS_PARTS])

    def test_the_ico_directory_matches_its_images(self):
        data = icon.build_ico(lambda size: b"\x89PNG\r\n\x1a\n" + bytes(size))
        _, _, count = struct.unpack("<HHH", data[:6])
        self.assertEqual(count, len(icon.ICO_SIZES))
        for index, size in enumerate(icon.ICO_SIZES):
            width, height, _c, _r, planes, bits, length, offset = struct.unpack(
                "<BBBBHHII", data[6 + 16 * index:6 + 16 * (index + 1)])
            self.assertEqual(width, size % 256)
            self.assertEqual(data[offset:offset + length], b"\x89PNG\r\n\x1a\n" + bytes(size))

    def test_the_bundled_window_picture_exists_and_is_current(self):
        bundled = (ROOT / "nudge" / "assets" / "icon-256.png").read_bytes()
        self.assertEqual(icon.png_size(bundled), (256, 256))
        self.assertEqual(bundled, icon.render_png(256), "run `python3 -m nudge.icon` after changing the drawing")


@needs_tk
class WindowIconTests(GuiCase):
    def test_the_window_gets_the_nudge_picture(self):
        from nudge.app import set_window_icon
        root = self.new_root()
        if tk.TkVersion < 8.6:
            self.skipTest("Tk 8.5 cannot read PNG pictures; the icon is simply left out there")
        set_window_icon(root)
        self.assertEqual(root._nudge_icon.width(), 256)

    def test_a_missing_picture_is_not_fatal(self):
        from nudge.app import set_window_icon
        root = self.new_root()
        with mock.patch("pathlib.Path.resolve", return_value=Path("/nowhere/nudge/app.py")):
            set_window_icon(root)
        self.assertFalse(hasattr(root, "_nudge_icon"))


class HandoutFilesTests(unittest.TestCase):
    def test_every_installer_script_is_present(self):
        for name in ("install.py", "Install on Mac.command", "Install on Windows.bat", "Install on Linux.sh"):
            self.assertTrue((ROOT / name).is_file(), name)

    def test_the_unix_scripts_are_executable_and_valid_shell(self):
        for name, shell in (("Install on Mac.command", "bash"), ("Install on Linux.sh", "sh")):
            path = ROOT / name
            self.assertTrue(os.access(path, os.X_OK), f"{name} must be executable so double-click works")
            checked = subprocess.run([shell, "-n", str(path)], capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertTrue(path.read_text().startswith("#!"))

    def test_the_windows_script_uses_windows_line_endings(self):
        data = (ROOT / "Install on Windows.bat").read_bytes()
        self.assertIn(b"\r\n", data)
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
        text = data.decode()
        self.assertIn("install.py", text)
        self.assertIn("python.org/downloads", text)

    def test_the_scripts_run_the_installer_and_point_to_python_when_missing(self):
        for name in ("Install on Mac.command", "Install on Linux.sh"):
            text = (ROOT / name).read_text()
            self.assertIn("install.py", text)
        self.assertIn("python.org/downloads", (ROOT / "Install on Mac.command").read_text())
        self.assertIn("python3-tk", (ROOT / "Install on Linux.sh").read_text())

    def test_the_mac_script_looks_for_the_python_org_python_first(self):
        text = (ROOT / "Install on Mac.command").read_text()
        self.assertLess(text.index("Python.framework"), text.index("/opt/homebrew"))

    def test_the_readme_names_every_installer_file_and_where_to_find_the_app(self):
        text = (ROOT / "README.md").read_text()
        for name in ("Install on Mac.command", "Install on Windows.bat", "Install on Linux.sh"):
            self.assertIn(name, text)
            self.assertTrue((ROOT / name).is_file())
        for phrase in ("Launchpad", "Start menu", "applications menu", "--uninstall", "--remove-data"):
            self.assertIn(phrase, text)

    def test_the_readme_describes_the_sound_formats_the_code_really_accepts(self):
        text = (ROOT / "README.md").read_text()
        self.assertIn("Add your own sound", text)
        line = [row for row in text.splitlines() if row.startswith("Sounds you can add:")][0]
        from nudge.sound import MAX_SOUND_BYTES, _EXTENSIONS
        for extension in _EXTENSIONS["Darwin"] + _EXTENSIONS["Linux"]:
            if extension in ("aif", "oga"):
                continue  # spelling variants of AIFF and OGG
            self.assertIn(extension.upper(), line)
        self.assertEqual(MAX_SOUND_BYTES, 5 * 1024 * 1024)
        self.assertIn("5 MB", line)

    def readme_pair(self):
        return {name: (ROOT / name).read_text(encoding="utf-8") for name in ("README.md", "README.es.md")}

    def test_both_readmes_link_to_each_other(self):
        texts = self.readme_pair()
        self.assertIn("(README.es.md)", texts["README.md"])
        self.assertIn("(README.md)", texts["README.es.md"])

    def test_both_readmes_explain_the_same_files_and_commands(self):
        for name, text in self.readme_pair().items():
            for needle in ("Install on Mac.command", "Install on Windows.bat", "Install on Linux.sh",
                           "install.py --uninstall", "--remove-data", "tests/run_all.py",
                           "tests/mutation_check.py", "python.org/downloads", "python3-tk",
                           "%LOCALAPPDATA%", "~/.local/share/nudge", "Application Support/Nudge",
                           "--demo", "Launchpad"):
                self.assertIn(needle, text, f"{name} is missing {needle}")

    def test_every_contents_link_points_to_a_real_heading(self):
        import re
        for name, text in self.readme_pair().items():
            slugs = set()
            for heading in re.findall(r"^#{1,4} (.+)$", text, flags=re.MULTILINE):
                slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
                slugs.add(slug)
            links = re.findall(r"\]\(#([^)]+)\)", text)
            self.assertGreater(len(links), 5, name)
            for link in links:
                self.assertIn(link, slugs, f"{name}: the link #{link} has no matching heading")

    def test_both_readmes_say_what_was_and_was_not_tested(self):
        texts = self.readme_pair()
        for name, needles in (("README.md", ("What has been tested, and what has not", "Not tested", "384 tests")),
                              ("README.es.md", ("Qué se ha probado y qué no", "No probado", "384 pruebas"))):
            for needle in needles:
                self.assertIn(needle, texts[name], name)
        for text in texts.values():
            for system in ("Windows", "Linux"):
                self.assertIn(system, text.split("Not tested" if "Not tested" in text else "No probado")[1])

    def test_the_project_is_mit_licensed_and_the_readmes_say_so(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertTrue(license_text.startswith("MIT License"))
        self.assertIn("Copyright (c) 2026", license_text)
        self.assertIn("Permission is hereby granted, free of charge", license_text)
        self.assertIn('THE SOFTWARE IS PROVIDED "AS IS"', license_text)
        for name, text in self.readme_pair().items():
            self.assertIn("(LICENSE)", text, name)
            self.assertIn("MIT", text, name)

    def test_git_is_told_to_keep_each_scripts_line_endings(self):
        rules = (ROOT / ".gitattributes").read_text()
        self.assertIn("*.bat text eol=crlf", rules)
        self.assertIn("*.sh text eol=lf", rules)
        self.assertIn("*.command text eol=lf", rules)

    def test_the_installer_explains_itself(self):
        out = subprocess.run([sys.executable, str(ROOT / "install.py"), "--help"], capture_output=True, text=True,
                             timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        for word in ("--uninstall", "--remove-data", "--no-launch"):
            self.assertIn(word, out.stdout)


def modern_tk():
    try:
        import tkinter
        return tkinter.TkVersion >= 8.6
    except ImportError:
        return False


@unittest.skipUnless(sys.platform == "darwin" and HAS_TK and modern_tk(), "the full install test needs a Mac with Tk 8.6+")
class EndToEndMacTests(unittest.TestCase):
    """Runs the real install.py as a person would, into a throwaway home folder."""

    def run_installer(self, home, *arguments):
        env = dict(os.environ, HOME=str(home))
        return subprocess.run([sys.executable, str(ROOT / "install.py"), "--no-launch", *arguments],
                              capture_output=True, text=True, env=env, timeout=120)

    def test_install_update_and_remove(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            first = self.run_installer(home)
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            self.assertIn("Launchpad", first.stdout)
            app = home / "Applications" / "Nudge.app"
            self.assertTrue((app / "Contents" / "MacOS" / "Nudge").is_file())
            started = subprocess.run([str(app / "Contents" / "MacOS" / "Nudge"), "--help"],
                                     capture_output=True, text=True, timeout=60)
            self.assertEqual(started.returncode, 0, started.stderr)
            self.assertIn("--demo", started.stdout)
            second = self.run_installer(home)
            self.assertEqual(second.returncode, 0, second.stderr)
            removed = self.run_installer(home, "--uninstall")
            self.assertEqual(removed.returncode, 0, removed.stderr)
            self.assertFalse(app.exists())


if __name__ == "__main__":
    unittest.main()
