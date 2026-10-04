#!/usr/bin/env python3
"""
Evocalc 3 — Material You calculator.
Pure Python + tkinter. Zero dependencies. No eval().

Hard fork of d9341944-bot/Evolutionary-calculator (MIT).

Highlights
  * Material 3 look: tonal palettes generated from a seed colour, light/dark
  * Pill buttons that morph into squircles when pressed, with state layers
  * Live result preview while you type, snackbar, shake on errors
  * Scientific panel (sin cos tan ln √ ^ π !), DEG / RAD switch
  * Calculation history drawer, persisted between launches
  * Full keyboard support, Ctrl+C / Ctrl+V, click the display to copy
  * Safe AST-based evaluator instead of eval()

Keyboard
  0-9 . + - * / ^ % ! ( )   input        Enter / =   evaluate
  Backspace                 delete       Esc / Del   clear (Esc closes history)
  p = π    r = √(    c = clear           Ctrl+C / Ctrl+V   copy / paste
"""

import ast
import colorsys
import json
import math
import operator
import os
import re
import sys
import tkinter as tk
from tkinter import font as tkfont

APP = "Evocalc"
CONFIG = os.path.join(os.path.expanduser("~"), ".evocalc.json")

HUES = [("Violet", 0.74), ("Blue", 0.60), ("Teal", 0.47), ("Green", 0.33),
        ("Amber", 0.11), ("Coral", 0.02), ("Rose", 0.93)]


# ═════════════════════════════════════════════════════════════ colour system ══
def _hex(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h % 1.0, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def _rgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def blend(a, b, t):
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(_rgb(a), _rgb(b)))


def scheme(hue, dark):
    """Tiny Material-3-style tonal scheme from a seed hue."""
    h, t = hue, hue + 0.12
    if dark:
        return dict(
            bg=_hex(h, .14, .07), mid=_hex(h, .14, .12), high=_hex(h, .14, .17),
            on_surface=_hex(h, .12, .91), variant=_hex(h, .10, .66),
            primary=_hex(h, .75, .80), on_primary=_hex(h, .80, .16),
            primary_c=_hex(h, .55, .30), on_primary_c=_hex(h, .85, .90),
            secondary_c=_hex(h, .25, .27), on_secondary_c=_hex(h, .40, .90),
            tertiary_c=_hex(t, .35, .26), on_tertiary_c=_hex(t, .60, .90),
            error=_hex(0.0, .85, .78), inverse=_hex(h, .12, .90), on_inverse=_hex(h, .15, .14))
    return dict(
        bg=_hex(h, .45, .97), mid=_hex(h, .35, .93), high=_hex(h, .30, .89),
        on_surface=_hex(h, .20, .11), variant=_hex(h, .12, .38),
        primary=_hex(h, .65, .40), on_primary=_hex(h, .30, .99),
        primary_c=_hex(h, .85, .88), on_primary_c=_hex(h, .90, .14),
        secondary_c=_hex(h, .40, .85), on_secondary_c=_hex(h, .50, .14),
        tertiary_c=_hex(t, .55, .84), on_tertiary_c=_hex(t, .60, .14),
        error=_hex(0.0, .70, .42), inverse=_hex(h, .15, .20), on_inverse=_hex(h, .20, .95))


# ═══════════════════════════════════════════════════════════ safe evaluator ══
class CalcError(Exception):
    pass


_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod}
_UN = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _clean(v):
    return 0.0 if abs(v) < 1e-12 else v


def _fact(n):
    if n < 0 or abs(n - round(n)) > 1e-12:
        raise CalcError("Factorial needs a whole number")
    if n > 170:
        raise CalcError("Number too large")
    return float(math.factorial(int(round(n))))


def _funcs(deg):
    to_rad = (lambda x: math.radians(x)) if deg else (lambda x: x)

    def tan(x):
        if deg and abs(math.cos(math.radians(x))) < 1e-12:
            raise CalcError("Undefined")
        return _clean(math.tan(to_rad(x)))

    def sqrt(x):
        if x < 0:
            raise CalcError("Invalid input")
        return math.sqrt(x)

    def ln(x):
        if x <= 0:
            raise CalcError("Invalid input")
        return math.log(x)

    def log(x):
        if x <= 0:
            raise CalcError("Invalid input")
        return math.log10(x)

    return {"sin": lambda x: _clean(math.sin(to_rad(x))),
            "cos": lambda x: _clean(math.cos(to_rad(x))),
            "tan": tan, "sqrt": sqrt, "ln": ln, "log": log, "fact": _fact}


