#!/usr/bin/env python3
"""Mac blink tracker: OpenCV webcam blinks, log, CSV export, reminders."""
from __future__ import annotations

import csv
import sqlite3
import subprocess
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

import os as _os
_HERE = Path(__file__).resolve().parent
if _os.environ.get("BLINK_TRACKER_HOME"):
    APP_DIR = Path(_os.environ["BLINK_TRACKER_HOME"]).expanduser()
    APP_DIR.mkdir(parents=True, exist_ok=True)
else:
    APP_DIR = _HERE
DB_PATH = APP_DIR / "blinks.db"
CONFIG_PATH = APP_DIR / "config.txt"

# Blink heuristic: closed eyes for N frames, then reopen
CLOSED_RATIO = 0.38  # eye height/width below this ≈ closed
CONSEC_CLOSED = 2
MIN_GAP_SEC = 0.3


def frontmost_app() -> str:
    try:
        out = subprocess.check_output(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get name of first application process whose frontmost is true',
            ],
            text=True,
            timeout=2,
        )
        return out.strip() or "Unknown"
    except Exception:
        return "Unknown"


def notify(title: str, body: str) -> None:
    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    safe_body = body.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.Popen(
        ["osascript", "-e", f'display notification "{safe_body}" with title "{safe_title}"']
    )


def load_reminder_seconds() -> int:
    """Config stores seconds. Old plain ints were minutes → *60."""
    if CONFIG_PATH.exists():
        raw = CONFIG_PATH.read_text().strip()
        try:
            if raw.startswith("sec="):
                return max(5, int(raw.split("=", 1)[1].split("|")[0]))
            return max(1, int(raw)) * 60
        except Exception:
            pass
    return 20 * 60


def save_reminder_seconds(seconds: int) -> None:
    CONFIG_PATH.write_text(f"sec={max(5, int(seconds))}")


