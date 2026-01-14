import tkinter as tk
from tkinter import ttk
import threading
import time
import random
import re
import math
from collections import deque
import queue

import serial
from serial.tools import list_ports

try:
    import pyperclip
    HAS_CLIPBOARD = True
except Exception:
    HAS_CLIPBOARD = False

BAUD = 115200

ANIM_CHAR_DELAY = 0.06
FPS_MS = 33

BUF_N = 140

BG_IDLE = "#0b0f1a"
BG_PRE  = "#101a2a"
BG_GEN  = "#1a1030"
BG_POST = "#0f1f16"

C_CYAN  = "#00ffff"
C_GREEN = "#66ff66"
C_PINK  = "#ff66ff"
C_RED   = "#ff4444"
C_AMBER = "#ffaa00"
C_GRAY  = "#a8b0c0"
C_WHITE = "#ffffff"

def list_serial_ports():
    return list(list_ports.comports())

def auto_find_microbit_port():
    ports = list_serial_ports()
    for p in ports:
        text = f"{p.description} {p.manufacturer or ''} {p.hwid}".lower()
        if "micro:bit" in text or "microbit" in text or "mbed" in text or "bbc" in text:
            return p.device
    if len(ports) == 1:
        return ports[0].device
    return None

def evaluate_strength(pw):
    length = len(pw)
    classes = sum([
        bool(re.search(r"[a-z]", pw)),
        bool(re.search(r"[A-Z]", pw)),
        bool(re.search(r"\d", pw)),
        bool(re.search(r"[^A-Za-z0-9]", pw))
    ])
    if length >= 14 and classes == 4:
        return "STRONG", "#00ff99"
    if length >= 12 and classes >= 3:
        return "GOOD", "#66ff66"
    if length >= 10 and classes >= 2:
        return "FAIR", "#ffaa00"
    return "WEAK", "#ff4444"

