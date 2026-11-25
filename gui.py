"""Modern Tkinter desktop interface for the Water Intake Reminder Log.

Pure standard-library Tk (no extra dependencies). Features: sidebar navigation,
animated progress ring, quick-add buttons, native canvas charts, searchable
history, settings, CSV import / report export, reminder toasts, light/dark theme.
"""
import re
import sys
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime, timedelta
from tkinter import ttk, messagebox, filedialog

from models import WaterEntry
from validators import CATEGORIES, MIN_VOLUME_ML, MAX_VOLUME_ML
from storage import (
    load_config, save_config, load_entries, save_entries,
    bulk_import_csv, next_entry_id, SAMPLE_IMPORT_PATH,
)
from analytics import (
    build_daily_summaries, calculate_streak, check_reminder_status,
    plot_hydration_trends, export_reports,
)

LIGHT = dict(
    bg="#f1f5f9", card="#ffffff", text="#0f172a", muted="#64748b", border="#e2e8f0",
    primary="#0284c7", primary_hover="#0369a1", accent="#10b981", warn="#f59e0b",
    danger="#ef4444", sidebar="#0c4a6e", sidebar_text="#bae6fd", sidebar_active="#075985",
    track="#e0f2fe", input="#ffffff", row_alt="#f8fafc", on_primary="#ffffff",
)
DARK = dict(
    bg="#0b1220", card="#111c2e", text="#e2e8f0", muted="#94a3b8", border="#1f2f48",
    primary="#0ea5e9", primary_hover="#38bdf8", accent="#34d399", warn="#fbbf24",
    danger="#f87171", sidebar="#070e1a", sidebar_text="#93c5fd", sidebar_active="#12233d",
    track="#1f2f48", input="#0d1626", row_alt="#0e1829", on_primary="#06121f",
)
PAGES = [("dashboard", "Dashboard", "◉"), ("add", "Add Entry", "＋"), ("history", "History", "☰"),
         ("analytics", "Analytics", "▤"), ("settings", "Settings", "⚙")]
QUICK_ML = [150, 250, 330, 500, 750]


class FlatButton(tk.Label):
    """Label-based button with hover colour (looks identical on every OS)."""

    def __init__(self, master, text, command, bg, fg, hover, font, padx=16, pady=8):
        super().__init__(master, text=text, bg=bg, fg=fg, font=font, padx=padx, pady=pady, cursor="hand2")
        self._bg, self._hover, self._cmd = bg, hover, command
        self.bind("<Enter>", lambda _e: self.config(bg=self._hover))
        self.bind("<Leave>", lambda _e: self.config(bg=self._bg))
        self.bind("<Button-1>", lambda _e: self._cmd())


class WaterTrackerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("HydroTrack – Water Intake Reminder Log")
        self.root.geometry("1180x760")
        self.root.minsize(1020, 680)
        self.cfg = load_config()
        self.cfg.setdefault("reminder_interval_mins", 90)
        self.cfg.setdefault("theme", "light")
        self.entries = load_entries()
        self.t = DARK if self.cfg["theme"] == "dark" else LIGHT
        self.page = "dashboard"
        self._ring_prev = 0.0
        self._last_notified = None
        self._toast_win = None

        fam = "Segoe UI" if "Segoe UI" in tkfont.families() else tkfont.nametofont("TkDefaultFont").actual("family")
        self.F = dict(
            h1=(fam, 20, "bold"), h2=(fam, 13, "bold"), body=(fam, 10), bold=(fam, 10, "bold"),
            small=(fam, 9), big=(fam, 30, "bold"), stat=(fam, 20, "bold"), btn=(fam, 10, "bold"),
        )
        self._build_shell()
        self._show(self.page)
        self.root.after(1500, self._tick)

    # ------------------------------------------------------------------ shell
    def _build_shell(self):
        for w in self.root.winfo_children():
            w.destroy()
        t = self.t
        self.root.configure(bg=t["bg"])
        self._style()

        self.sidebar = tk.Frame(self.root, bg=t["sidebar"], width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar, text="💧 HydroTrack", font=self.F["h2"], bg=t["sidebar"], fg="#ffffff",
                 anchor="w").pack(fill="x", padx=22, pady=(26, 2))
        tk.Label(self.sidebar, text="Water Intake Reminder Log", font=self.F["small"], bg=t["sidebar"],
                 fg=t["sidebar_text"], anchor="w").pack(fill="x", padx=22, pady=(0, 24))
        self.nav = {}
        for key, label, icon in PAGES:
            row = tk.Frame(self.sidebar, bg=t["sidebar"], cursor="hand2")
            row.pack(fill="x")
            bar = tk.Frame(row, bg=t["sidebar"], width=4)
            bar.pack(side="left", fill="y")
            lbl = tk.Label(row, text=f"  {icon}   {label}", font=self.F["btn"], bg=t["sidebar"],
                           fg=t["sidebar_text"], anchor="w", pady=11, padx=14)
            lbl.pack(side="left", fill="x", expand=True)
            for w in (row, lbl, bar):
                w.bind("<Button-1>", lambda _e, k=key: self._show(k))
            self.nav[key] = (row, bar, lbl)
        FlatButton(self.sidebar, "◐  Toggle theme", self._toggle_theme, t["sidebar_active"], "#ffffff",
                   t["primary"], self.F["small"], pady=7).pack(side="bottom", fill="x", padx=18, pady=20)

        main = tk.Frame(self.root, bg=t["bg"])
        main.pack(side="left", fill="both", expand=True)
        head = tk.Frame(main, bg=t["bg"])
        head.pack(fill="x", padx=30, pady=(24, 6))
        self.title_lbl = tk.Label(head, text="", font=self.F["h1"], bg=t["bg"], fg=t["text"])
        self.title_lbl.pack(side="left")
        self.chip = tk.Label(head, text="", font=self.F["bold"], padx=14, pady=6)
        self.chip.pack(side="right")
        self.content = tk.Frame(main, bg=t["bg"])
        self.content.pack(fill="both", expand=True, padx=30, pady=(6, 22))
        self._refresh_chip()

    def _style(self):
        t = self.t
        st = ttk.Style()
        st.theme_use("clam")
        st.configure("App.Treeview", background=t["card"], fieldbackground=t["card"], foreground=t["text"],
                     rowheight=32, borderwidth=0, font=self.F["body"])
        st.configure("App.Treeview.Heading", background=t["bg"], foreground=t["muted"], relief="flat",
                     font=self.F["bold"], padding=(8, 8))
        st.map("App.Treeview", background=[("selected", t["primary"])], foreground=[("selected", t["on_primary"])])
        st.configure("App.TCombobox", fieldbackground=t["input"], background=t["input"], foreground=t["text"],
                     arrowcolor=t["muted"], bordercolor=t["border"], lightcolor=t["border"], darkcolor=t["border"],
                     padding=6)
        st.map("App.TCombobox", fieldbackground=[("readonly", t["input"])], foreground=[("readonly", t["text"])],
               selectbackground=[("readonly", t["input"])], selectforeground=[("readonly", t["text"])])
        st.configure("App.Vertical.TScrollbar", background=t["border"], troughcolor=t["card"], bordercolor=t["card"],
                     arrowcolor=t["muted"])
        self.root.option_add("*TCombobox*Listbox.background", t["card"])
        self.root.option_add("*TCombobox*Listbox.foreground", t["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", t["primary"])

    def _show(self, page: str):
        self.page = page
        t = self.t
        for key, (row, bar, lbl) in self.nav.items():
            active = key == page
            bg = t["sidebar_active"] if active else t["sidebar"]
            row.config(bg=bg); lbl.config(bg=bg, fg="#ffffff" if active else t["sidebar_text"])
            bar.config(bg=t["primary_hover"] if active else bg)
        for w in self.content.winfo_children():
            w.destroy()
        titles = {k: n for k, n, _ in PAGES}
        self.title_lbl.config(text=titles[page])
        getattr(self, f"_page_{page}")(self.content)

    def _toggle_theme(self):
        self.cfg["theme"] = "light" if self.cfg["theme"] == "dark" else "dark"
        self.t = DARK if self.cfg["theme"] == "dark" else LIGHT
        save_config(self.cfg)
        self._ring_prev = 0.0
        self._build_shell()
        self._show(self.page)

    # ---------------------------------------------------------------- helpers
    def _card(self, parent, **kw):
        return tk.Frame(parent, bg=self.t["card"], highlightthickness=1, highlightbackground=self.t["border"], **kw)

    def _btn(self, parent, text, cmd, kind="primary", **kw):
        t = self.t
        colors = {"primary": (t["primary"], t["on_primary"], t["primary_hover"]),
                  "success": (t["accent"], "#06281d" if self.cfg["theme"] == "dark" else "#ffffff", t["accent"]),
                  "ghost": (t["border"], t["text"], t["track"]),
                  "danger": (t["danger"], "#ffffff", t["danger"])}[kind]
        return FlatButton(parent, text, cmd, colors[0], colors[1], colors[2], self.F["btn"], **kw)

    def _entry(self, parent, var, width=14):
        t = self.t
        return tk.Entry(parent, textvariable=var, width=width, relief="flat", bg=t["input"], fg=t["text"],
                        insertbackground=t["text"], highlightthickness=1, highlightbackground=t["border"],
                        highlightcolor=t["primary"], font=self.F["body"])

    def _label(self, parent, text, kind="body", **kw):
        fg = kw.pop("fg", self.t["muted"] if kind == "muted" else self.t["text"])
        font = self.F["small"] if kind == "muted" else self.F[kind if kind in self.F else "body"]
        return tk.Label(parent, text=text, font=font, bg=kw.pop("bg", self.t["card"]), fg=fg, **kw)

    def _status_color(self, status: str) -> str:
        if status.startswith(("WARNING", "CRITICAL")):
            return self.t["danger"]
        return self.t["accent"] if status == "Target Met" else self.t["primary"]

    def _today(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _today_total(self) -> int:
        d = self._today()
        return sum(e.amount_ml for e in self.entries if e.date == d)

    def _last_days(self, n: int):
        totals = {}
        for e in self.entries:
            totals[e.date] = totals.get(e.date, 0) + e.amount_ml
        days = [(datetime.now() - timedelta(days=i)).date() for i in range(n - 1, -1, -1)]
        return [d.strftime("%d %b") for d in days], [totals.get(d.strftime("%Y-%m-%d"), 0) for d in days]

    def _save(self):
        save_entries(self.entries)

    def _refresh_chip(self):
        msg = check_reminder_status(self.entries, self.cfg["reminder_interval_mins"])
        t = self.t
        if msg.startswith(("OVERDUE", "REMINDER")):
            bg, fg = ("#fee2e2", "#991b1b") if self.cfg["theme"] == "light" else ("#4c1d1d", "#fecaca")
        else:
            bg, fg = ("#dcfce7", "#166534") if self.cfg["theme"] == "light" else ("#123524", "#bbf7d0")
        self.chip.config(text="⏰  " + msg, bg=bg, fg=fg)
        return msg

    def toast(self, message: str, kind: str = "ok"):
        if self._toast_win is not None:
            try:
                self._toast_win.destroy()
            except tk.TclError:
                pass
        color = {"ok": self.t["accent"], "warn": self.t["warn"], "err": self.t["danger"]}[kind]
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        try:
            win.attributes("-topmost", True)
        except tk.TclError:
            pass
        frame = tk.Frame(win, bg=self.t["card"], highlightthickness=2, highlightbackground=color)
        frame.pack()
        tk.Label(frame, text=message, font=self.F["bold"], bg=self.t["card"], fg=self.t["text"],
                 padx=20, pady=14).pack()
        win.update_idletasks()
        x = self.root.winfo_x() + self.root.winfo_width() - win.winfo_width() - 30
        y = self.root.winfo_y() + self.root.winfo_height() - win.winfo_height() - 40
        win.geometry(f"+{x}+{y}")
        self._toast_win = win
        win.after(3200, lambda: win.winfo_exists() and win.destroy())

    def _tick(self):
        """Periodic reminder check (every 30 s)."""
        try:
            msg = self._refresh_chip()
            if msg.startswith(("OVERDUE", "REMINDER")):
                gap = timedelta(minutes=self.cfg["reminder_interval_mins"])
                if self._last_notified is None or datetime.now() - self._last_notified >= gap:
                    self._last_notified = datetime.now()
                    self.toast("💧 Time to drink some water!", "warn")
        except tk.TclError:
            return
        self.root.after(30000, self._tick)

    def _add_entry(self, amount, category, note, date=None, time=None):
        now = datetime.now()
        entry = WaterEntry(next_entry_id(self.entries), date or now.strftime("%Y-%m-%d"),
                           time or now.strftime("%H:%M"), amount, category, note or "Routine intake")
        self.entries.append(entry)
        self.entries.sort(key=lambda e: (e.date, e.time))
        self._save()
        self._refresh_chip()
        self._last_notified = None
        return entry

    # ----------------------------------------------------------------- charts
    def _draw_bars(self, cv, labels, values, target):
        t = self.t
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 60 or h < 60:
            return
        pl, pr, pt, pb = 46, 14, 14, 28
        vmax = max(max(values, default=0), target) * 1.15 or 1
        for i in range(5):
            y = pt + (h - pt - pb) * i / 4
            cv.create_line(pl, y, w - pr, y, fill=t["border"])
            cv.create_text(pl - 8, y, text=f"{int(vmax * (1 - i / 4))}", anchor="e", fill=t["muted"], font=self.F["small"])
        n = len(values)
        slot = (w - pl - pr) / max(n, 1)
        bw = min(slot * 0.58, 48)
        for i, (lab, v) in enumerate(zip(labels, values)):
            x0 = pl + slot * i + (slot - bw) / 2
            y1 = h - pb
            y0 = y1 - (h - pt - pb) * v / vmax
            col = t["accent"] if v >= target else (t["primary"] if v >= target * 0.5 else t["warn"])
            if v > 0:
                cv.create_rectangle(x0, y0, x0 + bw, y1, fill=col, outline="")
            if n <= 14 or i % 2 == 0:
                cv.create_text(x0 + bw / 2, h - pb + 14, text=lab, fill=t["muted"], font=self.F["small"])
        ty = h - pb - (h - pt - pb) * target / vmax
        cv.create_line(pl, ty, w - pr, ty, fill=t["danger"], dash=(5, 4), width=2)
        cv.create_text(w - pr, ty - 9, text=f"Goal {target} ml", anchor="e", fill=t["danger"], font=self.F["small"])

    def _draw_hbars(self, cv, items):
        t = self.t
        cv.delete("all")
        w = cv.winfo_width()
        if w < 60 or not items:
            return
        vmax = max(v for _, v in items) or 1
        total = sum(v for _, v in items) or 1
        palette = [t["primary"], t["accent"], t["warn"], "#a78bfa", "#f472b6"]
        for i, (name, v) in enumerate(items):
            y = 14 + i * 38
            cv.create_text(0, y, text=name, anchor="w", fill=t["text"], font=self.F["small"])
            bx0, bx1 = 150, w - 110
            cv.create_rectangle(bx0, y - 7, bx1, y + 7, fill=t["track"], outline="")
            if v:
                cv.create_rectangle(bx0, y - 7, bx0 + (bx1 - bx0) * v / vmax, y + 7, fill=palette[i % 5], outline="")
            cv.create_text(w, y, text=f"{v} ml · {v / total * 100:.0f}%", anchor="e", fill=t["muted"], font=self.F["small"])

    def _animate_ring(self, cv, target_pct, total, target):
        steps, start = 20, self._ring_prev
        self._ring_prev = target_pct

        def frame(i=1):
            if not cv.winfo_exists():
                return
            k = 1 - (1 - i / steps) ** 3  # ease-out
            self._draw_ring(cv, start + (target_pct - start) * k, total, target, target_pct)
            if i < steps:
                cv.after(16, lambda: frame(i + 1))
        frame()

    def _draw_ring(self, cv, pct, total, target, final_pct):
        t = self.t
        cv.delete("all")
        cx, cy, r = 130, 130, 100
        cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=t["track"], width=20)
        col = t["accent"] if final_pct >= 100 else (t["primary"] if final_pct >= 50 else t["warn"])
        if pct >= 100:
            cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=col, width=20)
        elif pct > 0.3:
            cv.create_arc(cx - r, cy - r, cx + r, cy + r, start=90, extent=-pct * 3.6, style="arc", outline=col, width=20)
        cv.create_text(cx, cy - 22, text=f"{int(total * pct / final_pct) if final_pct else 0}", fill=t["text"], font=self.F["big"])
        cv.create_text(cx, cy + 12, text=f"of {target} ml", fill=t["muted"], font=self.F["body"])
        cv.create_text(cx, cy + 40, text=f"{final_pct:.0f}% complete", fill=col, font=self.F["bold"])

    # ------------------------------------------------------------------ pages
    def _page_dashboard(self, p):
        t = self.t
        target = self.cfg["daily_target_ml"]
        total = self._today_total()
        pct = total / target * 100 if target else 0
        summaries = build_daily_summaries(self.entries, target)
        _, last7 = self._last_days(7)
        today_n = sum(1 for e in self.entries if e.date == self._today())
        p.columnconfigure(0, weight=2, uniform="a"); p.columnconfigure(1, weight=3, uniform="a")
        p.rowconfigure(1, weight=1)

        ring_card = self._card(p)
        ring_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14), pady=(0, 14))
        self._label(ring_card, "Today's progress", "h2").pack(anchor="w", padx=20, pady=(16, 0))
        cv = tk.Canvas(ring_card, width=260, height=260, bg=t["card"], highlightthickness=0)
        cv.pack(pady=(4, 14))
        self._animate_ring(cv, pct, total, target)

        right = tk.Frame(p, bg=t["bg"])
        right.grid(row=0, column=1, sticky="nsew", pady=(0, 14))
        right.columnconfigure((0, 1, 2), weight=1, uniform="s")
        stats = [("Entries today", str(today_n), t["primary"]),
                 ("7-day average", f"{sum(last7) // 7} ml", t["accent"]),
                 ("Goal streak", f"{calculate_streak(summaries)} day(s)", t["warn"])]
        for i, (name, val, col) in enumerate(stats):
            c = self._card(right)
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 7, 0 if i == 2 else 7))
            self._label(c, name, "muted").pack(anchor="w", padx=16, pady=(14, 0))
            self._label(c, val, "stat", fg=col).pack(anchor="w", padx=16, pady=(2, 14))

        quick = self._card(right)
        quick.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=(14, 0))
        right.rowconfigure(1, weight=1)
        self._label(quick, "Quick add", "h2").pack(anchor="w", padx=20, pady=(16, 2))
        self._label(quick, "One click logs plain water at the current time.", "muted").pack(anchor="w", padx=20)
        row = tk.Frame(quick, bg=t["card"])
        row.pack(anchor="w", padx=20, pady=14)
        for ml in QUICK_ML:
            self._btn(row, f"+{ml} ml", lambda m=ml: self._quick_add(m)).pack(side="left", padx=(0, 10))
        self._btn(row, "Custom…", lambda: self._show("add"), "ghost").pack(side="left")

        chart_card = self._card(p)
        chart_card.grid(row=1, column=0, columnspan=1, sticky="nsew", padx=(0, 14))
        self._label(chart_card, "Last 7 days", "h2").pack(anchor="w", padx=20, pady=(14, 0))
        labels, vals = self._last_days(7)
        ccv = tk.Canvas(chart_card, bg=t["card"], highlightthickness=0, height=170)
        ccv.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        ccv.bind("<Configure>", lambda _e: self._draw_bars(ccv, labels, vals, target))

        recent = self._card(p)
        recent.grid(row=1, column=1, sticky="nsew")
        self._label(recent, "Recent entries", "h2").pack(anchor="w", padx=20, pady=(14, 6))
        for e in list(reversed(self.entries))[:5]:
            r = tk.Frame(recent, bg=t["card"])
            r.pack(fill="x", padx=20, pady=3)
            self._label(r, f"{e.amount_ml} ml", "bold", fg=t["primary"], width=8, anchor="w").pack(side="left")
            self._label(r, f"{e.category}", "body", anchor="w").pack(side="left")
            self._label(r, f"{e.date}  {e.time}", "muted").pack(side="right")

    def _quick_add(self, ml):
        self._add_entry(ml, CATEGORIES[0], "Quick add")
        self._show("dashboard")
        self.toast(f"✓ Added {ml} ml")

    def _page_add(self, p):
        t = self.t
        card = self._card(p)
        card.pack(anchor="nw", fill="x")
        self._label(card, "Log new water intake", "h2").grid(row=0, column=0, columnspan=4, sticky="w", padx=24, pady=(20, 2))
        self._label(card, f"Volume must be {MIN_VOLUME_ML}–{MAX_VOLUME_ML} ml.", "muted").grid(row=1, column=0, columnspan=4, sticky="w", padx=24, pady=(0, 14))
        self.f_amt, self.f_date = tk.StringVar(value="250"), tk.StringVar(value=self._today())
        self.f_time, self.f_cat = tk.StringVar(value=datetime.now().strftime("%H:%M")), tk.StringVar(value=CATEGORIES[0])
        self.f_note = tk.StringVar()
        fields = [("Volume (ml)", self._entry(card, self.f_amt, 16)), ("Date (YYYY-MM-DD)", self._entry(card, self.f_date, 16)),
                  ("Time (HH:MM)", self._entry(card, self.f_time, 16))]
        for i, (name, widget) in enumerate(fields):
            self._label(card, name, "muted").grid(row=2, column=i, sticky="w", padx=(24, 8))
            widget.grid(row=3, column=i, sticky="ew", padx=(24, 8), pady=(2, 14), ipady=6)
        self._label(card, "Category", "muted").grid(row=2, column=3, sticky="w", padx=(16, 24))
        ttk.Combobox(card, textvariable=self.f_cat, values=CATEGORIES, state="readonly", style="App.TCombobox",
                     width=22).grid(row=3, column=3, sticky="ew", padx=(16, 24), pady=(2, 14))
        self._label(card, "Note (optional)", "muted").grid(row=4, column=0, sticky="w", padx=24)
        self._entry(card, self.f_note, 60).grid(row=5, column=0, columnspan=4, sticky="ew", padx=24, pady=(2, 14), ipady=6)
        presets = tk.Frame(card, bg=t["card"])
        presets.grid(row=6, column=0, columnspan=4, sticky="w", padx=24)
        self._label(presets, "Presets:", "muted").pack(side="left", padx=(0, 10))
        for ml in (100, 200, 250, 330, 500, 1000):
            self._btn(presets, f"{ml}", lambda m=ml: self.f_amt.set(str(m)), "ghost", padx=12, pady=5).pack(side="left", padx=4)
        self.form_err = self._label(card, "", "small", fg=t["danger"])
        self.form_err.grid(row=7, column=0, columnspan=4, sticky="w", padx=24, pady=(14, 0))
        btns = tk.Frame(card, bg=t["card"])
        btns.grid(row=8, column=0, columnspan=4, sticky="w", padx=24, pady=(8, 22))
        self._btn(btns, "＋  Add entry", self._submit_form, "success").pack(side="left", padx=(0, 10))
        self._btn(btns, "Set time to now", lambda: self.f_time.set(datetime.now().strftime("%H:%M")), "ghost").pack(side="left")
        for c in range(4):
            card.columnconfigure(c, weight=1)

    def _submit_form(self):
        try:
            amt = int(self.f_amt.get().strip())
        except ValueError:
            return self.form_err.config(text="Volume must be a whole number.")
        if not MIN_VOLUME_ML <= amt <= MAX_VOLUME_ML:
            return self.form_err.config(text=f"Volume must be between {MIN_VOLUME_ML} and {MAX_VOLUME_ML} ml.")
        d, tm = self.f_date.get().strip(), self.f_time.get().strip()
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
                raise ValueError
            datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            return self.form_err.config(text="Date must be a valid YYYY-MM-DD.")
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", tm):
            return self.form_err.config(text="Time must be 24-hour HH:MM.")
        self._add_entry(amt, self.f_cat.get(), self.f_note.get().strip(), d, tm)
        self._show("dashboard")
        self.toast(f"✓ Logged {amt} ml")

    def _page_history(self, p):
        t = self.t
        bar = self._card(p)
        bar.pack(fill="x", pady=(0, 12))
        self.h_search, self.h_cat, self.h_date = tk.StringVar(), tk.StringVar(value="All categories"), tk.StringVar()
        self._label(bar, "Search", "muted").grid(row=0, column=0, sticky="w", padx=(18, 6), pady=(12, 0))
        self._entry(bar, self.h_search, 26).grid(row=1, column=0, padx=(18, 6), pady=(2, 14), ipady=5)
        self._label(bar, "Category", "muted").grid(row=0, column=1, sticky="w", padx=6, pady=(12, 0))
        ttk.Combobox(bar, textvariable=self.h_cat, values=["All categories"] + CATEGORIES, state="readonly",
                     style="App.TCombobox", width=22).grid(row=1, column=1, padx=6, pady=(2, 14))
        self._label(bar, "Date (YYYY-MM-DD)", "muted").grid(row=0, column=2, sticky="w", padx=6, pady=(12, 0))
        self._entry(bar, self.h_date, 14).grid(row=1, column=2, padx=6, pady=(2, 14), ipady=5)
        self._btn(bar, "Today", lambda: self.h_date.set(self._today()), "ghost", padx=12, pady=6).grid(row=1, column=3, padx=4)
        self._btn(bar, "Clear", self._clear_filters, "ghost", padx=12, pady=6).grid(row=1, column=4, padx=4)
        self._btn(bar, "Delete selected", self._delete_selected, "danger", padx=12, pady=6).grid(row=1, column=5, padx=(4, 18))
        bar.columnconfigure(5, weight=1)
        bar.grid_slaves(row=1, column=5)[0].grid_configure(sticky="e")

        box = self._card(p)
        box.pack(fill="both", expand=True)
        cols = ("id", "date", "time", "amount", "category", "note")
        self.tree = ttk.Treeview(box, columns=cols, show="headings", style="App.Treeview", selectmode="extended")
        for col, w, anc in zip(cols, (90, 105, 70, 90, 170, 300), ("w", "w", "w", "e", "w", "w")):
            self.tree.heading(col, text=col.upper())
            self.tree.column(col, width=w, anchor=anc)
        self.tree.tag_configure("alt", background=t["row_alt"])
        sb = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview, style="App.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, padx=2, pady=2)
        self.h_count = self._label(p, "", "muted", bg=t["bg"])
        self.h_count.pack(anchor="w", pady=(8, 0))
        for v in (self.h_search, self.h_cat, self.h_date):
            v.trace_add("write", lambda *_: self._fill_history())
        self._fill_history()

    def _clear_filters(self):
        self.h_search.set(""); self.h_cat.set("All categories"); self.h_date.set("")

    def _fill_history(self):
        if not self.tree.winfo_exists():
            return
        kw, cat, d = self.h_search.get().strip().lower(), self.h_cat.get(), self.h_date.get().strip()
        rows = [e for e in reversed(self.entries)
                if (not kw or kw in e.note.lower() or kw in e.category.lower() or kw in e.entry_id.lower())
                and (cat == "All categories" or e.category == cat) and (not d or e.date == d)]
        self.tree.delete(*self.tree.get_children())
        for i, e in enumerate(rows):
            self.tree.insert("", "end", iid=e.entry_id, tags=("alt",) if i % 2 else (),
                             values=(e.entry_id, e.date, e.time, f"{e.amount_ml} ml", e.category, e.note))
        self.h_count.config(text=f"{len(rows)} of {len(self.entries)} entries · {sum(e.amount_ml for e in rows)} ml shown")

    def _delete_selected(self):
        ids = set(self.tree.selection())
        if not ids:
            return self.toast("Select one or more rows first.", "warn")
        if not messagebox.askyesno("Delete entries", f"Delete {len(ids)} selected entr{'y' if len(ids) == 1 else 'ies'}?"):
            return
        self.entries = [e for e in self.entries if e.entry_id not in ids]
        self._save()
        self._refresh_chip()
        self._fill_history()
        self.toast(f"Deleted {len(ids)} entr{'y' if len(ids) == 1 else 'ies'}", "warn")

    def _page_analytics(self, p):
        t = self.t
        target = self.cfg["daily_target_ml"]
        top = tk.Frame(p, bg=t["bg"])
        top.pack(fill="x", pady=(0, 12))
        self.a_days = tk.IntVar(value=14)
        for n in (7, 14, 30):
            b = self._btn(top, f"{n} days", lambda k=n: self._set_range(k), "primary" if n == 14 else "ghost", padx=14, pady=6)
            b.pack(side="left", padx=(0, 8))
        self._btn(top, "Export reports", self._export, "ghost", padx=14, pady=6).pack(side="right")
        self._btn(top, "Save Matplotlib chart", self._chart, "ghost", padx=14, pady=6).pack(side="right", padx=8)

        p.rowconfigure(1, weight=3); p.rowconfigure(2, weight=2); p.columnconfigure(0, weight=1)
        self.a_card = self._card(p)
        self.a_card.pack(fill="both", expand=True, pady=(0, 12))
        self._label(self.a_card, "Daily intake vs goal", "h2").pack(anchor="w", padx=20, pady=(14, 0))
        self.a_cv = tk.Canvas(self.a_card, bg=t["card"], highlightthickness=0, height=220)
        self.a_cv.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        self.a_cv.bind("<Configure>", lambda _e: self._redraw_analytics())

        lower = tk.Frame(p, bg=t["bg"])
        lower.pack(fill="both", expand=True)
        lower.columnconfigure((0, 1), weight=1, uniform="x")
        cat_card = self._card(lower)
        cat_card.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self._label(cat_card, "By category", "h2").pack(anchor="w", padx=20, pady=(14, 0))
        totals = {c: 0 for c in CATEGORIES}
        for e in self.entries:
            totals[e.category] = totals.get(e.category, 0) + e.amount_ml
        items = sorted(totals.items(), key=lambda kv: -kv[1])[:5]
        cv2 = tk.Canvas(cat_card, bg=t["card"], highlightthickness=0, height=190)
        cv2.pack(fill="both", expand=True, padx=20, pady=(8, 12))
        cv2.bind("<Configure>", lambda _e: self._draw_hbars(cv2, items))

        sum_card = self._card(lower)
        sum_card.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        self._label(sum_card, "Recent daily status", "h2").pack(anchor="w", padx=20, pady=(14, 6))
        for s in reversed(build_daily_summaries(self.entries, target)[-5:]):
            r = tk.Frame(sum_card, bg=t["card"])
            r.pack(fill="x", padx=20, pady=3)
            self._label(r, s.date, "body", width=11, anchor="w").pack(side="left")
            self._label(r, f"{s.total_ml} ml ({s.completion_pct:.0f}%)", "bold", width=16, anchor="w").pack(side="left")
            self._label(r, s.status.split(" (")[0], "small", fg=self._status_color(s.status)).pack(side="left")
        self._range = 14

    def _set_range(self, n):
        self._range = n
        self._redraw_analytics()

    def _redraw_analytics(self):
        if not self.a_cv.winfo_exists():
            return
        labels, vals = self._last_days(getattr(self, "_range", 14))
        self._draw_bars(self.a_cv, labels, vals, self.cfg["daily_target_ml"])

    def _chart(self):
        msg = plot_hydration_trends(build_daily_summaries(self.entries, self.cfg["daily_target_ml"]), show_plot=True)
        messagebox.showinfo("Visual analytics", msg)

    def _export(self):
        msg = export_reports(self.entries, build_daily_summaries(self.entries, self.cfg["daily_target_ml"]))
        self.toast("✓ " + msg)

    def _page_settings(self, p):
        t = self.t
        p.columnconfigure((0, 1), weight=1, uniform="s")
        goal = self._card(p)
        goal.grid(row=0, column=0, sticky="nsew", padx=(0, 7), pady=(0, 14))
        self._label(goal, "Hydration goal & reminders", "h2").pack(anchor="w", padx=20, pady=(16, 10))
        self.s_goal, self.s_int = tk.IntVar(value=self.cfg["daily_target_ml"]), tk.IntVar(value=self.cfg["reminder_interval_mins"])
        for text, var, lo, hi, step, unit in (("Daily target", self.s_goal, 500, 6000, 50, "ml"),
                                              ("Remind me every", self.s_int, 15, 240, 5, "min")):
            row = tk.Frame(goal, bg=t["card"])
            row.pack(fill="x", padx=20, pady=(4, 10))
            self._label(row, text, "body").pack(side="left")
            val = self._label(row, f"{var.get()} {unit}", "bold", fg=t["primary"])
            val.pack(side="right")
            tk.Scale(goal, from_=lo, to=hi, resolution=step, orient="horizontal", variable=var, showvalue=False,
                     bg=t["card"], fg=t["text"], troughcolor=t["track"], highlightthickness=0, bd=0, sliderrelief="flat",
                     activebackground=t["primary"], command=lambda v, l=val, u=unit: l.config(text=f"{int(float(v))} {u}")
                     ).pack(fill="x", padx=20)
        self._btn(goal, "Save settings", self._save_settings, "success").pack(anchor="w", padx=20, pady=20)

        data = self._card(p)
        data.grid(row=0, column=1, sticky="nsew", padx=(7, 0), pady=(0, 14))
        self._label(data, "Data tools", "h2").pack(anchor="w", padx=20, pady=(16, 4))
        self._label(data, "Import a CSV (date,time,amount_ml,category,note) or export your reports.", "muted").pack(anchor="w", padx=20)
        for text, cmd in (("Import CSV file…", self._import_csv), ("Export Markdown & audit log", self._export),
                          ("Generate Matplotlib chart", self._chart)):
            self._btn(data, text, cmd, "ghost").pack(anchor="w", padx=20, pady=(12, 0))
        tk.Frame(data, bg=t["card"], height=16).pack()

        about = self._card(p)
        about.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self._label(about, "About", "h2").pack(anchor="w", padx=20, pady=(16, 4))
        self._label(about, "HydroTrack – CampusSolve #31 Water Intake Reminder Log. Data lives in the data/ folder "
                    "(JSON + CSV). Use the theme toggle in the sidebar to switch between light and dark.", "muted",
                    wraplength=820, justify="left").pack(anchor="w", padx=20, pady=(0, 18))

    def _save_settings(self):
        self.cfg["daily_target_ml"] = int(self.s_goal.get())
        self.cfg["reminder_interval_mins"] = int(self.s_int.get())
        save_config(self.cfg)
        self._refresh_chip()
        self.toast("✓ Settings saved")

    def _import_csv(self):
        path = filedialog.askopenfilename(title="Choose CSV to import", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                                          initialfile=SAMPLE_IMPORT_PATH)
        if not path:
            return
        ok, errs = bulk_import_csv(path, self.entries)
        self.entries.sort(key=lambda e: (e.date, e.time))
        self._refresh_chip()
        detail = f"Imported {ok} valid row(s)."
        if errs:
            detail += f"\n\n{len(errs)} row(s) skipped:\n" + "\n".join(errs[:8])
        messagebox.showinfo("CSV import", detail)


def launch_gui():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # crisp text on HiDPI
        except Exception:
            pass
    root = tk.Tk()
    WaterTrackerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
