"""Starting the program: run(), demo mode, the single-instance check, main.py, run.sh."""

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

from helpers import HAS_TK, START, GuiCase, needs_tk

import main as launcher
import nudge.app as app_module
from nudge.storage import ProcessLock, default_state_path

ROOT = Path(__file__).resolve().parent.parent


class Recorder(app_module.NudgeApp):
    """Remembers the app that run() builds, so a test can look inside it."""

    instances = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        Recorder.instances.append(self)


@needs_tk
class RunTests(GuiCase):
    def setUp(self):
        super().setUp()
        Recorder.instances = []
        patches = [
            mock.patch.object(tk.Tk, "mainloop", lambda self, n=0: None),
            mock.patch.object(app_module, "NudgeApp", Recorder),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.addCleanup(self._close_recorded)

    def _close_recorded(self):
        for app in Recorder.instances:
            app._alive = False
            try:
                app.root.destroy()
            except tk.TclError:
                pass

    def test_a_normal_start_saves_defaults_and_releases_the_lock(self):
        app_module.run(state_path=self.path)
        self.assertTrue(self.path.exists())
        self.assertFalse(self.path.with_name("nudge.lock").exists())
        self.assertEqual(len(Recorder.instances), 1)
        self.assertEqual(len(Recorder.instances[0].state.reminders), 4)

    def test_a_second_copy_is_refused_politely(self):
        held = ProcessLock(self.path.with_name("nudge.lock"))
        self.assertTrue(held.acquire())
        self.addCleanup(held.release)
        with mock.patch.object(app_module.messagebox, "showinfo") as info:
            app_module.run(state_path=self.path)
        self.assertTrue(info.called)
        self.assertIn("already running", info.call_args[0][1])
        self.assertEqual(Recorder.instances, [])
        self.assertTrue(self.path.with_name("nudge.lock").exists(), "the first copy keeps its lock")

    def test_demo_rings_soon_and_leaves_real_settings_alone(self):
        real = default_state_path()
        before = real.read_bytes() if real.exists() else None
        app_module.run(demo=True, now=lambda: START)
        app = Recorder.instances[0]
        offsets = [r.next_due - START for r in app.state.reminders]
        self.assertEqual(offsets, [8, 28, 48, 68])
        self.assertNotEqual(Path(app.path).parent, real.parent)
        self.assertIn("nudge-demo-", str(app.path))
        after = real.read_bytes() if real.exists() else None
        self.assertEqual(before, after)
        shutil.rmtree(Path(app.path).parent, ignore_errors=True)

    def test_demo_does_not_use_the_lock_but_a_normal_start_does(self):
        with mock.patch("nudge.storage.ProcessLock") as lock_class:
            app_module.run(demo=True)
            self.assertFalse(lock_class.called, "a demo can run next to your real Nudge")
            app_module.run(state_path=self.path)
            self.assertTrue(lock_class.called)
        shutil.rmtree(Path(Recorder.instances[0].path).parent, ignore_errors=True)

    def test_window_is_brought_to_the_front_and_not_left_on_top(self):
        self.new_root()
        app_module.bring_to_front(self.root)
        self.assertEqual(int(self.root.attributes("-topmost")), 1)
        app_module._safe_attr(self.root, "-topmost", False)
        self.assertEqual(int(self.root.attributes("-topmost")), 0)

    def test_bring_to_front_survives_a_dead_window(self):
        self.new_root()
        self.root.destroy()
        app_module.bring_to_front(self.root)
        app_module._safe_attr(self.root, "-topmost", False)


class MainTests(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("NUDGE_NO_REEXEC", None)
        # Never really restart the test process.
        quiet = mock.patch.object(launcher, "ensure_quiet_start")
        self.quiet = quiet.start()
        self.addCleanup(quiet.stop)

    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = launcher.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_help_lists_every_option(self):
        for flag in ("--help", "-h"):
            code, out, _ = self.run_main([flag])
            self.assertEqual(code, 0)
            for option in ("--demo", "--preview"):
                self.assertIn(option, out)

    def test_flags_reach_run(self):
        for argv, expected in (
            ([], (False, False)),
            (["--demo"], (False, True)),
            (["--preview"], (True, False)),
            (["--demo", "--preview"], (True, True)),
        ):
            with self.subTest(argv=argv):
                with mock.patch.object(launcher, "switch_to_modern_tk"), \
                        mock.patch.object(app_module, "run") as run:
                    with mock.patch.object(tk, "TkVersion", 9.1):
                        code, _, err = self.run_main(argv)
                self.assertEqual(code, 0)
                run.assert_called_once_with(preview_on_start=expected[0], demo=expected[1])
                self.assertEqual(err, "")

    def test_old_tk_prints_a_warning_with_the_fix(self):
        with mock.patch.object(launcher, "switch_to_modern_tk"), \
                mock.patch.object(app_module, "run"), \
                mock.patch.object(tk, "TkVersion", 8.5):
            code, _, err = self.run_main([])
        self.assertEqual(code, 0)
        self.assertIn("brew install python-tk", err)
        self.assertIn("8.5", err)

    def test_missing_tkinter_explains_how_to_fix_it(self):
        with mock.patch.object(launcher, "switch_to_modern_tk"), \
                mock.patch.dict(sys.modules, {"tkinter": None}):
            code, _, err = self.run_main([])
        self.assertEqual(code, 1)
        self.assertIn("brew install python-tk", err)

    def test_old_tk_triggers_the_switch(self):
        with mock.patch.object(launcher, "switch_to_modern_tk") as switch, \
                mock.patch.object(app_module, "run"), \
                mock.patch.object(tk, "TkVersion", 8.5):
            self.run_main(["--demo"])
        switch.assert_called_once_with(["--demo"])

    def test_modern_tk_does_not_trigger_the_switch(self):
        with mock.patch.object(launcher, "switch_to_modern_tk") as switch, \
                mock.patch.object(app_module, "run"), \
                mock.patch.object(tk, "TkVersion", 9.1):
            self.run_main([])
        switch.assert_not_called()


class SwitchTests(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("NUDGE_NO_REEXEC", None)

    def switch(self, candidates, version, exists=True, argv=("--demo",)):
        with mock.patch.object(launcher, "CANDIDATES", candidates), \
                mock.patch.object(launcher, "tk_version", return_value=version), \
                mock.patch("os.path.exists", return_value=exists), \
                mock.patch("os.execv") as execv:
            launcher.switch_to_modern_tk(list(argv))
        return execv

    def test_restarts_under_a_python_with_a_modern_tk(self):
        execv = self.switch(("/fake/python3.13",), 9.1)
        execv.assert_called_once()
        python, args = execv.call_args[0]
        self.assertEqual(python, "/fake/python3.13")
        self.assertEqual(args[0], "/fake/python3.13")
        self.assertEqual(Path(args[1]), ROOT / "main.py")
        self.assertEqual(args[2:], ["--demo"] + launcher.extra_flags())
        self.assertEqual(os.environ["NUDGE_NO_REEXEC"], "1")

    def test_does_not_loop_forever(self):
        os.environ["NUDGE_NO_REEXEC"] = "1"
        self.switch(("/fake/python3.13",), 9.1).assert_not_called()

    def test_ignores_pythons_that_are_missing_or_still_old(self):
        self.switch(("/fake/python3.13",), 9.1, exists=False).assert_not_called()
        self.switch(("/fake/python3.13",), 8.5).assert_not_called()
        self.switch(("/fake/python3.13",), 0.0).assert_not_called()

    def test_does_not_restart_into_itself(self):
        self.switch((sys.executable,), 9.1).assert_not_called()

    def test_tries_the_next_candidate(self):
        with mock.patch.object(launcher, "CANDIDATES", ("/fake/old", "/fake/new")), \
                mock.patch.object(launcher, "tk_version", side_effect=lambda p: 8.5 if p == "/fake/old" else 9.1), \
                mock.patch("os.path.exists", return_value=True), \
                mock.patch("os.execv") as execv:
            launcher.switch_to_modern_tk([])
        self.assertEqual(execv.call_args[0][0], "/fake/new")

    @unittest.skipUnless(HAS_TK, "this Python has no Tk")
    def test_tk_version_of_this_python(self):
        self.assertGreaterEqual(launcher.tk_version(sys.executable), 8.0)

    def test_tk_version_of_something_that_is_not_python(self):
        self.assertEqual(launcher.tk_version("/definitely/not/python"), 0.0)
        self.assertEqual(launcher.tk_version("/bin/false"), 0.0)


class QuietStartTests(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)

    def run_with(self, platform, argv_in_process, argv=("--demo",)):
        with mock.patch.object(sys, "platform", platform), \
                mock.patch.object(sys, "argv", ["main.py"] + list(argv_in_process)), \
                mock.patch("os.execv") as execv:
            launcher.ensure_quiet_start(list(argv))
        return execv

    def test_mac_restarts_once_with_the_flag(self):
        execv = self.run_with("darwin", ["--demo"])
        execv.assert_called_once()
        python, args = execv.call_args[0]
        self.assertEqual(python, sys.executable)
        self.assertEqual(args[2:], ["--demo", "-ApplePersistenceIgnoreState", "YES"])

    def test_mac_does_not_restart_again_once_the_flag_is_there(self):
        flags = ["--demo", "-ApplePersistenceIgnoreState", "YES"]
        self.run_with("darwin", flags, argv=flags).assert_not_called()

    def test_the_flag_is_never_added_twice(self):
        flags = ["--demo", "-ApplePersistenceIgnoreState", "YES"]
        with mock.patch.object(sys, "platform", "darwin"), mock.patch("os.execv") as execv:
            launcher.restart("/fake/python", flags)
        self.assertEqual(execv.call_args[0][1][2:], flags)

    def test_other_systems_are_left_alone(self):
        for platform in ("linux", "win32"):
            with self.subTest(platform=platform):
                self.run_with(platform, ["--demo"]).assert_not_called()
                self.assertEqual(self.run_flags(platform), [])

    def run_flags(self, platform):
        with mock.patch.object(sys, "platform", platform):
            return launcher.extra_flags()

    def test_main_asks_for_the_quiet_start_before_opening_a_window(self):
        with mock.patch.object(launcher, "ensure_quiet_start") as quiet, \
                mock.patch.object(launcher, "switch_to_modern_tk"), \
                mock.patch.object(app_module, "run"), \
                mock.patch.object(tk, "TkVersion", 9.1):
            with contextlib.redirect_stdout(io.StringIO()):
                launcher.main(["--demo"])
        quiet.assert_called_once_with(["--demo"])


@unittest.skipUnless(shutil.which("zsh"), "zsh is not installed")
class ShellLauncherTests(unittest.TestCase):
    def test_script_has_valid_syntax_and_is_executable(self):
        subprocess.run(["zsh", "-n", str(ROOT / "run.sh")], check=True)
        self.assertTrue(os.access(ROOT / "run.sh", os.X_OK))

    def test_run_sh_forwards_arguments_to_the_program(self):
        result = subprocess.run(
            ["zsh", str(ROOT / "run.sh"), "--help"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--demo", result.stdout)

    def test_plain_python_also_works(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "main.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--preview", result.stdout)


class ProjectFilesTests(unittest.TestCase):
    def test_gitignore_keeps_personal_data_and_caches_out_of_git(self):
        text = (ROOT / ".gitignore").read_text()
        for entry in ("data/", "__pycache__/", ".venv/"):
            self.assertIn(entry, text)

    def test_readme_mentions_every_documented_command(self):
        text = (ROOT / "README.md").read_text()
        for needle in ("./run.sh", "--demo", "--preview", "brew install python-tk@3.13", "tests/run_all.py"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
