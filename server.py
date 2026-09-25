#!/usr/bin/env python3
"""
ChartBytes — dead-simple chart-image API.

GET /chart?t=bar&d=10,20,30&labels=A,B,C&title=Sales&format=png
  -> renders a chart to PNG (Pillow) or SVG (pure stdlib).

Free tier: all chart types, no watermark, light theme, 500 renders/mo (soft).
Pro (license via Stripe Checkout -> /api/redeem): dark/brand themes,
  25k renders/mo, immutable caching on content-addressed URLs.

Pure stdlib + Pillow (PNG). No DB, no accounts, stateless.
"""
import base64
import hashlib
import hmac
import io
import json
import os
import time
import urllib.parse
import urllib.request
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except Exception:
    HAS_PIL = False

# --------------------------------------------------------------------------- config
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "")   # set at deploy from created price
LICENSE_SECRET = os.environ.get("CHART_LICENSE_SECRET", "")  # HMAC secret for Pro keys

FREE_MONTHLY_QUOTA = 500
PRO_MONTHLY_QUOTA = 25000
DEFAULT_W = 600
DEFAULT_H = 300

LANDING_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "landing")
INDEXNOW_KEY = "32dde7100d40b3fe6f533c2bd96e29bb"  # served at /<key>.txt for IndexNow

# --------------------------------------------------------------------------- palette
LIGHT = {
    "bg": (255, 255, 255), "fg": (45, 55, 72), "grid": (226, 232, 240),
    "accent": (59, 130, 246), "accent2": (16, 185, 129),
    "palette": [(59, 130, 246), (16, 185, 129), (245, 158, 11), (239, 68, 68),
                (139, 92, 246), (14, 165, 233), (236, 72, 153), (132, 204, 22)],
}
DARK = {
    "bg": (15, 23, 42), "fg": (226, 232, 240), "grid": (51, 65, 85),
    "accent": (96, 165, 250), "accent2": (52, 211, 153),
    "palette": [(96, 165, 250), (52, 211, 153), (251, 191, 36), (248, 113, 113),
                (167, 139, 250), (56, 189, 248), (244, 114, 182), (74, 222, 128)],
}
BRAND = {
    "bg": (12, 20, 38), "fg": (230, 240, 255), "grid": (40, 58, 86),
    "accent": (45, 212, 191), "accent2": (250, 204, 21),
    "palette": [(45, 212, 191), (250, 204, 21), (148, 163, 184), (94, 234, 212),
                (253, 224, 71), (226, 232, 240), (240, 171, 252), (125, 211, 252)],
}

THEMES = {"light": LIGHT, "dark": DARK, "brand": BRAND}
FREE_THEMES = {"light"}

# --------------------------------------------------------------------------- counters
_lock = threading.Lock()
_STATS = {"total": 0, "humans": 0, "bots": 0, "paths": {}, "referers": {}}
_QUOTA = {}  # "YYYY-MM" -> renders count

BOT_UA = ("bot", "spider", "crawl", "slurp", "bingpreview", "headless", "curl", "wget",
          "python-requests", "googlebot")


def _month():
    return time.strftime("%Y-%m", time.gmtime())


def _is_bot(ua):
    u = (ua or "").lower()
    return any(b in u for b in BOT_UA)


def _count_render(is_bot, path, referer, licensed):
    with _lock:
        _STATS["total"] += 1
        _STATS["bots" if is_bot else "humans"] += 1
        _STATS["paths"][path] = _STATS["paths"].get(path, 0) + 1
        if referer:
            _STATS["referers"][referer] = _STATS["referers"].get(referer, 0) + 1
        m = _month()
        _QUOTA[m] = _QUOTA.get(m, 0) + 1
        return _QUOTA[m]


# --------------------------------------------------------------------------- license
def _lic_verify(key):
    """key = '<id>:<hex hmac>'; verify HMAC over 'pro:<id>'."""
    if not LICENSE_SECRET or not key or ":" not in key:
        return False
    ident, sig = key.rsplit(":", 1)
    expect = hmac.new(LICENSE_SECRET.encode(), ("pro:" + ident).encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expect, sig)


def _lic_sign(ident):
    sig = hmac.new(LICENSE_SECRET.encode(), ("pro:" + ident).encode(), hashlib.sha256).hexdigest()
    return f"{ident}:{sig}"


