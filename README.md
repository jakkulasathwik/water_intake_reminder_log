# CampusSolve Project #31: Water Intake Reminder Log

A modular, fault-tolerant Python application for tracking daily water intake against user-set hydration targets, featuring defensive validation, JSON/CSV persistence with automatic corruption recovery, executive analytics, Matplotlib visualizations, multi-format exports, bulk CSV import, and and a modern Tkinter desktop GUI (HydroTrack).

## Quick Start (Windows / VS Code)
1. Open this folder in VS Code.
2. Open Terminal (`Ctrl + ~`) and install Matplotlib (optional, graceful fallback included):
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```
4. Run automated unit tests:
   ```bash
   python -m unittest test_app.py
   ```

## Desktop GUI (HydroTrack)
Launch directly with `python main.py --gui` (or `python gui.py`, or menu option 9). No extra packages needed — it uses Tkinter, which ships with Python on Windows/macOS (on Debian/Ubuntu: `sudo apt install python3-tk`).

- **Dashboard** – animated progress ring, quick-add buttons (150–750 ml), 7-day chart, streak and recent entries
- **Add Entry** – full form with date/time/category/note, volume presets and inline validation
- **History** – live search, category and date filters, multi-select delete
- **Analytics** – 7/14/30-day charts vs. goal, category breakdown, daily status, Matplotlib PNG and report export
- **Settings** – daily goal and reminder-interval sliders, CSV import, data export
- **Reminders** – header status chip plus a pop-up toast when you are overdue for a drink
- **Light / dark theme** toggle (remembered between sessions)