def _eval(node, F):
    if isinstance(node, ast.Expression):
        return _eval(node.body, F)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.Name) and node.id == "pi":
        return math.pi
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UN:
        return _UN[type(node.op)](_eval(node.operand, F))
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        a, b = _eval(node.left, F), _eval(node.right, F)
        if isinstance(node.op, ast.Pow) and abs(b) > 10000:
            raise CalcError("Number too large")
        try:
            r = _BIN[type(node.op)](a, b)
        except ZeroDivisionError:
            raise CalcError("Can’t divide by zero")
        except OverflowError:
            raise CalcError("Number too large")
        if isinstance(r, complex):
            raise CalcError("Invalid input")
        if math.isinf(r) or math.isnan(r):
            raise CalcError("Number too large")
        return r
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in F and len(node.args) == 1 and not node.keywords:
        return F[node.func.id](_eval(node.args[0], F))
    raise CalcError("Invalid expression")


def evaluate(expr, deg=True):
    s = expr.replace(" ", "")
    # percent: 200+10% -> 200+(200*10/100); otherwise x% -> x*(0.01)
    s = re.sub(r"(?<![\d.*/×÷^])(\d+(?:\.\d+)?)([+−])(\d+(?:\.\d+)?)%",
               lambda m: f"{m[1]}{m[2]}({m[1]}×{m[3]}÷100)", s)
    s = s.replace("%", "×(0.01)")
    # implicit multiplication: 2(3)  2π  3√(4)  (1+2)(3)  π2
    s = re.sub(r"(?<=[\d)π])(?=[(π√]|sin\(|cos\(|tan\(|ln\(|log\()", "×", s)
    s = re.sub(r"(?<=[)π])(?=[\d.])", "×", s)
    s = re.sub(r"(\d+(?:\.\d+)?)!", r"fact(\1)", s)
    s = (s.replace("×", "*").replace("÷", "/").replace("−", "-")
          .replace("^", "**").replace("π", "pi").replace("√", "sqrt"))
    try:
        tree = ast.parse(s, mode="eval")
        r = _eval(tree, _funcs(deg))
    except CalcError:
        raise
    except (SyntaxError, ValueError, TypeError, RecursionError, MemoryError):
        raise CalcError("Invalid expression")
    return r


def fmt(x):
    if x == int(x) and abs(x) < 1e15:
        s = str(int(x))
    else:
        s = f"{x:.10g}"
        if "e" in s:
            m, e = s.split("e")
            s = f"{m}×10^{int(e)}"
    return s.replace("-", "−")