# --------------------------------------------------------------------------- parsing
def _parse_numbers(s):
    out = []
    for tok in s.split(","):
        tok = tok.strip()
        if tok == "":
            continue
        try:
            out.append(float(tok))
        except ValueError:
            raise ValueError(f"invalid number: {tok!r}")
    return out


def _parse_series(data):
    """data = '1,2,3|4,5,6' -> [[1,2,3],[4,5,6]] (single '1,2,3' -> [[...]])."""
    return [_parse_numbers(p) for p in data.split("|")]


def _parse_labels(labels, n):
    if not labels:
        return [str(i + 1) for i in range(n)]
    parts = [p.strip() for p in labels.split(",")]
    if len(parts) != n:
        # pad / truncate
        parts = (parts + [str(i + 1) for i in range(len(parts), n)])[:n]
    return parts


def _qparams(qs):
    """Accept both short (t,d) and long (type,data) param names."""
    def first(*names, default=None):
        for n in names:
            v = qs.get(n, [""])[0]
            if v != "":
                return v
        return default

    ctype = first("t", "type", default="bar").lower()
    data = first("d", "data")
    if data is None:
        raise ValueError("missing 'd' (data) parameter")
    labels = first("labels", "label", default="")
    title = first("title", default="")
    w = int(first("w", "width", default=str(DEFAULT_W)))
    h = int(first("h", "height", default=str(DEFAULT_H)))
    fmt = first("format", default="png").lower()
    theme = first("theme", default="light").lower()
    series_names = first("series", "legend", default="")
    w = max(80, min(w, 2000))
    h = max(80, min(h, 2000))
    return ctype, data, labels, title, w, h, fmt, theme, series_names