def clamp(x, a, b):
    return a if x < a else (b if x > b else x)

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Micro:bit Password Tool + Sensor Telemetry (Animated)")
        self.root.geometry("980x560")
        self.root.configure(bg=BG_IDLE)

        self.q = queue.Queue()

        self.ser = None
        self.port = None

        self.gen_state = "IDLE"
        self.state_ts = time.time()

        self.ax = 0
        self.ay = 0
        self.az = 0
        self.last_pw = ""
        self.last_strength = ("", C_GRAY)

        self.ax_buf = deque([0]*BUF_N, maxlen=BUF_N)
        self.ay_buf = deque([0]*BUF_N, maxlen=BUF_N)
        self.az_buf = deque([0]*BUF_N, maxlen=BUF_N)
        self.mag_buf = deque([0]*BUF_N, maxlen=BUF_N)

        self.build_ui()
        self.connect_serial()
        self.root.after(FPS_MS, self.ui_tick)

    def build_ui(self):
        top = tk.Frame(self.root, bg=BG_IDLE)
        top.pack(fill="x", padx=14, pady=10)

        self.title_lbl = tk.Label(top, text="MICRO:BIT PASSWORD VAULT + LIVE SENSOR SIMULATION",
                                  font=("Consolas", 18, "bold"), fg=C_CYAN, bg=BG_IDLE)
        self.title_lbl.pack(side="left")

        self.status_lbl = tk.Label(top, text="Disconnected", font=("Consolas", 10, "bold"),
                                   fg=C_RED, bg=BG_IDLE)
        self.status_lbl.pack(side="right")

        body = tk.Frame(self.root, bg=BG_IDLE)
        body.pack(fill="both", expand=True, padx=14, pady=8)

        left = tk.Frame(body, bg=BG_IDLE)
        left.pack(side="left", fill="both", expand=False)

        right = tk.Frame(body, bg=BG_IDLE)
        right.pack(side="right", fill="both", expand=True, padx=(12,0))

        self.pw_lbl = tk.Label(left, text="WAITING...", font=("Consolas", 30, "bold"),
                               fg=C_WHITE, bg=BG_IDLE, width=18, anchor="w")
        self.pw_lbl.pack(pady=(6,10), padx=6)

        self.str_lbl = tk.Label(left, text="STRENGTH: -", font=("Consolas", 14, "bold"),
                                fg=C_GRAY, bg=BG_IDLE, anchor="w")
        self.str_lbl.pack(pady=(0,14), padx=6, fill="x")

        btns = tk.Frame(left, bg=BG_IDLE)
        btns.pack(pady=6, padx=6, fill="x")

        self.gen_btn = tk.Button(btns, text="GENERATE (GEN)", font=("Consolas", 13, "bold"),
                                 bg="#00ffaa", fg="#000000", command=self.send_gen)
        self.gen_btn.pack(fill="x", pady=(0,8))

        self.telem_on = True
        self.telem_btn = tk.Button(btns, text="Telemetry: ON", font=("Consolas", 12, "bold"),
                                   bg="#334455", fg=C_WHITE, command=self.toggle_telem)
        self.telem_btn.pack(fill="x", pady=(0,8))

        self.len_var = tk.StringVar(value="12")
        len_row = tk.Frame(btns, bg=BG_IDLE)
        len_row.pack(fill="x")
        tk.Label(len_row, text="Length:", font=("Consolas", 11, "bold"),
                 fg=C_GRAY, bg=BG_IDLE).pack(side="left")
        self.len_entry = tk.Entry(len_row, textvariable=self.len_var, font=("Consolas", 11),
                                  bg="#0f1525", fg=C_WHITE, insertbackground=C_WHITE, width=6)
        self.len_entry.pack(side="left", padx=(8,8))
        tk.Button(len_row, text="SET (LEN:)", font=("Consolas", 11, "bold"),
                  bg="#6688ff", fg="#000000", command=self.send_len).pack(side="left", fill="x", expand=True)

        tip = ("Use A/B to change length on micro:bit. Press A+B to generate.\n"
               "This GUI animates sensor changes BEFORE/DURING/AFTER generation.")
        self.tip_lbl = tk.Label(left, text=tip, font=("Consolas", 10),
                                fg=C_GRAY, bg=BG_IDLE, justify="left")
        self.tip_lbl.pack(padx=6, pady=14, anchor="w")

        self.canvas = tk.Canvas(right, bg="#070a12", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

    def connect_serial(self):
        self.port = auto_find_microbit_port()
        if not self.port:
            ports = list_serial_ports()
            if not ports:
                self.status_lbl.config(text="No COM ports found (plug micro:bit)", fg=C_RED)
                return
            msg = "Pick COM port: " + ", ".join([p.device for p in ports])
            self.status_lbl.config(text=msg, fg=C_AMBER)
            self.port = ports[0].device

        try:
            self.ser = serial.Serial(self.port, BAUD, timeout=0.5)
            self.status_lbl.config(text=f"Connected: {self.port}", fg=C_GREEN)
            t = threading.Thread(target=self.read_loop, daemon=True)
            t.start()
        except Exception as e:
            self.status_lbl.config(text=str(e), fg=C_RED)

    def send_line(self, s):
        try:
            if self.ser:
                if not s.endswith("\n"):
                    s += "\n"
                self.ser.write(s.encode("utf-8", errors="ignore"))
        except Exception:
            pass

    def send_gen(self):
        self.send_line("GEN")

    def send_len(self):
        try:
            n = int(self.len_var.get().strip())
        except Exception:
            return
        n = clamp(n, 8, 24)
        self.len_var.set(str(n))
        self.send_line(f"LEN:{n}")

    def toggle_telem(self):
        self.telem_on = not self.telem_on
        if self.telem_on:
            self.telem_btn.config(text="Telemetry: ON", bg="#334455")
            self.send_line("TELEM:ON")
        else:
            self.telem_btn.config(text="Telemetry: OFF", bg="#552233")
            self.send_line("TELEM:OFF")

    def read_loop(self):
        while True:
            try:
                raw = self.ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                self.q.put(line)
            except Exception:
                time.sleep(0.2)

    def set_state(self, st):
        self.gen_state = st
        self.state_ts = time.time()
        if st == "IDLE":
            self.root.configure(bg=BG_IDLE)
        elif st == "PRE":
            self.root.configure(bg=BG_PRE)
        elif st == "GEN":
            self.root.configure(bg=BG_GEN)
        elif st == "POST":
            self.root.configure(bg=BG_POST)

        bg = self.root.cget("bg")
        self.title_lbl.config(bg=bg)
        self.status_lbl.config(bg=bg)
        self.pw_lbl.config(bg=bg)
        self.str_lbl.config(bg=bg)
        self.tip_lbl.config(bg=bg)

    def animate_password(self, pw):
        self.last_pw = pw
        self.pw_lbl.config(text="")
        self.str_lbl.config(text="STRENGTH: ANALYZING...", fg=C_GRAY)

        def run():
            shown = [" "] * len(pw)
            charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-_=+[]{};:,.?/"
            for i in range(len(pw)):
                for _ in range(9):
                    shown[i] = random.choice(charset)
                    self.root.after(0, lambda s="".join(shown): self.pw_lbl.config(text=s))
                    time.sleep(ANIM_CHAR_DELAY)
                shown[i] = pw[i]
                self.root.after(0, lambda s="".join(shown): self.pw_lbl.config(text=s))

            label, color = evaluate_strength(pw)
            self.last_strength = (label, color)
            self.root.after(0, lambda: self.str_lbl.config(text=f"STRENGTH: {label}", fg=color))

            if HAS_CLIPBOARD:
                try:
                    pyperclip.copy(pw)
                except Exception:
                    pass

        threading.Thread(target=run, daemon=True).start()

    def consume_serial_queue(self):
        try:
            while True:
                line = self.q.get_nowait()

                if line.startswith("S:"):
                    try:
                        payload = line[2:]
                        parts = payload.split(",")
                        ax = int(parts[1]); ay = int(parts[2]); az = int(parts[3])
                        self.ax, self.ay, self.az = ax, ay, az
                        mag = math.sqrt(ax*ax + ay*ay + az*az)
                        self.ax_buf.append(ax)
                        self.ay_buf.append(ay)
                        self.az_buf.append(az)
                        self.mag_buf.append(mag)
                    except Exception:
                        pass

                elif line.startswith("EV:"):
                    st = line[3:].strip().upper()
                    if st in ("IDLE", "PRE", "GEN", "POST"):
                        self.set_state(st)

                elif line.startswith("PW:"):
                    pw = line[3:]
                    self.animate_password(pw)

                elif line.startswith("LN:"):
                    try:
                        self.len_var.set(line[3:].strip())
                    except Exception:
                        pass

        except queue.Empty:
            return

    def draw(self):
        c = self.canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()

        bg = "#070a12"
        c.create_rectangle(0, 0, w, h, fill=bg, outline="")

        header = f"STATE: {self.gen_state}   ACCEL: ({self.ax},{self.ay},{self.az})"
        c.create_text(14, 16, text=header, font=("Consolas", 12, "bold"), fill=C_GRAY, anchor="w")

        state_age = time.time() - self.state_ts
        pulse = 0.5 + 0.5 * math.sin(time.time() * (5.0 if self.gen_state == "GEN" else 2.5))

        if self.gen_state == "IDLE":
            glow = "#0c2b2b"
        elif self.gen_state == "PRE":
            glow = "#203a6b"
        elif self.gen_state == "GEN":
            glow = "#5a2b8a"
        else:
            glow = "#1f5a3a"

        accel_mag = self.mag_buf[-1] if len(self.mag_buf) else 0
        jitter = int(clamp((accel_mag / 2500.0) * 14.0, 0, 14))
        jx = random.randint(-jitter, jitter) if jitter > 0 else 0
        jy = random.randint(-jitter, jitter) if jitter > 0 else 0

        mb_x = 60 + jx
        mb_y = 60 + jy
        mb_w = 250
        mb_h = 240

        c.create_rectangle(mb_x-8, mb_y-8, mb_x+mb_w+8, mb_y+mb_h+8, fill=glow, outline="", stipple="gray25")
        c.create_rectangle(mb_x, mb_y, mb_x+mb_w, mb_y+mb_h, fill="#0e1424", outline="#1e2b44", width=2)

        c.create_text(mb_x+10, mb_y+16, text="VIRTUAL micro:bit", font=("Consolas", 11, "bold"), fill=C_CYAN, anchor="w")

        grid_x0 = mb_x + 55
        grid_y0 = mb_y + 50
        cell = 28
        rad = 9

        led_intensity = pulse
        if self.gen_state == "IDLE":
            led_intensity = 0.25 + 0.20 * pulse
        elif self.gen_state == "PRE":
            led_intensity = 0.35 + 0.35 * pulse
        elif self.gen_state == "GEN":
            led_intensity = 0.60 + 0.40 * pulse
        else:
            led_intensity = 0.30 + 0.25 * pulse

        led_color = C_CYAN if self.gen_state != "GEN" else C_PINK
        off_color = "#111827"

        for r in range(5):
            for col in range(5):
                cx = grid_x0 + col * cell
                cy = grid_y0 + r * cell
                if (r + col) % 2 == 0:
                    use = led_intensity
                else:
                    use = 0.2 + 0.6 * led_intensity

                def blend(col_hex, t):
                    col_hex = col_hex.lstrip("#")
                    r0 = int(col_hex[0:2], 16)
                    g0 = int(col_hex[2:4], 16)
                    b0 = int(col_hex[4:6], 16)
                    r1 = int(off_color[1:3], 16)
                    g1 = int(off_color[3:5], 16)
                    b1 = int(off_color[5:7], 16)
                    rr = int(r1 + (r0 - r1) * t)
                    gg = int(g1 + (g0 - g1) * t)
                    bb = int(b1 + (b0 - b1) * t)
                    return f"#{rr:02x}{gg:02x}{bb:02x}"

                fill = blend(led_color, clamp(use, 0.0, 1.0))
                c.create_oval(cx-rad, cy-rad, cx+rad, cy+rad, fill=fill, outline="")

        c.create_text(mb_x+18, mb_y+210, text="A  B", font=("Consolas", 14, "bold"), fill=C_GRAY, anchor="w")
        c.create_oval(mb_x+36, mb_y+224, mb_x+58, mb_y+246, fill="#19233a", outline="#2a3a5a")
        c.create_oval(mb_x+76, mb_y+224, mb_x+98, mb_y+246, fill="#19233a", outline="#2a3a5a")

        c.create_text(mb_x+150, mb_y+210, text="Shake / Noise -> Entropy", font=("Consolas", 10), fill=C_GRAY, anchor="w")

        dash_x0 = 340
        dash_y0 = 55
        dash_w = w - dash_x0 - 20
        dash_h = h - dash_y0 - 20
        c.create_rectangle(dash_x0, dash_y0, dash_x0+dash_w, dash_y0+dash_h, fill="#0a1020", outline="#1e2b44", width=2)
        c.create_text(dash_x0+12, dash_y0+18, text="SENSOR TELEMETRY (LIVE)", font=("Consolas", 12, "bold"), fill=C_CYAN, anchor="w")

        bar_x = dash_x0 + 30
        bar_y = dash_y0 + 60
        bar_h = 190
        bar_w = 34
        gap = 36

        def draw_bar(label, val, x, color):
            v = clamp(val / 2048.0, -1.0, 1.0)
            mid = bar_y + bar_h/2
            y1 = mid
            y2 = mid - v*(bar_h/2)
            c.create_rectangle(x, bar_y, x+bar_w, bar_y+bar_h, fill="#0f1525", outline="#243454")
            c.create_line(x, mid, x+bar_w, mid, fill="#243454")
            c.create_rectangle(x+4, min(y1,y2), x+bar_w-4, max(y1,y2), fill=color, outline="")
            c.create_text(x+bar_w/2, bar_y+bar_h+18, text=label, font=("Consolas", 11, "bold"), fill=C_GRAY)
            c.create_text(x+bar_w/2, bar_y-14, text=str(val), font=("Consolas", 10), fill=C_GRAY)

        draw_bar("AX", self.ax, bar_x, "#66aaff")
        draw_bar("AY", self.ay, bar_x + (bar_w+gap), "#66ffcc")
        draw_bar("AZ", self.az, bar_x + 2*(bar_w+gap), "#ffaa66")

        mag = self.mag_buf[-1] if len(self.mag_buf) else 0.0
        c.create_text(bar_x, bar_y+bar_h+48, text=f"Accel magnitude: {mag:.0f}", font=("Consolas", 10, "bold"), fill=C_GRAY, anchor="w")



        phase_help = "PRE: entropy mix  |  GEN: password emit  |  POST: settle"
        c.create_text(dash_x0+12, dash_y0+dash_h-12, text=phase_help, font=("Consolas", 10), fill=C_GRAY, anchor="w")

    def ui_tick(self):
        self.consume_serial_queue()
        self.draw()
        self.root.after(FPS_MS, self.ui_tick)

def main():
    root = tk.Tk()
    app = App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