# ═══════════════════════════════════════════════════════════════ UI widgets ══
def _rr(cv, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


class MButton(tk.Canvas):
    """Material button: pill shape, hover/press state layer, shape morph."""

    def __init__(self, master, text, command, bg, fg, base, font,
                 rest=0.5, w=60, h=50):
        super().__init__(master, width=w, height=h, bg=base, bd=0,
                         highlightthickness=0, cursor="hand2")
        self.text, self.command, self.bgc, self.fgc = text, command, bg, fg
        self.font, self.rest = font, rest
        self._frac, self._tfrac = rest, rest
        self._press, self._tpress = 0.0, 0.0
        self._hover, self._thover = 0.0, 0.0
        self._job = None
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._down)
        self.bind("<ButtonRelease-1>", self._up)

    # public
    def set_text(self, text):
        self.text = text
        self._draw()

    def recolor(self, bg, fg):
        self.bgc, self.fgc = bg, fg
        self._draw()

    def pulse(self):
        self._tpress, self._tfrac = 1.0, self.rest * 0.6
        self._go()
        self.after(110, self._unpulse)

    # events
    def _enter(self, _):
        self._thover = 1.0
        self._go()

    def _leave(self, _):
        self._thover, self._tpress, self._tfrac = 0.0, 0.0, self.rest
        self._go()

    def _down(self, _):
        self._tpress, self._tfrac = 1.0, self.rest * 0.6
        self._go()

    def _up(self, e):
        self._tpress, self._tfrac = 0.0, self.rest
        self._go()
        if 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height():
            self.command()          # last: it may destroy this widget

    def _unpulse(self):
        try:
            self._tpress, self._tfrac = 0.0, self.rest
            self._go()
        except tk.TclError:
            pass

    # animation
    def _go(self):
        if self._job is None:
            self._job = self.after(0, self._tick)

    def _tick(self):
        try:
            done = True
            for name, tgt in (("_frac", self._tfrac), ("_press", self._tpress),
                              ("_hover", self._thover)):
                cur = getattr(self, name)
                if abs(tgt - cur) > 0.01:
                    setattr(self, name, cur + (tgt - cur) * 0.38)
                    done = False
                else:
                    setattr(self, name, tgt)
            self._draw()
            self._job = None if done else self.after(16, self._tick)
        except tk.TclError:
            self._job = None

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 6 or h < 6:
            return
        pad = 2
        s = 1 - 0.035 * self._press
        iw, ih = (w - 2 * pad) * s, (h - 2 * pad) * s
        x1, y1 = (w - iw) / 2, (h - ih) / 2
        r = min(iw, ih) / 2 * self._frac
        fill = blend(self.bgc, self.fgc, 0.08 * self._hover + 0.12 * self._press)
        _rr(self, x1, y1, x1 + iw, y1 + ih, r, fill=fill, outline="")
        self.create_text(w / 2, h / 2, text=self.text, fill=self.fgc, font=self.font)


class Card(tk.Canvas):
    """Rounded surface that hosts an inner Frame."""

    def __init__(self, master, fill, base, r=28, pad=14):
        super().__init__(master, bg=base, bd=0, highlightthickness=0)
        self.fill, self.r, self.pad = fill, r, pad
        self.inner = tk.Frame(self, bg=fill)
        self.win = self.create_window(pad, pad, anchor="nw", window=self.inner)
        self.bind("<Configure>", self._cfg)

    def _cfg(self, e):
        self.delete("card")
        _rr(self, 1, 1, e.width - 1, e.height - 1, self.r, fill=self.fill, outline="", tags="card")
        self.tag_lower("card")
        self.itemconfigure(self.win, width=max(1, e.width - 2 * self.pad),
                           height=max(1, e.height - 2 * self.pad))


# ═══════════════════════════════════════════════════════════════════ layout ══
MAIN = [
    [("AC", "act"), ("( )", "act"), ("%", "act"), ("÷", "op")],
    [("7", "num"), ("8", "num"), ("9", "num"), ("×", "op")],
    [("4", "num"), ("5", "num"), ("6", "num"), ("−", "op")],
    [("1", "num"), ("2", "num"), ("3", "num"), ("+", "op")],
    [("⌫", "act"), ("0", "num"), (".", "num"), ("=", "eq")],
]
SCI = [
    [("sin", "sci"), ("cos", "sci"), ("tan", "sci"), ("ln", "sci")],
    [("√", "sci"), ("^", "sci"), ("π", "sci"), ("!", "sci")],
]
OPS = "+−×÷^"
FUNCS = {"sin": "sin(", "cos": "cos(", "tan": "tan(", "ln": "ln(", "√": "√("}
KEYMAP = {"+": "+", "-": "−", "*": "×", "x": "×", "X": "×", "/": "÷", "^": "^",
          "%": "%", "!": "!", ".": ".", ",": ".", "(": "(", ")": ")", "p": "π",
          "=": "=", "c": "AC", "C": "AC", "r": "√"}


def pick_font(root):
    have = set(tkfont.families(root))
    for f in ("Google Sans", "Product Sans", "Roboto", "Segoe UI Variable Display",
              "Segoe UI", "SF Pro Display", "Helvetica Neue", "Ubuntu",
              "Cantarell", "Noto Sans", "DejaVu Sans"):
        if f in have:
            return f
    return "TkDefaultFont"


