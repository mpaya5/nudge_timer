# Nudge

*Leer en español: [README.es.md](README.es.md)*

A small desktop clock for the breaks you mean to take. It keeps a separate timer for each reminder (drink water, rest, walk, stretch, or anything you add), and when one is due, a short animation walks across the screen with a sound.

- A timer **and** a frequency for every reminder, both adjustable.
- A different animation and sound per reminder. You can add your own sounds.
- A "I'm in a meeting" snooze that freezes everything and gives the time back afterwards.
- Works on macOS, Windows and Linux. Written in Python with Tkinter, no extra packages.

## Contents

- [Install](#install)
- [Using Nudge](#using-nudge)
- [Sounds](#sounds)
- [Snooze](#snooze)
- [Troubleshooting](#troubleshooting)
- [What has been tested, and what has not](#what-has-been-tested-and-what-has-not)
- [Contributing](#contributing)
- [License](#license)
- [For developers](#for-developers)

## Install

You don't need any technical knowledge. Download this folder, unzip it if needed, and double-click the file for your computer. It takes about a minute and **never asks for an administrator password**: everything goes into your own user folders.

| Your computer | Double-click this file | Then find Nudge here |
| --- | --- | --- |
| Mac | `Install on Mac.command` | Launchpad, or press Command+Space and type "Nudge" |
| Windows | `Install on Windows.bat` | Start menu: press the Windows key and type "Nudge" |
| Linux | `Install on Linux.sh` | Your applications menu: search for "Nudge" |

Nudge opens by itself when the install finishes. If the installer can't run on your machine for any reason, open a terminal in the folder and run `python3 install.py` (Windows: `py -3 install.py`). It does the same thing.

### What you need first: Python

Nudge needs Python 3.8 or newer **with its window library (Tk) version 8.6 or newer**. Most people have to install it once:

- **Mac and Windows:** get the free installer from [python.org/downloads](https://www.python.org/downloads/) and run it with the default options. It includes everything Nudge needs. If Python is missing, the installer opens that page for you; install it, then double-click the install file again.
- **Linux:** Python 3 is usually present, but the window library often is not. If it is missing, the installer prints the line to run, for example:
  - Ubuntu, Debian, Mint: `sudo apt install python3-tk`
  - Fedora: `sudo dnf install python3-tkinter`
  - Arch, Manjaro: `sudo pacman -S tk`

  For sound on Linux you also need `paplay`, which comes with `pulseaudio-utils` (or `pipewire-pulse`) and is already installed on most desktops.

> The Python that comes with macOS has Tk 8.5, which draws an **empty window**. The installer detects this and refuses to install, with instructions, instead of leaving you with a blank app.

### Step by step

**macOS**

1. Download and unzip the folder.
2. Double-click `Install on Mac.command`. A Terminal window opens and shows the progress.
3. If macOS says it can't verify the file: right-click it and choose **Open**, then **Open** again. On newer macOS versions that don't show an Open button, go to **System Settings > Privacy & Security**, scroll down, and click **Open Anyway** next to the message about the file. You only need to do this once.
4. When it says "Nudge is installed", press any key to close the window. Nudge opens.
5. From now on, open it from Launchpad or Spotlight. Nudge has its own icon (a clock with four colored dots). The program lives in `~/Library/Application Support/Nudge`, and `Nudge.app` is in `~/Applications`.

**Windows**

1. Download and unzip the folder (right-click the zip, **Extract All**; don't run it from inside the zip).
2. Double-click `Install on Windows.bat`. A black window shows the progress.
3. If a blue "Windows protected your PC" box appears, click **More info**, then **Run anyway**.
4. When it says "Nudge is installed", press any key. Nudge opens.
5. From now on, press the Windows key and type "Nudge". The program lives in `%LOCALAPPDATA%\Nudge` and the shortcut is in the Start menu. If PowerShell is blocked on your computer, the installer falls back to a plain `Nudge.cmd` launcher in the same Start menu folder.

**Linux**

1. Download and unzip the folder.
2. Run `Install on Linux.sh`. Many file managers offer **Run** or **Run in Terminal** when you double-click or right-click it. If yours opens it in a text editor instead, open a terminal in the folder and type `sh "Install on Linux.sh"`.
3. When it says "Nudge is installed", press Enter. Nudge opens.
4. From now on, search for "Nudge" in your applications menu. The program lives in `~/.local/share/nudge`. If the menu entry doesn't appear right away, log out and in again.

### Updating

Download the newer folder and double-click the same install file. The program is replaced, and **your reminders and added sounds are kept**. If you were using Nudge straight from the downloaded folder before installing, the first install brings those reminders along.

### Removing Nudge

Open a terminal in the downloaded folder and run:

```bash
python3 install.py --uninstall        # Windows: py -3 install.py --uninstall
```

This removes the app and its launcher but **keeps your reminders**, in case you come back (it tells you where they are). Add `--remove-data` to delete those too:

```bash
python3 install.py --uninstall --remove-data
```

### Where your data lives

| System | Program and data |
| --- | --- |
| Mac | `~/Library/Application Support/Nudge` (reminders in `data/state.json`, added sounds in `data/sounds/`) |
| Windows | `%LOCALAPPDATA%\Nudge` (same layout) |
| Linux | `~/.local/share/nudge` (same layout) |

Leave Nudge running in the background: closing its window stops the reminders. Your timers are saved, so the next launch continues where you left off.

## Using Nudge

Each card has two settings:

- **Frequency**: how often it shows up (every 40 minutes, for example).
- **Timer**: how long the activity lasts once you press Start (a 2 minute stretch).

The ring at the top counts down to whichever reminder is next. `+` and `−` adjust a card quickly. **Edit** sets an exact number of minutes, the name, the color, the sound, and which animation plays. **Add a reminder** creates your own. **Preview** walks the animation across the screen, with its sound, without changing that reminder's schedule.

## Sounds

Every reminder can have its own sound. Press **Edit** on a card and look at **Sound**:

- **Matches the animation** (the default) plays a different gentle chime for water, rest, walk and stretch.
- **Silent** keeps that one reminder quiet while the others still ring.
- **Mac system sounds** such as Glass, Hero or Ping are listed on a Mac.
- **Add your own sound…** opens your files. Pick any short sound and it appears in the list, ready for any reminder to use. Nudge keeps its own copy, so it still works if you move or delete the original.

Press **Play** next to the list to hear a sound before you save. **Sound on / Muted** at the top of the window silences everything at once.

Sounds you can add: WAV, MP3, AIFF and M4A on a Mac; WAV on Windows; WAV, OGG and FLAC on Linux. Keep them short (a few seconds, under 5 MB). If a file can't be used, Nudge says why and keeps your previous choice.

## Snooze

**In a meeting?** at the bottom freezes every reminder for 15 minutes, 30 minutes, 1 hour, or 2 hours. They resume on their own, with the time you had left still intact. **Resume now** brings them back early.

**Pause** freezes them until you press **Resume**. It does not turn itself back on.

When an alarm is on screen:

- **Start** runs that reminder's timer.
- **5 / 10 / 15 min** snoozes only that reminder.
- **I'm in a meeting** snoozes everything for 30 minutes.
- **Esc** snoozes the one on screen for 10 minutes (or ends the activity timer if you already started it).
- **Return** starts the timer.
- If you ignore the prompt for 5 minutes, it snoozes itself for 10.

Time you spend with the app closed still counts, unless a pause or meeting snooze was on. Several reminders missed while it was closed (or while the computer slept) come back one at a time instead of all at once.

## Troubleshooting

| Problem | What to do |
| --- | --- |
| The window is empty (Mac) | The Python in use has an old Tk. Install Python from [python.org](https://www.python.org/downloads/) and install Nudge again. |
| The window doesn't appear | Mac: look for the icon in the Dock and click it. Make sure Nudge isn't already running (it tells you if it is). |
| "Nudge is already running" | Only one copy runs at a time, so two don't overwrite each other's reminders. Find the open window. If Nudge was closed abnormally (a crash, a power cut), the lock clears itself and it starts normally. |
| No sound | Check the **Sound on / Muted** button, then the reminder's **Sound** choice (not **Silent**). Linux: install `pulseaudio-utils` for `paplay`. Windows plays added sounds only if they are `.wav`. |
| The installer says Python is missing or too old | Install the free Python from [python.org](https://www.python.org/downloads/) and double-click the install file again. |
| Mac or Windows warns about the file | See the step-by-step instructions above. It's a one-time confirmation because the file was downloaded. |
| The Linux menu entry doesn't show | Log out and in again, or run `python3 ~/.local/share/nudge/main.py`. |

## What has been tested, and what has not

Honest summary, so you know how much to trust each part.

### Automated tests

`python3 tests/run_all.py` runs **384 tests**:

| Python | Tk | Result |
| --- | --- | --- |
| 3.13 (Homebrew) | 9.1 | all pass |
| 3.9 (macOS system Python) | 8.5 | all pass; 2 skipped because they need Tk 8.6+ |

- **Code coverage: 94%** of the lines. The uncovered lines are mostly defensive error handling (disk or system errors) and the Windows-only process check.
- **Planted-bug check:** `python3 tests/mutation_check.py` puts 23 deliberate bugs into a temporary copy, one at a time (for example "a silent reminder still plays", "an update overwrites your reminders", "Windows ends the other Nudge"). The tests failed for **all 23**.
- **Randomized test:** 300 random histories of pause, snooze and resume confirm that paused time never leaks into a countdown.
- **Style:** `pyflakes` reports nothing; `pycodestyle` is clean.

What the automated tests cover: the timing rules (frequency, timer, pause, meeting snooze, wake from sleep), saving and loading (including damaged files), adding, editing and deleting reminders in the real window, the alarm window and its phases, sound choice and playing, adding your own sounds (including hostile file names), the installer's files for all three systems, and the icon.

### Tried for real on a Mac

- The main window, the add and edit dialogs, the alarm animations and the prompt, checked with screenshots.
- The full install on macOS into a throwaway home folder: building `Nudge.app`, opening it like a double-click would (it opened, with its own Dock icon), updating over an existing install, uninstalling (keeping and removing reminders), and reinstalling.
- Refusal of the old Tk 8.5, with the right message and nothing installed.

### Not tested

| What | Why it matters |
| --- | --- |
| **Everything on real Windows** (install, Start menu shortcut, `pythonw`, `.wav` playback, the running-copy check) | The installer's files and commands were built and checked here, but PowerShell and Windows APIs were replaced by stand-ins. |
| **Everything on real Linux** (install, menu entry, `paplay`, Tk, window behavior) | Same: the `.desktop` file and commands are checked as text only. Window managers (and Wayland) differ in how they handle always-on-top and borderless windows. |
| Real keypresses (Esc, Return) on the alarm window | The tests check focus and the key handlers, but cannot type on the keyboard. |
| **Hearing** the sounds | Tests check the exact command that plays a sound, not the audio. MP3 and M4A decoding by the system player was not verified. |
| Opening the downloaded install files with the real macOS and Windows security prompts | Only the instructions are written; the prompts depend on system version. |
| Python 3.8 and 3.10 to 3.12 | The code is written to work from 3.8, but only 3.9 and 3.13 were run. |
| Multiple monitors, very high-resolution screens, other macOS or Windows versions | Not tried. |

If you can test any of these, please say how it went. It helps everyone.

## Contributing

Contributions of any size are welcome, and you don't need to be an expert:

- **Try it** on a system we couldn't (see the table above) and tell us what happened, including if everything worked.
- **Report a problem** or suggest an idea: open an issue with what you did, what you expected, what happened, your system and Python version (`python3 --version`), and any message shown.
- **Suggest improvements**: new animations, more reminder ideas, wording that is clearer for non-technical users, a translation, a "start when I log in" option.
- **Send a change**: fork, make your edit, run the tests (below), and open a pull request describing what and why.

Guidelines that keep things smooth:

1. Run `python3 tests/run_all.py` before and after your change. Everything should pass.
2. Add a test for new behavior or a bug fix. Tests in `tests/` show the pattern; window tests use `GuiCase` in `tests/helpers.py` with a fake clock.
3. Keep it simple for non-technical users: plain wording in messages, no jargon.
4. Keep it dependency-free (standard library only) and compatible with Python 3.8+.
5. For timing or installer changes, also run `python3 tests/mutation_check.py` to check the tests would notice a regression.

Tests on Windows and Linux are the most valuable contribution right now.

## License

Nudge is free software under the [MIT License](LICENSE): you may use, copy, modify and share it, including for your team or company, as long as the license notice stays with it. It comes without any warranty. The app's interface is in English.

## For developers

### Run it from the folder

```bash
./run.sh
```

That picks a Python with a modern Tk. The Tk 8.5 bundled with macOS draws an empty window, so use the python.org Python, or with Homebrew:

```bash
brew install python-tk@3.13
```

Plain `python3 main.py` also switches to a suitable Python on its own. Run from the folder, Nudge keeps its data in `data/` next to `main.py`.

To see an alarm right away:

```bash
python3 main.py --demo
```

Alarms fire after 8, 28, 48 and 68 seconds. Demo mode uses throwaway settings, so your real reminders are untouched.

```bash
python3 main.py --preview
```

plays the first reminder's animation immediately.

### Project layout

| Path | What it is |
| --- | --- |
| `main.py` | Entry point; finds a Python with a modern Tk |
| `install.py` | Command-line installer (the double-click files call it) |
| `Install on ….command / .bat / .sh` | Double-click launchers for the installer |
| `nudge/logic.py` | Pure timing rules (pause, snooze, wake from sleep) |
| `nudge/app.py`, `cards.py`, `dialog.py`, `widgets.py` | Main window, reminder cards, add/edit dialog |
| `nudge/overlay.py`, `sprites.py` | The alarm window and its animations |
| `nudge/sound.py` | Built-in and added sounds, playing them |
| `nudge/storage.py`, `models.py` | Saving, loading, the single-copy lock, data types |
| `nudge/installer.py`, `icon.py` | Installer logic and the drawn app icon |
| `tests/` | Test suite, plus `mutation_check.py` |

The icon is drawn by `nudge/icon.py`; run `python3 -m nudge.icon` after changing it.

### Tests

```bash
python3 tests/run_all.py        # add -v to list every test
```

The window tests open real (hidden) windows, so run them from a normal terminal, not a sandbox. They are skipped automatically if Tk cannot start. On macOS, `run_all.py` starts Python in a mode that avoids a hidden "reopen windows?" prompt that could stall the tests after a crash.

To check that the tests really catch bugs, `python3 tests/mutation_check.py` plants two dozen deliberate bugs, one at a time, in a temporary copy of the project and confirms the suite fails for each. It takes a few minutes and never touches your files.