# --------------------------------------------------------------------------- SVG
def _svg_esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def render_svg(spec):
    t = spec["type"]
    series = spec["series"]
    labels = spec["labels"]
    title = spec["title"]
    w, h = spec["w"], spec["h"]
    theme = THEMES.get(spec["theme"], LIGHT)
    pal = theme["palette"]

    pad_l, pad_r, pad_t, pad_b = 46, 12, (28 if title else 12), 34
    iw, ih = w - pad_l - pad_r, h - pad_t - pad_b

    def rgb(c):
        return f"rgb({c[0]},{c[1]},{c[2]})"

    parts = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
                 f'viewBox="0 0 {w} {h}">')
    parts.append(f'<rect width="100%" height="100%" fill="{rgb(theme["bg"])}"/>')

    def value_label(x, y, txt, anchor="middle", size=12):
        parts.append(f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="{size}" '
                     f'fill="{rgb(theme["fg"])}" text-anchor="{anchor}">{_svg_esc(txt)}</text>')

    if title:
        parts.append(f'<text x="{w/2}" y="22" font-family="sans-serif" font-size="16" '
                     f'font-weight="bold" fill="{rgb(theme["fg"])}" '
                     f'text-anchor="middle">{_svg_esc(title)}</text>')

    # --- categorical (bar / hbar / stacked / pie / donut) ---
    if t in ("pie", "donut"):
        flat = series[0]
        n = len(flat)
        total = sum(abs(v) for v in flat) or 1.0
        cx, cy = w / 2, h / 2
        outer = min(iw, ih) / 2 * 0.86
        inner = outer * 0.55 if t == "donut" else 0.0
        a0 = -90.0
        for i, v in enumerate(flat):
            frac = abs(v) / total
            a1 = a0 + frac * 360.0
            large = 1 if (a1 - a0) > 180 else 0
            x0, y0 = cx + outer * __import__("math").cos(__import__("math").radians(a0)), \
                     cy + outer * __import__("math").sin(__import__("math").radians(a0))
            x1, y1 = cx + outer * __import__("math").cos(__import__("math").radians(a1)), \
                     cy + outer * __import__("math").sin(__import__("math").radians(a1))
            if inner > 0:
                ix0, iy0 = cx + inner * __import__("math").cos(__import__("math").radians(a0)), \
                           cy + inner * __import__("math").sin(__import__("math").radians(a0))
                ix1, iy1 = cx + inner * __import__("math").cos(__import__("math").radians(a1)), \
                           cy + inner * __import__("math").sin(__import__("math").radians(a1))
                d = (f"M{x0:.1f},{y0:.1f} A{outer:.1f},{outer:.1f} 0 {large} 1 {x1:.1f},{y1:.1f} "
                     f"L{ix1:.1f},{iy1:.1f} A{inner:.1f},{inner:.1f} 0 {large} 0 {ix0:.1f},{iy0:.1f} Z")
            else:
                d = f"M{cx:.1f},{cy:.1f} L{x0:.1f},{y0:.1f} A{outer:.1f},{outer:.1f} 0 {large} 1 {x1:.1f},{y1:.1f} Z"
            color = pal[i % len(pal)]
            parts.append(f'<path d="{d}" fill="{rgb(color)}" stroke="{rgb(theme["bg"])}" stroke-width="1"/>')
            # label
            mid = (a0 + a1) / 2
            lx = cx + outer * 0.66 * __import__("math").cos(__import__("math").radians(mid))
            ly = cy + outer * 0.66 * __import__("math").sin(__import__("math").radians(mid)) + 4
            value_label(lx, ly, f"{labels[i]}")
            a0 = a1
    elif t in ("line", "area", "scatter"):
        ncat = len(labels)
        gap = iw / max(ncat, 1)
        vals = [v for s in series for v in s]
        vmax = max(vals + [1e-9])
        vmin = min(vals + [0.0])
        rng = (vmax - vmin) or 1.0
        ybase = pad_t + ih
        for g in range(0, 6):
            gy = pad_t + ih - (g / 5.0) * ih
            parts.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{w-pad_r}" y2="{gy:.1f}" '
                         f'stroke="{rgb(theme["grid"])}" stroke-width="1"/>')
            value_label(pad_l - 6, gy + 4, f"{vmin + rng*g/5:.0f}", anchor="end", size=11)
        for si, s in enumerate(series):
            color = pal[si % len(pal)]
            pts = []
            for i, v in enumerate(s):
                x = pad_l + i * gap + gap / 2
                y = ybase - (v - vmin) / rng * ih
                pts.append((x, y))
            if t == "area":
                poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
                parts.append(f'<polygon points="{poly} {pts[-1][0]:.1f},{ybase:.1f} '
                             f'{pts[0][0]:.1f},{ybase:.1f}" fill="{rgb(color)}" '
                             f'fill-opacity="0.25" stroke="none"/>')
            if t in ("line", "area"):
                lp = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
                parts.append(f'<polyline points="{lp}" fill="none" stroke="{rgb(color)}" '
                             f'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')
            for x, y in pts:
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{rgb(color)}" '
                             f'stroke="{rgb(theme["bg"])}" stroke-width="1"/>')
        for i in range(ncat):
            value_label(pad_l + i * gap + gap / 2, h - 10, labels[i])
    else:
        ncat = len(labels)
        nser = len(series)
        if t == "hbar":
            bw = ih / max(ncat, 1) * 0.6
            gap = ih / max(ncat, 1)
            vmax = max([max(s) for s in series] + [1e-9])
            for si, s in enumerate(series):
                for i, v in enumerate(s):
                    bh = bw / nser
                    bwpx = abs(v) / vmax * iw
                    x = pad_l
                    y = pad_t + i * gap + (gap - bw) / 2 + si * bh
                    color = pal[si % len(pal)]
                    parts.append(f'<rect x="{x}" y="{y:.1f}" width="{bwpx:.1f}" height="{bh:.1f}" '
                                 f'fill="{rgb(color)}"/>')
            for i in range(ncat):
                value_label(pad_l - 6, pad_t + i * gap + gap / 2 + 4, labels[i], anchor="end")
        else:
            stacked = t == "stacked"
            bw = iw / max(ncat, 1) * 0.6
            gap = iw / max(ncat, 1)
            if stacked:
                vmax = max([sum(abs(v) for v in s) for s in zip(*series)] + [1e-9])
            else:
                vmax = max([max(s) for s in series] + [1e-9])
            # gridlines + y axis ticks (5)
            for g in range(0, 6):
                gy = pad_t + ih - (g / 5.0) * ih
                parts.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{w-pad_r}" y2="{gy:.1f}" '
                             f'stroke="{rgb(theme["grid"])}" stroke-width="1"/>')
                value_label(pad_l - 6, gy + 4, f"{vmax*g/5:.0f}", anchor="end", size=11)
            for i in range(ncat):
                x = pad_l + i * gap + (gap - bw) / 2
                ybase = pad_t + ih
                acc = 0.0
                for si, s in enumerate(series):
                    v = s[i]
                    bh = abs(v) / vmax * ih
                    if stacked:
                        y = pad_t + ih - (acc + abs(v)) / vmax * ih
                        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{abs(v)/vmax*ih:.1f}" '
                                     f'fill="{rgb(pal[si % len(pal)])}"/>')
                        acc += abs(v)
                    else:
                        y = ybase - bh
                        parts.append(f'<rect x="{x + si * bw / nser:.1f}" y="{y:.1f}" width="{bw/nser:.1f}" height="{bh:.1f}" '
                                     f'fill="{rgb(pal[si % len(pal)])}"/>')
                value_label(pad_l + i * gap + gap / 2, h - 10, labels[i])

    parts.append("</svg>")
    return ("".join(parts)).encode("utf-8")