class App:
    def __init__(self):
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass
        self.root = tk.Tk()
        self.root.title(APP)
        self.k = max(1.0, self.root.winfo_fpixels("1i") / 96.0)

        cfg = self._load()
        self.hue_i = int(cfg.get("hue", 0)) % len(HUES)
        self.dark = bool(cfg.get("dark", True))
        self.deg = bool(cfg.get("deg", True))
        self.sci = bool(cfg.get("sci", False))
        self.hist = [h for h in cfg.get("hist", [])
                     if isinstance(h, list) and len(h) == 2][-100:]

        self.expr, self.last, self.err, self.just = "", "", None, False
        self.buttons, self.chips, self.sci_btns = {}, {}, []
        self.panel = self.toast_lbl = self.toast_job = None

        self.fam = pick_font(self.root)
        self.meas = tkfont.Font(root=self.root, family=self.fam, size=52)

        k = self.k
        w, h = int(420 * k), int(800 * k)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        h = min(h, sh - int(80 * k))
        self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 3)}")
        self.root.minsize(int(390 * k), int(620 * k))

        self.build()
        self.root.bind("<Key>", self.on_key)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    # ─────────────────────────────────────────────────────────── persistence
    @staticmethod
    def _load():
        try:
            with open(CONFIG, encoding="utf-8") as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def save(self):
        try:
            with open(CONFIG, "w", encoding="utf-8") as f:
                json.dump({"hue": self.hue_i, "dark": self.dark, "deg": self.deg,
                           "sci": self.sci, "hist": self.hist[-100:]}, f, ensure_ascii=False)
        except OSError:
            pass

    def quit(self):
        self.save()
        self.root.destroy()

    # ───────────────────────────────────────────────────────────────── build
    def build(self):
        r, k = self.root, self.k
        for w in r.winfo_children():
            w.destroy()
        self.buttons, self.chips, self.sci_btns, self.panel = {}, {}, [], None
        self.toast_lbl = None
        c = self.c = scheme(HUES[self.hue_i][1], self.dark)
        r.configure(bg=c["bg"])
        r.grid_columnconfigure(0, weight=1)
        r.grid_rowconfigure(0, weight=0)
        r.grid_rowconfigure(1, weight=3)
        r.grid_rowconfigure(2, weight=4)

        # top bar -----------------------------------------------------------
        top = tk.Frame(r, bg=c["bg"])
        top.grid(row=0, column=0, sticky="ew", padx=int(18 * k), pady=(int(14 * k), 0))
        tk.Label(top, text=APP, bg=c["bg"], fg=c["variant"],
                 font=(self.fam, 13, "bold")).pack(side="left")
        specs = [("◉", self.next_hue, 40, "hue"), ("◐", self.toggle_dark, 40, "dark"),
                 ("History", self.show_history, 66, "hist"),
                 ("DEG" if self.deg else "RAD", self.toggle_deg, 50, "deg"),
                 ("ƒx", self.toggle_sci, 44, "sci")]
        for text, cmd, width, name in specs:
            bg, fg = ((c["primary_c"], c["on_primary_c"]) if name == "sci" and self.sci
                      else (c["high"], c["on_surface"]))
            b = MButton(top, text, cmd, bg, fg, c["bg"], (self.fam, 10, "bold"),
                        w=int(width * k), h=int(34 * k))
            b.pack(side="right", padx=int(3 * k))
            self.chips[name] = b

        # display -----------------------------------------------------------
        d = self.disp = tk.Frame(r, bg=c["bg"])
        d.grid(row=1, column=0, sticky="nsew")
        d.bind("<Configure>", lambda e: self.refresh())
        self.inner = tk.Frame(d, bg=c["bg"])
        self.inner.pack(side="bottom", fill="x", padx=int(22 * k), pady=(0, int(8 * k)))
        self.last_lbl = tk.Label(self.inner, anchor="e", bg=c["bg"], fg=c["variant"],
                                 font=(self.fam, 15))
        self.last_lbl.pack(fill="x")
        holder = tk.Frame(self.inner, bg=c["bg"], height=int(84 * k))
        holder.pack(fill="x")
        holder.pack_propagate(False)
        self.expr_lbl = tk.Label(holder, anchor="e", bg=c["bg"], fg=c["on_surface"],
                                 font=(self.fam, 52), cursor="hand2")
        self.expr_lbl.pack(side="bottom", fill="x")
        self.expr_lbl.bind("<Button-1>", lambda e: self.copy())
        self.prev_lbl = tk.Label(self.inner, anchor="e", bg=c["bg"], fg=c["primary"],
                                 font=(self.fam, 20), height=1)
        self.prev_lbl.pack(fill="x", pady=(int(2 * k), 0))

        # keypad ------------------------------------------------------------
        kf = self.kf = tk.Frame(r, bg=c["bg"])
        kf.grid(row=2, column=0, sticky="nsew", padx=int(12 * k),
                pady=(int(6 * k), int(14 * k)))
        for col in range(4):
            kf.grid_columnconfigure(col, weight=1, uniform="c")
        for ri, row in enumerate(SCI + MAIN):
            for ci, (key, kind) in enumerate(row):
                b = self.make_key(kf, key, kind)
                b.grid(row=ri, column=ci, sticky="nsew", padx=int(4 * k), pady=int(4 * k))
                self.buttons[key] = b
                if kind == "sci":
                    self.sci_btns.append(b)
        self.apply_sci()
        self.refresh()

    def make_key(self, parent, key, kind):
        c, k = self.c, self.k
        colors = {"num": (c["high"], c["on_surface"]),
                  "op": (c["secondary_c"], c["on_secondary_c"]),
                  "act": (c["tertiary_c"], c["on_tertiary_c"]),
                  "eq": (c["primary"], c["on_primary"]),
                  "sci": (c["mid"], c["primary"])}
        size = {"num": 22, "op": 24, "act": 18, "eq": 26, "sci": 16}[kind]
        rest = 0.36 if kind == "eq" else 0.5
        bg, fg = colors[kind]
        return MButton(parent, key, lambda: self.press(key), bg, fg, c["bg"],
                       (self.fam, size), rest=rest, w=int(60 * k), h=int(40 * k))

    def apply_sci(self):
        for ri in (0, 1):
            if self.sci:
                self.kf.grid_rowconfigure(ri, weight=1, uniform="r")
            else:
                self.kf.grid_rowconfigure(ri, weight=0, uniform="")
        for ri in range(2, 7):
            self.kf.grid_rowconfigure(ri, weight=1, uniform="r")
        for b in self.sci_btns:
            b.grid() if self.sci else b.grid_remove()

    # ───────────────────────────────────────────────────────────── toggles
    def toggle_sci(self):
        self.sci = not self.sci
        c = self.c
        self.chips["sci"].recolor(*((c["primary_c"], c["on_primary_c"]) if self.sci
                                    else (c["high"], c["on_surface"])))
        self.apply_sci()
        self.save()

    def toggle_deg(self):
        self.deg = not self.deg
        self.chips["deg"].set_text("DEG" if self.deg else "RAD")
        self.refresh()
        self.save()

    def toggle_dark(self):
        self.dark = not self.dark
        self.save()
        self.build()

    def next_hue(self):
        self.hue_i = (self.hue_i + 1) % len(HUES)
        self.save()
        self.build()
        self.toast(HUES[self.hue_i][0])

    # ───────────────────────────────────────────────────────────── display
    def refresh(self):
        try:
            c = self.c
            text = self.expr or "0"
            maxw = max(self.disp.winfo_width() - int(44 * self.k), 120)
            size = 52
            while True:
                self.meas.configure(size=size)
                if self.meas.measure(text) <= maxw or size <= 24:
                    break
                size -= 2
            if self.meas.measure(text) > maxw:
                while len(text) > 3 and self.meas.measure("…" + text) > maxw:
                    text = text[1:]
                text = "…" + text
            self.expr_lbl.configure(text=text, font=(self.fam, size),
                                    fg=c["on_surface"] if self.expr else blend(c["bg"], c["on_surface"], .35))
            if self.err:
                self.prev_lbl.configure(text=self.err, fg=c["error"])
            else:
                self.prev_lbl.configure(text=self.preview(), fg=c["primary"])
            self.last_lbl.configure(text=self.last)
        except tk.TclError:
            pass

    def preview(self):
        if self.just or not self.expr:
            return ""
        e = re.sub(r"(?:sin\(|cos\(|tan\(|ln\(|log\(|√\(|[+−×÷^(])+$", "", self.expr)
        if not e or not re.search(r"[+−×÷^%!()√π]|sin|cos|tan|ln", e.lstrip("−")):
            return ""
        e += ")" * max(0, e.count("(") - e.count(")"))
        try:
            res = fmt(evaluate(e, self.deg))
        except CalcError:
            return ""
        return "" if res == e else "= " + res

    def shake(self, i=0):
        offs = [10, -10, 7, -7, 4, -4, 0]
        if i >= len(offs):
            return
        try:
            o = int(offs[i] * self.k)
            base = int(22 * self.k)
            self.inner.pack_configure(padx=(base + o, base - o))
            self.root.after(34, lambda: self.shake(i + 1))
        except tk.TclError:
            pass

    def toast(self, msg):
        c, k = self.c, self.k
        try:
            if self.toast_lbl:
                self.toast_lbl.destroy()
            if self.toast_job:
                self.root.after_cancel(self.toast_job)
            lbl = tk.Label(self.root, text=msg, bg=c["inverse"], fg=c["on_inverse"],
                           font=(self.fam, 11), padx=int(18 * k), pady=int(10 * k))
            lbl.place(relx=0.5, rely=0.975, anchor="s")
            lbl.lift()
            self.toast_lbl = lbl
            self.toast_job = self.root.after(1500, self._untoast)
        except tk.TclError:
            pass

    def _untoast(self):
        try:
            if self.toast_lbl:
                self.toast_lbl.destroy()
        except tk.TclError:
            pass
        self.toast_lbl = self.toast_job = None

    # ──────────────────────────────────────────────────────────────── input
    def _fresh(self):
        if self.just:
            self.expr, self.just, self.last = "", False, ""

    def press(self, key):
        self.err = None
        e = self.expr
        if key == "AC":
            self.expr, self.last, self.just = "", "", False
        elif key == "⌫":
            self.just = False
            self.expr = re.sub(r"(?:sin\(|cos\(|tan\(|ln\(|log\(|√\(|.)$", "", e)
        elif key == "=":
            self.equals()
            return
        elif key in "0123456789":
            self._fresh()
            if re.search(r"(?<![\d.])0$", self.expr):
                self.expr = self.expr[:-1]
            self.expr += key
        elif key == ".":
            self._fresh()
            cur = re.search(r"[\d.]*$", self.expr).group(0)
            if "." not in cur:
                self.expr += "0." if cur == "" else "."
        elif key in OPS:
            self.just = False
            e = self.expr
            if not e or e.endswith("("):
                if key == "−":
                    self.expr += key
            elif e[-1] in OPS:
                if key == "−" and e[-1] in "×÷^":
                    self.expr += key
                else:
                    while self.expr and self.expr[-1] in OPS:
                        self.expr = self.expr[:-1]
                    if self.expr and not self.expr.endswith("("):
                        self.expr += key
            else:
                self.expr += key
        elif key == "%":
            if e and e[-1] in "0123456789)%π":
                self.just = False
                self.expr += key
        elif key == "!":
            if e and e[-1].isdigit():
                self.just = False
                self.expr += key
        elif key in ("( )", "(", ")"):
            opens = e.count("(") - e.count(")")
            can_close = bool(e) and e[-1] in "0123456789)π%!" and opens > 0
            if key == ")" or (key == "( )" and can_close):
                if can_close:
                    self.just = False
                    self.expr += ")"
            else:
                self._fresh()
                self.expr += "("
        elif key == "π":
            self._fresh()
            self.expr += "π"
        elif key in FUNCS:
            self._fresh()
            self.expr += FUNCS[key]
        self.refresh()

    def equals(self):
        if not self.expr or self.just:
            return
        e = self.expr
        e += ")" * max(0, e.count("(") - e.count(")"))
        try:
            res = fmt(evaluate(e, self.deg))
        except CalcError as ex:
            self.err = str(ex)
            self.refresh()
            self.shake()
            return
        if res != self.expr:
            self.hist.append([self.expr, res])
            self.hist = self.hist[-100:]
            self.save()
        self.last = self.expr + " ="
        self.expr, self.just = res, True
        self.refresh()

    def on_key(self, e):
        ks = e.keysym
        if e.state & 0x4:                       # Ctrl
            if ks.lower() == "c":
                self.copy()
            elif ks.lower() == "v":
                self.paste()
            return
        if ks in ("Return", "KP_Enter"):
            key = "="
        elif ks == "BackSpace":
            key = "⌫"
        elif ks in ("Escape", "Delete"):
            if self.panel:
                self.close_panel()
                return
            key = "AC"
        elif len(e.char) == 1 and e.char in "0123456789":
            key = e.char
        elif e.char in KEYMAP:
            key = KEYMAP[e.char]
        else:
            return
        self.press(key)
        b = self.buttons.get("( )" if key in "()" else key)
        if b:
            b.pulse()

    def copy(self):
        txt = self.expr
        if not txt:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        self.toast("Copied")

    def paste(self):
        try:
            t = self.root.clipboard_get()
        except tk.TclError:
            return
        t = t.replace("*", "×").replace("/", "÷").replace("-", "−")
        t = "".join(ch for ch in t if ch in "0123456789.+−×÷^%!()π√")
        if t:
            self._fresh()
            self.expr += t
            self.err = None
            self.refresh()

    # ───────────────────────────────────────────────────────────── history
    def show_history(self):
        if self.panel:
            self.close_panel()
            return
        c, k, fam = self.c, self.k, self.fam
        card = Card(self.disp, c["mid"], c["bg"], r=int(28 * k), pad=int(16 * k))
        card.place(x=int(10 * k), y=int(4 * k), relwidth=1, width=-int(20 * k),
                   relheight=1, height=-int(8 * k))
        self.panel = card
        inner = card.inner

        head = tk.Frame(inner, bg=c["mid"])
        head.pack(fill="x")
        tk.Label(head, text="History", bg=c["mid"], fg=c["on_surface"],
                 font=(fam, 15, "bold")).pack(side="left")
        for text, cmd, width in (("Close", self.close_panel, 54), ("Clear", self.clear_history, 54)):
            MButton(head, text, cmd, c["high"], c["on_surface"], c["mid"],
                    (fam, 10, "bold"), w=int(width * k), h=int(30 * k)).pack(side="right", padx=int(3 * k))

        cv = tk.Canvas(inner, bg=c["mid"], bd=0, highlightthickness=0)
        cv.pack(fill="both", expand=True, pady=(int(8 * k), 0))
        lst = tk.Frame(cv, bg=c["mid"])
        win = cv.create_window(0, 0, anchor="nw", window=lst)
        cv.bind("<Configure>", lambda e: cv.itemconfigure(win, width=e.width))
        lst.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))

        if not self.hist:
            tk.Label(lst, text="Nothing here yet", bg=c["mid"], fg=c["variant"],
                     font=(fam, 13)).pack(pady=int(30 * k))
        for ex, res in reversed(self.hist[-50:]):
            row = tk.Frame(lst, bg=c["mid"], cursor="hand2")
            row.pack(fill="x", pady=(0, int(10 * k)))
            a = tk.Label(row, text=ex + " =", anchor="e", bg=c["mid"], fg=c["variant"], font=(fam, 12))
            b = tk.Label(row, text=res, anchor="e", bg=c["mid"], fg=c["on_surface"], font=(fam, 20))
            a.pack(fill="x")
            b.pack(fill="x")
            for w in (row, a, b):
                w.bind("<Button-1>", lambda e, r=res: self.use_history(r))

        def wheel(e):
            n = getattr(e, "num", 0)
            d = -1 if n == 4 else 1 if n == 5 else (-1 if e.delta > 0 else 1)
            cv.yview_scroll(d, "units")
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            card.bind_all(ev, wheel)

    def close_panel(self):
        if not self.panel:
            return
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.panel.unbind_all(ev)
        self.panel.destroy()
        self.panel = None

    def clear_history(self):
        self.hist = []
        self.save()
        self.close_panel()
        self.show_history()

    def use_history(self, res):
        self.expr, self.just, self.last, self.err = res, True, "", None
        self.close_panel()
        self.refresh()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
         