class Store:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        with self._connect() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS blinks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    app TEXT NOT NULL,
                    fidelity REAL NOT NULL
                )
                """
            )

    def _connect(self):
        return sqlite3.connect(self.path, check_same_thread=False)

    def add(self, ts: str, app: str, fidelity: float) -> None:
        with self._lock, self._connect() as c:
            c.execute(
                "INSERT INTO blinks (ts, app, fidelity) VALUES (?, ?, ?)",
                (ts, app, float(fidelity)),
            )

    def recent(self, limit: int = 300):
        with self._lock, self._connect() as c:
            rows = c.execute(
                "SELECT ts, app, fidelity FROM blinks ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return list(reversed(rows))

    def range_rows(self, start: str, end: str):
        with self._lock, self._connect() as c:
            return c.execute(
                """
                SELECT ts, app, fidelity FROM blinks
                WHERE ts >= ? AND ts <= ?
                ORDER BY ts ASC
                """,
                (start, end),
            ).fetchall()

    def count(self) -> int:
        with self._lock, self._connect() as c:
            return int(c.execute("SELECT COUNT(*) FROM blinks").fetchone()[0])


class BlinkDetector:
    """Face + eye cascades; blink when both eyes look closed then open."""

    def __init__(self):
        cascade_dir = Path(cv2.data.haarcascades)
        self.face = cv2.CascadeClassifier(str(cascade_dir / "haarcascade_frontalface_default.xml"))
        self.eyes = cv2.CascadeClassifier(str(cascade_dir / "haarcascade_eye_tree_eyeglasses.xml"))
        self.closed_frames = 0
        self.was_closed = False

    def process(self, frame_bgr):
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        faces = self.face.detectMultiScale(gray, 1.1, 5, minSize=(120, 120))
        fidelity = 0.0
        closed = False
        label = "No face"

        if len(faces) > 0:
            # largest face
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            cv2.rectangle(frame_bgr, (x, y), (x + w, y + h), (0, 180, 0), 2)
            roi_gray = gray[y : y + h, x : x + w]
            roi_color = frame_bgr[y : y + h, x : x + w]
            eyes = self.eyes.detectMultiScale(roi_gray, 1.1, 8, minSize=(25, 15))
            # keep upper-half eyes only
            eyes = [e for e in eyes if e[1] + e[3] // 2 < h * 0.55]
            eyes = sorted(eyes, key=lambda e: e[0])[:2]

            ratios = []
            for ex, ey, ew, eh in eyes:
                cv2.rectangle(roi_color, (ex, ey), (ex + ew, ey + eh), (255, 180, 0), 1)
                ratios.append(eh / max(ew, 1))

            if len(ratios) >= 2:
                avg = float(np.mean(ratios))
                closed = avg < CLOSED_RATIO
                # fidelity: how clearly closed (lower ratio → higher)
                fidelity = max(0.0, min(1.0, (CLOSED_RATIO - avg) / CLOSED_RATIO + 0.45))
                label = f"eyes open  r={avg:.2f}" if not closed else f"eyes closed  r={avg:.2f}"
            elif len(ratios) == 1:
                avg = float(ratios[0])
                closed = avg < CLOSED_RATIO
                fidelity = max(0.0, min(1.0, (CLOSED_RATIO - avg) / CLOSED_RATIO + 0.35))
                label = f"1 eye  r={avg:.2f}"
            else:
                # no eyes found while face present often means blink mid-frame
                closed = True
                fidelity = 0.55
                label = "face, no eyes (maybe blink)"

        blink = False
        if closed:
            self.closed_frames += 1
            if self.closed_frames >= CONSEC_CLOSED:
                self.was_closed = True
        else:
            if self.was_closed and self.closed_frames >= CONSEC_CLOSED:
                blink = True
            self.closed_frames = 0
            self.was_closed = False

        cv2.putText(
            frame_bgr,
            label,
            (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 200, 0) if not closed else (0, 140, 255),
            2,
        )
        return blink, fidelity, frame_bgr


class BlinkApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Blink Tracker")
        self.geometry("900x650")
        self.minsize(740, 520)

        self.store = Store(DB_PATH)
        self.detector = BlinkDetector()
        self.reminder_sec = load_reminder_seconds()
        self.running = False
        self.cap = None
        self.worker = None
        self.photo = None
        self.last_blink_at = time.time()
        self.session_blinks = 0
        self._preview = None

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(1000, self._tick_reminder)
        self.after(400, self.refresh_log)
        self.after(300, self.start_camera)

    def _build_ui(self):
        top = ttk.Frame(self, padding=8)
        top.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(top)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.video = ttk.Label(left, text="Starting camera…")
        self.video.pack(fill=tk.BOTH, expand=True)

        status = ttk.Frame(left)
        status.pack(fill=tk.X, pady=6)
        self.status_var = tk.StringVar(value="Idle")
        self.count_var = tk.StringVar(value=f"Blinks: 0 (all-time {self.store.count()})")
        ttk.Label(status, textvariable=self.status_var).pack(side=tk.LEFT)
        ttk.Label(status, textvariable=self.count_var).pack(side=tk.RIGHT)

        btns = ttk.Frame(left)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="Start", command=self.start_camera).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Stop", command=self.stop_camera).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Config", command=self.open_config).pack(side=tk.RIGHT, padx=2)

        right = ttk.Frame(top, padding=(8, 0, 0, 0))
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        ttk.Label(right, text="Blink log (time · main app · fidelity)").pack(anchor=tk.W)
        cols = ("time", "app", "fidelity")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", height=24)
        self.tree.heading("time", text="Time")
        self.tree.heading("app", text="Main app")
        self.tree.heading("fidelity", text="Fidelity")
        self.tree.column("time", width=150)
        self.tree.column("app", width=170)
        self.tree.column("fidelity", width=80, anchor=tk.E)
        scroll = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        tip = ttk.Label(
            self,
            text="Allow Camera. For correct app names: System Settings → Privacy & Security → Accessibility → enable Terminal.",
            wraplength=860,
            padding=(8, 0, 8, 8),
        )
        tip.pack(fill=tk.X)

    def start_camera(self):
        if self.running:
            return
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror(
                "Camera",
                "Could not open webcam.\n\nSystem Settings → Privacy & Security → Camera\n→ enable Terminal (or Python).",
            )
            self.cap = None
            return
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.running = True
        self.status_var.set("Watching… blink naturally")
        self.worker = threading.Thread(target=self._loop, daemon=True)
        self.worker.start()

    def stop_camera(self):
        self.running = False
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        self.status_var.set("Stopped")

    def _loop(self):
        while self.running and self.cap is not None:
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.05)
                continue
            frame = cv2.flip(frame, 1)
            blink, fidelity, frame = self.detector.process(frame)
            if blink:
                self._on_blink(fidelity)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            img.thumbnail((270, 200))
            imgtk = ImageTk.PhotoImage(img)
            self._preview = imgtk
            self.after(0, self._show_frame, imgtk)
            time.sleep(0.03)

    def _show_frame(self, imgtk):
        self.video.configure(image=imgtk, text="")
        self.photo = imgtk

    def _on_blink(self, fidelity: float):
        now = time.time()
        if now - self.last_blink_at < MIN_GAP_SEC:
            return
        self.last_blink_at = now
        self.session_blinks += 1
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        app = frontmost_app()
        fid = round(float(fidelity), 3)
        self.store.add(ts, app, fid)
        self.after(0, self._ui_after_blink, ts, app, fid)

    def _ui_after_blink(self, ts, app, fid):
        self.count_var.set(f"Blinks: {self.session_blinks} (all-time {self.store.count()})")
        self.status_var.set(f"Blink @ {ts}")
        self.tree.insert("", 0, values=(ts, app, f"{fid:.3f}"))

    def refresh_log(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for ts, app, fid in reversed(self.store.recent(400)):
            self.tree.insert("", 0, values=(ts, app, f"{float(fid):.3f}"))
        self.count_var.set(f"Blinks: {self.session_blinks} (all-time {self.store.count()})")

    def _tick_reminder(self):
        secs = self.reminder_sec
        if secs > 0 and self.running:
            idle = time.time() - self.last_blink_at
            if idle >= secs:
                notify("Blink reminder", f"No blink logged for {secs}s. Look away and blink.")
                self.last_blink_at = time.time()
        self.after(2000, self._tick_reminder)

    def open_config(self):
        win = tk.Toplevel(self)
        win.title("Config")
        win.geometry("440x300")
        win.transient(self)
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Remind me every (seconds)").grid(row=0, column=0, sticky=tk.W)
        rem = tk.StringVar(value=str(self.reminder_sec))
        ttk.Entry(frm, textvariable=rem, width=8).grid(row=0, column=1, sticky=tk.W, padx=6)

        ttk.Label(frm, text="CSV from (YYYY-MM-DD HH:MM:SS)").grid(row=1, column=0, sticky=tk.W, pady=(12, 0))
        start = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d 00:00:00"))
        ttk.Entry(frm, textvariable=start, width=22).grid(row=1, column=1, sticky=tk.W, padx=6, pady=(12, 0))

        ttk.Label(frm, text="CSV to (YYYY-MM-DD HH:MM:SS)").grid(row=2, column=0, sticky=tk.W, pady=(8, 0))
        end = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d 23:59:59"))
        ttk.Entry(frm, textvariable=end, width=22).grid(row=2, column=1, sticky=tk.W, padx=6, pady=(8, 0))

        def save_rem():
            try:
                s = max(5, int(rem.get()))
            except ValueError:
                messagebox.showerror("Config", "Seconds must be a number (min 5).", parent=win)
                return
            self.reminder_sec = s
            save_reminder_seconds(s)
            messagebox.showinfo("Config", f"Reminder every {s} seconds.", parent=win)

        def export_csv():
            path = filedialog.asksaveasfilename(
                parent=win,
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv")],
                initialfile=f"blinks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            )
            if not path:
                return
            rows = self.store.range_rows(start.get().strip(), end.get().strip())
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["time", "main_app", "fidelity"])
                w.writerows(rows)
            messagebox.showinfo("CSV", f"Saved {len(rows)} rows:\n{path}", parent=win)

        def test_notify():
            notify("Blink reminder", "Test notification from Blink Tracker.")

        ttk.Button(frm, text="Save reminder", command=save_rem).grid(row=3, column=0, pady=16, sticky=tk.W)
        ttk.Button(frm, text="Download CSV", command=export_csv).grid(row=3, column=1, pady=16, sticky=tk.W)
        ttk.Button(frm, text="Test notification", command=test_notify).grid(row=4, column=0, sticky=tk.W)

    def on_close(self):
        self.stop_camera()
        self.destroy()


if __name__ == "__main__":
    BlinkApp().mainloop()