# --------------------------------------------------------------------------- PNG
def render_png(spec):
    if not HAS_PIL:
        raise RuntimeError("PNG rendering unavailable (Pillow not installed)")
    import math
    t = spec["type"]
    series = spec["series"]
    labels = spec["labels"]
    title = spec["title"]
    w, h = spec["w"], spec["h"]
    theme = THEMES.get(spec["theme"], LIGHT)
    pal = theme["palette"]

    img = Image.new("RGB", (w, h), theme["bg"])
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        font_s = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
        font_t = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except Exception:
        font = font_s = font_t = ImageFont.load_default()

    pad_l, pad_r, pad_t, pad_b = 46, 12, (30 if title else 14), 34
    iw, ih = w - pad_l - pad_r, h - pad_t - pad_b

    if title:
        d.text((w / 2, 12), title, fill=theme["fg"], font=font_t, anchor="ma")

    if t in ("pie", "donut"):
        flat = series[0]
        n = len(flat)
        total = sum(abs(v) for v in flat) or 1.0
        cx, cy = w / 2, h / 2
        outer = min(iw, ih) / 2 * 0.86
        inner = outer * 0.55 if t == "donut" else 0.0
        a0 = -90.0
        for i, v in enumerate(flat):
            frac = abs(v) / total
            a1 = a0 + frac * 360.0
            box = [cx - outer, cy - outer, cx + outer, cy + outer]
            if inner > 0:
                d.pieslice(box, a0, a1, fill=pal[i % len(pal)], outline=theme["bg"], width=1)
                d.ellipse([cx - inner, cy - inner, cx + inner, cy + inner], fill=theme["bg"])
            else:
                d.pieslice(box, a0, a1, fill=pal[i % len(pal)], outline=theme["bg"], width=1)
            mid = math.radians((a0 + a1) / 2)
            lx = cx + outer * 0.66 * math.cos(mid)
            ly = cy + outer * 0.66 * math.sin(mid)
            d.text((lx, ly), labels[i], fill=theme["bg"], font=font_s, anchor="mm")
            a0 = a1
    elif t in ("line", "area", "scatter"):
        ncat = len(labels)
        gap = iw / max(ncat, 1)
        vals = [v for s in series for v in s]
        vmax = max(vals + [1e-9])
        vmin = min(vals + [0.0])
        rng = (vmax - vmin) or 1.0
        ybase = pad_t + ih
        for g in range(0, 6):
            gy = pad_t + ih - (g / 5.0) * ih
            d.line([(pad_l, gy), (w - pad_r, gy)], fill=theme["grid"], width=1)
            d.text((pad_l - 6, gy), f"{vmin + rng*g/5:.0f}", fill=theme["fg"], font=font_s, anchor="rm")
        for si, s in enumerate(series):
            color = pal[si % len(pal)]
            pts = []
            for i, v in enumerate(s):
                x = pad_l + i * gap + gap / 2
                y = ybase - (v - vmin) / rng * ih
                pts.append((x, y))
            if t == "area":
                fill = tuple(int(c * 0.75 + bc * 0.25) for c, bc in zip(color, theme["bg"]))
                d.polygon(pts + [(pts[-1][0], ybase), (pts[0][0], ybase)], fill=fill)
            if t in ("line", "area"):
                d.line(pts, fill=color, width=3, joint="curve")
            for x, y in pts:
                d.ellipse([x - 3.5, y - 3.5, x + 3.5, y + 3.5], fill=color, outline=theme["bg"], width=1)
        for i in range(ncat):
            d.text((pad_l + i * gap + gap / 2, h - 12), labels[i], fill=theme["fg"], font=font_s, anchor="mm")
    else:
        ncat = len(labels)
        nser = len(series)
        if t == "hbar":
            gap = ih / max(ncat, 1)
            bw = gap * 0.6
            vmax = max([max(s) for s in series] + [1e-9])
            for i in range(ncat):
                y = pad_t + i * gap + (gap - bw) / 2
                d.text((pad_l - 6, y + bw / 2), labels[i], fill=theme["fg"], font=font_s, anchor="rm")
            for si, s in enumerate(series):
                for i, v in enumerate(s):
                    bh = bw / nser
                    bwpx = abs(v) / vmax * iw
                    y = pad_t + i * gap + (gap - bw) / 2 + si * bh
                    d.rectangle([pad_l, y, pad_l + bwpx, y + bh - 1], fill=pal[si % len(pal)])
        else:
            stacked = t == "stacked"
            gap = iw / max(ncat, 1)
            bw = gap * 0.6
            if stacked:
                vmax = max([sum(abs(v) for v in s) for s in zip(*series)] + [1e-9])
            else:
                vmax = max([max(s) for s in series] + [1e-9])
            for g in range(0, 6):
                gy = pad_t + ih - (g / 5.0) * ih
                d.line([(pad_l, gy), (w - pad_r, gy)], fill=theme["grid"], width=1)
                d.text((pad_l - 6, gy), f"{vmax*g/5:.0f}", fill=theme["fg"], font=font_s, anchor="rm")
            for i in range(ncat):
                x = pad_l + i * gap + (gap - bw) / 2
                ybase = pad_t + ih
                acc = 0.0
                for si, s in enumerate(series):
                    v = s[i]
                    bh = abs(v) / vmax * ih
                    if stacked:
                        y = ybase - (acc + abs(v)) / vmax * ih
                        d.rectangle([x, y, x + bw, ybase - acc / vmax * ih], fill=pal[si % len(pal)])
                        acc += abs(v)
                    else:
                        d.rectangle([x + si * bw / nser, ybase - bh, x + (si + 1) * bw / nser, ybase],
                                    fill=pal[si % len(pal)])
                d.text((pad_l + i * gap + gap / 2, h - 12), labels[i], fill=theme["fg"], font=font_s, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------- dispatch
def render_chart(qs, body=None):
    if body:
        ctype, data = body.get("type", "bar").lower(), body.get("data")
        if data is None:
            raise ValueError("missing 'data'")
        labels = body.get("labels", [])
        title = body.get("title", "")
        w = max(80, min(int(body.get("width", DEFAULT_W)), 2000))
        h = max(80, min(int(body.get("height", DEFAULT_H)), 2000))
        fmt = body.get("format", "png").lower()
        theme = body.get("theme", "light").lower()
        if isinstance(data, list) and data and isinstance(data[0], (int, float)):
            series = [data]
        else:
            series = data  # list of lists
        if labels and not isinstance(labels, str):
            labels = ",".join(str(x) for x in labels)
    else:
        ctype, data, labels, title, w, h, fmt, theme, _ = _qparams(qs)
        series = _parse_series(data)

    if ctype not in ("bar", "hbar", "line", "area", "pie", "donut", "stacked", "scatter"):
        raise ValueError(f"unknown chart type: {ctype}")

    if not series or not all(series):
        raise ValueError("empty data series")
    n = max(len(s) for s in series)
    labels = _parse_labels(labels or "", n)

    spec = {"type": ctype, "series": series, "labels": labels, "title": title,
            "w": w, "h": h, "theme": theme}
    if fmt == "svg":
        return render_svg(spec), "image/svg+xml"
    return render_png(spec), "image/png"


# --------------------------------------------------------------------------- Stripe
def _stripe(method, path, payload=None):
    if not STRIPE_SECRET_KEY:
        raise RuntimeError("STRIPE_SECRET_KEY not configured")
    req = urllib.request.Request(
        "https://api.stripe.com/v1/" + path,
        data=(urllib.parse.urlencode(payload).encode() if payload else None),
        method=method,
        headers={"Authorization": "Bearer " + STRIPE_SECRET_KEY,
                 "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def create_checkout_session(base_url):
    if not STRIPE_PRICE_ID:
        raise RuntimeError("STRIPE_PRICE_ID not configured")
    return _stripe("POST", "checkout/sessions", {
        "mode": "payment",
        "line_items[0][price]": STRIPE_PRICE_ID,
        "line_items[0][quantity]": "1",
        "success_url": base_url + "/api/redeem?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": base_url + "/?pro=cancel",
        "allow_promotion_codes": "true",
    })


def redeem_session(session_id):
    sess = _stripe("GET", f"checkout/sessions/{session_id}")
    if sess.get("payment_status") != "paid":
        return None
    email = sess.get("customer_details", {}).get("email") or sess.get("customer") or "pro"
    return _lic_sign(email)


# --------------------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "ChartBytes/1.0"

    def _base_url(self):
        host = self.headers.get("Host", "localhost")
        proto = "https" if self.headers.get("X-Forwarded-Proto", "http") == "https" else "http"
        return f"{proto}://{host}"

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj).encode(), "application/json")

    def _log(self, code):
        print(f"{time.strftime('%H:%M:%S')} {self.command} {self.path} -> {code}", flush=True)

    def _serve_static(self, filename, ctype="text/html; charset=utf-8"):
        """Serve a file from the landing/ dir; returns False if missing."""
        try:
            with open(os.path.join(LANDING_DIR, filename), "rb") as f:
                body = f.read()
        except Exception:
            return False
        self._send(200, body, ctype)
        return True

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            if path == "/health":
                self._json(200, {"ok": True, "service": "chartbytes", "png": HAS_PIL})
            elif path in ("/", "/index.html"):
                if not self._serve_static("index.html"):
                    self._send(200, INDEX_HTML.encode(), "text/html; charset=utf-8")
            elif path in ("/image-charts-alternative.html", "/quickchart-alternative.html",
                          "/chart-image-for-email.html", "/builder.html"):
                if not self._serve_static(path.lstrip("/")):
                    self._json(404, {"error": "not found"})
            elif path == "/sitemap.xml":
                if not self._serve_static("sitemap.xml", "application/xml; charset=utf-8"):
                    self._json(404, {"error": "not found"})
            elif path == "/robots.txt":
                if not self._serve_static("robots.txt", "text/plain; charset=utf-8"):
                    self._json(404, {"error": "not found"})
            elif path == f"/{INDEXNOW_KEY}.txt":
                self._send(200, INDEXNOW_KEY.encode(), "text/plain; charset=utf-8")
            elif path == "/__stats__":
                with _lock:
                    self._json(200, {**_STATS, "quota_this_month": _QUOTA.get(_month(), 0),
                                     "free_quota": FREE_MONTHLY_QUOTA})
            elif path == "/api/checkout":
                sess = create_checkout_session(self._base_url())
                self.send_response(302)
                self.send_header("Location", sess["url"])
                self.send_header("Content-Length", "0")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self._log(302)
            elif path == "/api/redeem":
                sid = qs.get("session_id", [""])[0]
                key = redeem_session(sid) if sid else None
                if key:
                    self._send(200, (f"Your ChartBytes Pro license key:\n\n{key}\n\n"
                                     f"Use it as ?lic={urllib.parse.quote(key)} on any chart request.\n").encode(),
                               "text/plain; charset=utf-8")
                else:
                    self._send(200, b"Payment not found or not yet paid.", "text/plain; charset=utf-8")
            elif path == "/chart":
                lic = qs.get("lic", [""])[0]
                licensed = _lic_verify(lic)
                theme = qs.get("theme", ["light"])[0].lower()
                if theme not in FREE_THEMES and not licensed:
                    self._json(403, {"error": f"theme '{theme}' is Pro-only",
                                     "pro": True})
                    self._log(403)
                    return
                n = _count_render(_is_bot(self.headers.get("User-Agent", "")), path,
                                  self.headers.get("Referer", ""), licensed)
                limit = PRO_MONTHLY_QUOTA if licensed else FREE_MONTHLY_QUOTA
                if n > limit:
                    self._json(429, {"error": "monthly render quota exceeded",
                                     "pro": not licensed,
                                     "buy": self._base_url() + "/api/checkout"})
                    self._log(429)
                    return
                body, ctype = render_chart(qs)
                cache = "public, max-age=300" if not licensed else "public, max-age=300"
                if qs.get("h", [""])[0]:
                    cache = "public, max-age=31536000, immutable"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", cache)
                self.end_headers()
                self.wfile.write(body)
                self._log(200)
            else:
                self._json(404, {"error": "not found"})
                self._log(404)
        except ValueError as e:
            self._json(400, {"error": str(e)})
            self._log(400)
        except Exception as e:
            self._json(500, {"error": str(e)})
            self._log(500)

    def do_POST(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            if path == "/chart":
                ln = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(ln) if ln else b"{}"
                body = json.loads(raw.decode() or "{}")
                lic = body.get("lic", "")
                licensed = _lic_verify(lic)
                theme = body.get("theme", "light")
                if theme not in FREE_THEMES and not licensed:
                    self._json(403, {"error": f"theme '{theme}' is Pro-only", "pro": True})
                    return
                n = _count_render(_is_bot(self.headers.get("User-Agent", "")), path,
                                  self.headers.get("Referer", ""), licensed)
                limit = PRO_MONTHLY_QUOTA if licensed else FREE_MONTHLY_QUOTA
                if n > limit:
                    self._json(429, {"error": "monthly render quota exceeded", "pro": not licensed})
                    return
                out, ctype = render_chart(None, body)
                self._send(200, out, ctype)
            elif path == "/api/checkout":
                sess = create_checkout_session(self._base_url())
                self._json(200, {"url": sess["url"]})
            else:
                self._json(404, {"error": "not found"})
        except ValueError as e:
            self._json(400, {"error": str(e)})
        except Exception as e:
            self._json(500, {"error": str(e)})

    def log_message(self, *a):
        pass  # we log ourselves


INDEX_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ChartBytes — chart image API</title>
<style>
 body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:760px;margin:3rem auto;padding:0 1.5rem;color:#1f2937;background:#fff}
 code{background:#f3f4f6;padding:.15rem .4rem;border-radius:4px;font-size:.9em}
 pre{background:#0f172a;color:#e2e8f0;padding:1rem;border-radius:8px;overflow-x:auto}
 a{color:#2563eb}
 h1{font-size:1.8rem} .muted{color:#6b7280}
</style></head><body>
<h1>ChartBytes</h1>
<p class="muted">A dead-simple API that turns a URL into a chart image — for emails, READMEs, Notion, reports.</p>
<h2>Example</h2>
<pre>GET /chart?t=bar&d=12,19,8,24&labels=Q1,Q2,Q3,Q4&title=Sales&format=png</pre>
<p><img src="/chart?t=bar&d=12,19,8,24&labels=Q1,Q2,Q3,Q4&title=Sales" alt="example chart" style="max-width:100%"></p>
<h2>Chart types</h2>
<p><code>bar</code> · <code>hbar</code> · <code>stacked</code> · <code>line</code> · <code>area</code> · <code>scatter</code> · <code>pie</code> · <code>donut</code></p>
<h2>Params</h2>
<ul>
<li><code>t</code> / <code>type</code> — chart type (required)</li>
<li><code>d</code> / <code>data</code> — comma-separated numbers; <code>|</code> separates series (required)</li>
<li><code>labels</code> — comma-separated labels</li>
<li><code>title</code> — chart title</li>
<li><code>w</code>/<code>width</code>, <code>h</code>/<code>height</code> — size (default 600×300)</li>
<li><code>format</code> — <code>png</code> (default) or <code>svg</code></li>
<li><code>theme</code> — <code>light</code> (free) · <code>dark</code>, <code>brand</code> (Pro)</li>
</ul>
<h2>Pro</h2>
<p>Free: 500 renders/mo, light theme, no watermark. Pro ($9 one-time): dark/brand themes, 25k renders/mo, immutable caching. <a href="/api/checkout">Get Pro →</a></p>
</body></html>
"""


def main():
    port = int(os.environ.get("PORT", "10000"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"ChartBytes listening on :{port} (PIL={HAS_PIL})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
