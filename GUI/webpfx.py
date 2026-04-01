"""
FFmpeg Animated WebP Filter UI + Banner Stitcher  v4
-----------------------------------------------------
Folder layout:
  input/    <- animated .webp files
  output/   <- results
  banners/  <- banner images matched by prefix  (gb.png -> gb_dark_720p.webp)

Requires: Python 3.8+  |  pip install Pillow
FFmpeg: on PATH  OR  ffmpeg.exe in the same folder as this script.
"""

import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont
import subprocess, threading, os, sys, shutil, glob, tempfile, logging, traceback, colorsys
from datetime import datetime
from PIL import Image, ImageTk

# ══════════════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════════════
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE   = os.path.join(SCRIPT_DIR, "ffui_debug.log")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(funcName)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("ffui")
log.info("=" * 60)
log.info("FFmpeg Filter UI v4 starting")

# ══════════════════════════════════════════════════════════════════════════
#  PATHS
# ══════════════════════════════════════════════════════════════════════════
FFMPEG     = shutil.which("ffmpeg") or os.path.join(SCRIPT_DIR, "ffmpeg.exe")
INPUT_DIR  = os.path.join(SCRIPT_DIR, "input")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
BANNER_DIR = os.path.join(SCRIPT_DIR, "banners")
for d in (INPUT_DIR, OUTPUT_DIR, BANNER_DIR):
    os.makedirs(d, exist_ok=True)
log.info(f"FFmpeg: {FFMPEG}")

# ══════════════════════════════════════════════════════════════════════════
#  SHELL HELPERS
# ══════════════════════════════════════════════════════════════════════════
def _q(s):
    return '"' + str(s).replace('"', '\\"') + '"'

def _run_shell(cmd, timeout=600):
    log.debug(f"shell: {cmd}")
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=True)

def _ffmpeg_cmd(inp, out, vf, fps, single=False):
    cmd = f"{_q(FFMPEG)} -y -framerate {fps} -i {_q(inp)} -vf {_q(vf)}"
    if single:
        cmd += f" -frames:v 1 {_q(out)}"
    else:
        cmd += f" -c:v libwebp_anim -pix_fmt yuva420p -loop 0 {_q(out)}"
    return cmd

def run_ffmpeg(inp, out, vf, fps, on_done):
    log.info(f"run_ffmpeg: {os.path.basename(inp)} -> {os.path.basename(out)}")
    def worker():
        try:
            r = _run_shell(_ffmpeg_cmd(inp, out, vf, fps), timeout=600)
            if r.returncode == 0:
                sz = os.path.getsize(out) if os.path.exists(out) else 0
                log.info(f"ffmpeg OK: {sz} bytes")
                on_done(True, "Done.")
            else:
                log.error(f"ffmpeg FAIL:\n{r.stderr[-800:]}")
                on_done(False, r.stderr[-600:])
        except subprocess.TimeoutExpired:
            on_done(False, "FFmpeg timeout (600s)")
        except Exception as e:
            log.error(traceback.format_exc())
            on_done(False, str(e))
    threading.Thread(target=worker, daemon=True).start()

# ══════════════════════════════════════════════════════════════════════════
#  FRAME UTILITIES
# ══════════════════════════════════════════════════════════════════════════
def extract_frames(path):
    log.info(f"extract_frames: {path}")
    tmp = tempfile.mkdtemp(prefix="ffui_")
    try:
        img = Image.open(path)
        fps = 1000 / img.info.get("duration", 40)
        n   = 0
        try:
            while True:
                img.seek(n)
                img.convert("RGBA").save(os.path.join(tmp, f"frame_{n:04d}.png"))
                n += 1
        except EOFError:
            pass
        log.info(f"Extracted {n} frames  fps={fps:.2f}")
        return tmp, fps
    except Exception as e:
        log.error(f"extract_frames: {e}")
        shutil.rmtree(tmp, ignore_errors=True)
        return None, 0.0

def first_frame(path):
    try:
        img = Image.open(path); img.seek(0)
        return img.convert("RGBA")
    except Exception as e:
        log.error(f"first_frame: {e}"); return None

def webp_size(path):
    try:
        img = Image.open(path); img.seek(0); return img.size
    except: return (1280, 720)

# ══════════════════════════════════════════════════════════════════════════
#  BANNER UTILITIES
# ══════════════════════════════════════════════════════════════════════════
BANNER_EXTS = (".png", ".jpg", ".jpeg", ".webp")

def find_banner(name):
    """
    Match banner to webp by filename prefix (before first underscore).
    Priority order:
      1. Full stem match:   NES_PAL.webp -> banners/NES_PAL.png
      2. Prefix match:      NES_PAL.webp -> banners/NES.png
    This means:
      gb.webp       -> banners/gb.png     (exact stem)
      gb_dark.webp  -> banners/gb.png     (prefix)
      gba_dark.webp -> banners/gba.png    (prefix, different file = no conflict)
      nes.webp      -> banners/nes.png    (exact stem, no underscore)
      nes_pal.webp  -> banners/nes.png    (prefix fallback)
    """
    stem   = os.path.splitext(name)[0]
    prefix = stem.split("_")[0].lower()
    stem_l = stem.lower()
    log.debug(f"find_banner: name='{name}' stem='{stem_l}' prefix='{prefix}'")

    # 1. Full stem match first (most specific)
    for ext in BANNER_EXTS:
        c = os.path.join(BANNER_DIR, stem_l + ext)
        if os.path.isfile(c):
            log.info(f"Banner matched (full stem '{stem_l}'): {c}")
            return c

    # 2. Prefix match (e.g. gb_dark -> gb)
    if prefix != stem_l:  # only try prefix if it differs from full stem
        for ext in BANNER_EXTS:
            c = os.path.join(BANNER_DIR, prefix + ext)
            if os.path.isfile(c):
                log.info(f"Banner matched (prefix '{prefix}'): {c}")
                return c

    log.debug(f"find_banner: no match for '{name}' (tried stem='{stem_l}' prefix='{prefix}')")
    return None

def crop_alpha(img):
    if img.mode != "RGBA": img = img.convert("RGBA")
    bb = img.split()[3].getbbox()
    return img.crop(bb) if bb else img

def load_banner(path, h):
    try:
        img = Image.open(path).convert("RGBA")
        img = crop_alpha(img)
        w, oh = img.size
        nw  = max(1, int(w * h / oh))
        img = img.resize((nw, h), Image.LANCZOS)
        log.debug(f"Banner {img.size}")
        return img
    except Exception as e:
        log.error(f"load_banner: {e}"); return None

def detect_banner_orientation(path):
    """
    Returns 'horizontal' or 'vertical' based on aspect ratio of the banner image
    after alpha-cropping. Ratio >= 1.0 = horizontal, < 1.0 = vertical.
    """
    try:
        img = Image.open(path).convert("RGBA")
        img = crop_alpha(img)
        w, h = img.size
        ratio = w / h if h > 0 else 1.0
        orientation = "horizontal" if ratio >= 1.0 else "vertical"
        log.debug(f"detect_banner_orientation: {w}x{h} ratio={ratio:.2f} -> {orientation}")
        return orientation
    except Exception as e:
        log.error(f"detect_banner_orientation: {e}")
        return "horizontal"


def load_banner(path, size_px, orientation="horizontal"):
    """
    Load banner, crop alpha, scale to target size.
    orientation='horizontal': size_px = target height, width scales proportionally.
    orientation='vertical':   size_px = target width,  height scales proportionally.
    """
    try:
        img = Image.open(path).convert("RGBA")
        img = crop_alpha(img)
        w, oh = img.size
        if orientation == "horizontal":
            scale = size_px / oh
            nw    = max(1, int(w * scale))
            img   = img.resize((nw, size_px), Image.LANCZOS)
        else:  # vertical
            scale = size_px / w
            nh    = max(1, int(oh * scale))
            img   = img.resize((size_px, nh), Image.LANCZOS)
        log.debug(f"Banner loaded ({orientation}): {img.size}")
        return img
    except Exception as e:
        log.error(f"load_banner: {e}"); return None


def stitch(frame, banner, pos, overlap_pct):
    """
    Composite banner onto frame.

    pos: "top-left" | "top-center" | "top-right" |
         "mid-left" | "mid-center" | "mid-right"  |
         "bot-left" | "bot-center" | "bot-right"

    overlap_pct: 0.0 = banner fully outside frame (extends canvas)
                 1.0 = banner fully overlaps frame (pure overlay, no canvas change)
    Values between 0 and 1 partially overlap.

    Returns the composited image (may be larger than original if overlap < 1).
    The caller is responsible for fit_to_canvas() to restore original dimensions.
    """
    fw, fh = frame.size
    bw, bh = banner.size
    vert, horiz = pos.split("-")

    # Horizontal alignment of banner
    def _bx(canvas_w):
        if horiz == "left":   return 0
        if horiz == "right":  return canvas_w - bw
        return (canvas_w - bw) // 2  # center

    # For mid positions: pure overlay at anchor point, no canvas extension
    if vert == "mid":
        c = frame.copy()
        bx = _bx(fw)
        if horiz == "left":   bx = 0
        elif horiz == "right": bx = fw - bw
        else:                  bx = (fw - bw) // 2
        by = (fh - bh) // 2
        c.paste(banner, (bx, by), banner)
        log.debug(f"stitch mid: banner at ({bx},{by}) on {fw}x{fh}")
        return c

    # For top/bot: overlap_pct controls how much banner slides into frame
    # overlap_pct=0: banner fully outside (adds bh to canvas)
    # overlap_pct=1: banner fully inside (no canvas extension, pure overlay)
    overlap_px = int(bh * overlap_pct)      # how many px of banner are inside frame
    extend_px  = bh - overlap_px            # how many px extend the canvas

    if extend_px > 0:
        canvas_w = max(fw, bw)
        canvas_h = fh + extend_px
        c = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        bx = _bx(canvas_w)
        fx = (canvas_w - fw) // 2

        if vert == "top":
            # Banner at top, extends upward by extend_px
            by_banner = 0
            by_frame  = extend_px
        else:  # bot
            # Frame at top, banner at bottom extends downward
            by_frame  = 0
            by_banner = fh - overlap_px

        c.paste(frame,  (fx, by_frame),  frame)
        c.paste(banner, (bx, by_banner), banner)
        log.debug(f"stitch {vert} overlap={overlap_pct:.0%}: "
                  f"extend={extend_px}px canvas={canvas_w}x{canvas_h}")
    else:
        # Full overlap: pure overlay on original frame size
        c = frame.copy()
        bx = _bx(fw)
        if vert == "top":   by = 0
        else:               by = fh - bh
        c.paste(banner, (bx, by), banner)
        log.debug(f"stitch {vert} full overlap: banner at ({bx},{by})")

    return c


def fit_to_canvas(img, target_w, target_h):
    """
    Scale img down to fit within target_w x target_h (preserving aspect ratio),
    then center it on a target_w x target_h transparent canvas.
    If img already fits, just center it with padding.
    No cropping ever occurs.
    """
    iw, ih = img.size
    if iw == 0 or ih == 0:
        return Image.new("RGBA", (target_w, target_h), (0,0,0,0))
    scale  = min(target_w / iw, target_h / ih, 1.0)  # never upscale
    new_w  = max(1, int(iw * scale))
    new_h  = max(1, int(ih * scale))
    if scale < 1.0:
        img = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGBA", (target_w, target_h), (0,0,0,0))
    px = (target_w - new_w) // 2
    py = (target_h - new_h) // 2
    canvas.paste(img, (px, py), img)
    log.debug(f"fit_to_canvas: {iw}x{ih} -> {new_w}x{new_h} on {target_w}x{target_h}")
    return canvas


def apply_banner_to_frames(tmp, bpath, bh, pos, overlap_pct, orientation, orig_w, orig_h):
    """Legacy helper kept for compatibility. Not used in main pipeline."""
    banner = load_banner(bpath, bh, orientation)
    if not banner: return False
    frames = sorted(glob.glob(os.path.join(tmp, "frame_*.png")))
    for i, fp in enumerate(frames):
        try:
            fr = Image.open(fp).convert("RGBA")
            stitched = stitch(fr, banner, pos, overlap_pct)
            fit_to_canvas(stitched, orig_w, orig_h).save(fp)
        except Exception as e:
            log.error(f"stitch frame {i}: {e}"); return False
    return True

# ══════════════════════════════════════════════════════════════════════════
#  PS1 RESOLUTION PRESETS
#  Single slider 1-5 maps to named resolution levels
# ══════════════════════════════════════════════════════════════════════════
PS1_LEVELS = [
    (1, "NES",    64,  48),
    (2, "Lo",    128,  96),
    (3, "PS1",   256, 192),
    (4, "Hi",    320, 240),
    (5, "SVGA",  640, 480),
]
PS1_LABEL = {lvl: f"{lvl} - {name} ({w}×{h})" for lvl, name, w, h in PS1_LEVELS}

def ps1_dims(level):
    for lvl, name, w, h in PS1_LEVELS:
        if lvl == level:
            return w, h
    return 256, 192


def stitch_banner_onto_output(out_path, banner_path, banner_size, position,
                              overlap_pct, orientation, orig_w, orig_h):
    """
    Post-render banner stitching on an already-encoded webp.
    Reads all frames, stitches banner with overlap/orientation settings,
    fits result back to orig_w x orig_h with alpha padding, re-encodes.

    banner_size:  height in px (horizontal) or width in px (vertical)
    overlap_pct:  0.0 = fully outside, 1.0 = fully inside
    orientation:  'horizontal' or 'vertical'
    """
    log.info(f"stitch_banner_onto_output: {os.path.basename(out_path)} "
             f"size={banner_size} pos={position} overlap={overlap_pct:.0%} "
             f"orient={orientation} target={orig_w}x{orig_h}")

    banner = load_banner(banner_path, banner_size, orientation)
    if banner is None:
        log.error("Banner load failed")
        return False

    try:
        src_img = Image.open(out_path)
        fps     = 1000 / src_img.info.get("duration", 40)
        frames  = []
        n = 0
        try:
            while True:
                src_img.seek(n)
                frame    = src_img.convert("RGBA")
                stitched = stitch(frame, banner, position, overlap_pct)
                final    = fit_to_canvas(stitched, orig_w, orig_h)
                frames.append(final)
                n += 1
        except EOFError:
            pass

        if not frames:
            log.error("No frames extracted from output webp")
            return False

        log.info(f"Re-encoding {n} frames with banner")
        duration_ms = int(1000 / fps)
        frames[0].save(
            out_path, format="WEBP", save_all=True,
            append_images=frames[1:], loop=0,
            duration=duration_ms, lossless=False, quality=90,
        )
        log.info(f"Banner stitch complete: {out_path}")
        return True

    except Exception as e:
        log.error(f"stitch_banner_onto_output: {e}")
        log.debug(traceback.format_exc())
        return False


def fit_to_canvas(img, target_w, target_h):
    """
    Scale img to fit within target_w x target_h, then pad with transparency
    to reach exactly target_w x target_h. Aspect ratio is preserved.
    No cropping — transparent letterbox/pillarbox if needed.
    """
    iw, ih = img.size
    if iw == 0 or ih == 0:
        return Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))

    scale    = min(target_w / iw, target_h / ih)
    new_w    = max(1, int(iw * scale))
    new_h    = max(1, int(ih * scale))
    scaled   = img.resize((new_w, new_h), Image.LANCZOS)

    canvas   = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    paste_x  = (target_w - new_w) // 2
    paste_y  = (target_h - new_h) // 2
    canvas.paste(scaled, (paste_x, paste_y), scaled)
    log.debug(f"fit_to_canvas: {iw}x{ih} -> {new_w}x{new_h} on {target_w}x{target_h} "
              f"at ({paste_x},{paste_y})")
    return canvas

# ══════════════════════════════════════════════════════════════════════════
#  HALFTONE (Pillow-based, alpha-preserving)
#  geq cannot preserve alpha on transparent webp — we apply this on PNG frames
#  before ffmpeg encoding so the dots float on the transparent background.
# ══════════════════════════════════════════════════════════════════════════

def apply_halftone_to_frames(tmp_dir, cell, bw_mode, dot_scale):
    """
    Apply a halftone dot effect to every frame PNG in tmp_dir in-place.

    cell:       grid cell size in pixels (dot pitch)
    bw_mode:    True = greyscale dots, False = color dots
    dot_scale:  0.3-1.0, controls max dot radius as fraction of cell half
                (0.5 = small sparse dots, 1.0 = large nearly-solid dots)

    The dot radius for each cell scales with the average brightness of that cell:
      radius = dot_scale * (cell/2) * brightness
    Transparent areas stay transparent. Dots float on the transparent background.
    """
    import math
    log.info(f"apply_halftone_to_frames: cell={cell} bw={bw_mode} dot_scale={dot_scale}")
    frames = sorted(glob.glob(os.path.join(tmp_dir, "frame_*.png")))
    if not frames:
        log.error("No frames for halftone")
        return False

    for fi, fpath in enumerate(frames):
        try:
            img = Image.open(fpath).convert("RGBA")
            w, h = img.size
            pixels = img.load()

            # Output canvas — fully transparent
            out = Image.new("RGBA", (w, h), (0, 0, 0, 0))

            # We'll draw dots using ImageDraw for clean anti-aliased circles
            # but drawn at 2x then downscaled for smooth edges
            scale = 2
            canvas = Image.new("RGBA", (w * scale, h * scale), (0, 0, 0, 0))
            try:
                from PIL import ImageDraw
                draw = ImageDraw.Draw(canvas)
            except Exception as e:
                log.error(f"ImageDraw import failed: {e}")
                return False

            half = cell / 2.0
            max_r = half * dot_scale

            # Iterate over each cell
            for cy_cell in range(0, h, cell):
                for cx_cell in range(0, w, cell):
                    # Sample region for this cell
                    x1 = cx_cell
                    y1 = cy_cell
                    x2 = min(cx_cell + cell, w)
                    y2 = min(cy_cell + cell, h)

                    # Compute average color and alpha of cell
                    r_sum = g_sum = b_sum = a_sum = 0
                    count = 0
                    for yy in range(y1, y2):
                        for xx in range(x1, x2):
                            pr, pg, pb, pa = pixels[xx, yy]
                            r_sum += pr; g_sum += pg; b_sum += pb; a_sum += pa
                            count += 1

                    if count == 0:
                        continue

                    avg_a = a_sum / count
                    if avg_a < 8:
                        # Fully transparent cell — skip, keep transparent
                        continue

                    avg_r = r_sum / count
                    avg_g = g_sum / count
                    avg_b = b_sum / count

                    # Luminance 0-1
                    lum = (avg_r * 0.299 + avg_g * 0.587 + avg_b * 0.114) / 255.0

                    # Dot radius proportional to luminance
                    dot_r = max_r * lum
                    if dot_r < 0.5:
                        continue  # invisible dot — skip

                    # Dot center
                    cx_dot = cx_cell + half
                    cy_dot = cy_cell + half

                    # Dot color
                    if bw_mode:
                        # Dark dot on transparent bg — darker areas = bigger dot
                        # Invert so dark source = large dot
                        dot_r = max_r * (1.0 - lum)
                        if dot_r < 0.5:
                            continue
                        # Force full alpha on dots — dots must be solid
                        dot_color = (30, 30, 30, 255)
                    else:
                        # Force full alpha on dots regardless of source alpha.
                        # Semi-transparent source pixels would make dots invisible
                        # on light backgrounds. Dots are always fully opaque.
                        dot_color = (int(avg_r), int(avg_g), int(avg_b), 255)

                    # Draw at 2x scale for anti-aliasing
                    s = scale
                    bx = int((cx_dot - dot_r) * s)
                    by = int((cy_dot - dot_r) * s)
                    ex = int((cx_dot + dot_r) * s)
                    ey = int((cy_dot + dot_r) * s)
                    draw.ellipse([bx, by, ex, ey], fill=dot_color)

            # Downsample 2x for smooth circles
            out = canvas.resize((w, h), Image.LANCZOS)
            out.save(fpath)

            if fi == 0 or (fi + 1) % 10 == 0:
                log.debug(f"Halftone frame {fi+1}/{len(frames)}")

        except Exception as e:
            log.error(f"Halftone frame {fpath}: {e}")
            log.debug(traceback.format_exc())
            return False

    log.info("Halftone complete")
    return True


# ══════════════════════════════════════════════════════════════════════════
#  FILTER BUILDER
# ══════════════════════════════════════════════════════════════════════════

def _mono_tint_geq(h_deg, sat):
    """
    Recolor any image (including greyscale) to a single tint.
    Maps pixel luminance -> tinted RGB using target hue.
    hue=s=0 then hue=h=X:s=Y does NOT work on grey because hue filter
    only rotates existing chrominance — grey has none to rotate.
    This geq formula injects actual color based on luminance directly.
    """
    import colorsys as _cs
    h_norm = (h_deg % 360) / 360.0
    # Map sat slider (0-8) to a reasonable colorsys saturation (0-1)
    sat_c  = min(1.0, max(0.0, sat / 8.0))
    r, g, b = _cs.hsv_to_rgb(h_norm, sat_c, 1.0)
    r255, g255, b255 = r * 255, g * 255, b * 255
    # lum: weighted luminance of source pixel, range 0-255
    lum = "((r(X,Y)*0.299+g(X,Y)*0.587+b(X,Y)*0.114)/255)"
    return (
        f"geq="
        f"r='{lum}*{r255:.2f}'"
        f":g='{lum}*{g255:.2f}'"
        f":b='{lum}*{b255:.2f}'"
    )


def build_vf(p):
    """
    Build ffmpeg -vf string from UI params dict.
    Returns None if no filters active.

    Filter order (intentional):
      1. Pixel/Dither/PS1   — resolution changes first
      2. Color & Artistic   — tint, levels, thermal, sketch, halftone, sepia, posterize
      3. Sharpening & Glow  — sharpen, blur, neon, glow
      4. CRT & VHS          — screen simulation always last, on top of all color work
      5. Reverse            — frame order, always final step

    Named stream labels use unique prefixes per filter to avoid graph conflicts.
    """
    parts = []

    # ── 1. PIXEL & LOW-RES ───────────────────────────────────────────────
    if p.get("pixel_on"):
        d         = max(2, int(p["pixel_size"]))
        lcd       = bool(p.get("pixel_lcd", False))
        thickness = max(1, int(p.get("pixel_lcd_thick", 1)))
        opacity   = float(p.get("pixel_lcd_opacity", 0.6))
        parts.append(
            f"scale=iw/{d}:-2:flags=neighbor,"
            f"scale=1280:720:flags=neighbor"
        )
        if lcd:
            bright = 1.0 - opacity
            grid_cond = (
                f"if(lt(mod(X,{d}),{thickness})+lt(mod(Y,{d}),{thickness}),"
                f"{bright:.3f}*r(X,Y),r(X,Y))"
            )
            grid_cond_g = grid_cond.replace("r(X,Y)", "g(X,Y)")
            grid_cond_b = grid_cond.replace("r(X,Y)", "b(X,Y)")
            parts.append(
                f"geq=r='{grid_cond}'"
                f":g='{grid_cond_g}'"
                f":b='{grid_cond_b}'"
            )
            log.debug(f"pixel_lcd d={d} thick={thickness} opacity={opacity:.2f}")
        log.debug(f"pixel d={d} lcd={lcd}")

    if p.get("dither_on"):
        d = max(2, int(p["dither_size"]))
        parts.append(
            f"scale=iw/{d}:-2:flags=neighbor,"
            f"format=rgb8,format=rgb24,"
            f"scale=1280:720:flags=neighbor"
        )
        log.debug(f"dither d={d}")

    if p.get("ps1_on"):
        level = max(1, min(5, int(p.get("ps1_level", 3))))
        w, h  = ps1_dims(level)
        parts.append(
            f"scale={w}:{h}:flags=neighbor,"
            f"format=rgb8,format=rgb24,"
            f"scale=1280:720:flags=neighbor,"
            f"noise=alls=4:allf=u"
        )
        log.debug(f"ps1 level={level} {w}x{h}")

    # ── 2. COLOR & TONES ─────────────────────────────────────────────────
    if p.get("tint_on"):
        h_deg = float(p.get("tint_hue", 0))
        sat   = float(p.get("tint_sat", 1.5))
        mono  = bool(p.get("tint_mono", False))
        if mono:
            parts.append(_mono_tint_geq(h_deg, sat))
            log.debug(f"tint MONO geq h={h_deg} sat={sat}")
        else:
            parts.append(f"hue=h={h_deg:.1f}:s={sat:.2f}")
            log.debug(f"tint h={h_deg} s={sat}")

    if p.get("tint_anim_on"):
        swing  = float(p.get("tint_swing", 60))
        period = float(p.get("tint_period", 14))
        parts.append(f"hue=h='{swing:.0f}*sin(2*3.14159*t/{period:.1f})'")
        log.debug(f"tint_anim swing={swing} period={period}")

    if p.get("levels_on"):
        br = float(p["levels_brightness"])
        co = float(p["levels_contrast"])
        sa = float(p["levels_saturation"])
        parts.append(f"eq=brightness={br:.2f}:contrast={co:.2f}:saturation={sa:.2f}")
        log.debug(f"levels br={br} co={co} sa={sa}")

    if p.get("sepia_on"):
        parts.append("colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131:0")
        log.debug("sepia")

    if p.get("posterize_on"):
        lvl  = max(2, int(p.get("posterize_levels", 4)))
        step = max(1, 256 // lvl)
        parts.append(
            f"geq=r='floor(r(X,Y)/{step})*{step}'"
            f":g='floor(g(X,Y)/{step})*{step}'"
            f":b='floor(b(X,Y)/{step})*{step}'"
        )
        log.debug(f"posterize lvl={lvl} step={step}")

    if p.get("thermal_on"):
        parts.append(
            "hue=s=0,"
            "curves="
            "r='0/0 0.25/0.1 0.5/0.1 0.65/0.4 0.8/0.9 1/1':"
            "g='0/0 0.25/0.0 0.45/0.6 0.6/0.9 0.75/0.7 0.9/0.2 1/1':"
            "b='0/0.2 0.15/0.6 0.3/0.9 0.5/0.4 0.65/0.1 0.8/0.0 1/1'"
        )
        log.debug("thermal")

    # ── 3. ARTISTIC ──────────────────────────────────────────────────────
    if p.get("sketch_on"):
        sigma = float(p.get("sketch_sigma", 6))
        mode  = str(p.get("sketch_mode", "bw"))
        log.debug(f"sketch sigma={sigma} mode={mode}")
        core = (
            f"split[sk1][sk2],[sk2]negate[sk3],"
            f"[sk3]gblur=sigma={sigma:.0f}[sk4],"
            f"[sk1][sk4]blend=all_mode=dodge:all_opacity=1.0"
        )
        if mode == "color":
            parts.append(core)
        elif mode == "bw":
            parts.append(
                f"hue=s=0,{core},"
                f"hue=s=0,"
                f"colorlevels=romax=0.85:gomax=0.85:bomax=0.85"
            )
        elif mode == "inverted":
            parts.append(f"{core},negate")
        elif mode == "tinted":
            sh_deg = float(p.get("sketch_tint_hue", 110))
            s_sat  = float(p.get("sketch_tint_sat", 4.0))
            tint_g = _mono_tint_geq(sh_deg, s_sat)
            parts.append(
                f"hue=s=0,{core},"
                f"hue=s=0,"
                f"colorlevels=romax=0.85:gomax=0.85:bomax=0.85,"
                f"{tint_g}"
            )

    # NOTE: halftone is applied as a Pillow post-process on PNG frames
    # (see apply_halftone_to_frames) — not here — because geq can't preserve alpha.

    # ── 4. SHARPENING & GLOW ─────────────────────────────────────────────
    if p.get("sharpen_on"):
        amt = float(p["sharpen_amt"])
        parts.append(f"unsharp=5:5:{amt:.1f}:5:5:0.0")
        log.debug(f"sharpen amt={amt}")

    if p.get("blur_on"):
        sigma = float(p["blur_sigma"])
        parts.append(f"gblur=sigma={sigma:.1f}")
        log.debug(f"blur sigma={sigma}")

    if p.get("neon_on"):
        sat  = float(p["neon_sat"])
        blm  = float(p["neon_bloom"])
        op   = float(p["neon_opacity"])
        parts.append(
            f"eq=contrast=1.4:saturation={sat:.1f},"
            f"split[nn1][nn2],[nn2]gblur=sigma={blm:.0f}[nn3],"
            f"[nn1][nn3]blend=all_mode=screen:all_opacity={op:.2f}"
        )
        log.debug(f"neon sat={sat} bloom={blm}")

    if p.get("glow_on"):
        sigma = float(p["glow_sigma"])
        op    = float(p["glow_opacity"])
        parts.append(
            f"split[gg1][gg2],[gg2]gblur=sigma={sigma:.0f}[gg3],"
            f"[gg1][gg3]blend=all_mode=screen:all_opacity={op:.2f}"
        )
        log.debug(f"glow sigma={sigma}")

    # ── 5. CRT & VHS — always last, overlaid on top of everything ────────
    if p.get("crt_on"):
        freq   = float(p["crt_freq"])
        floor  = 1.0 - float(p["crt_depth"])
        period = freq / 2.0
        sc     = f"({floor:.3f}+{1-floor:.3f}*max(0,sin(Y*3.14159/{period:.3f})))"
        parts.append(f"geq=r='r(X,Y)*{sc}':g='g(X,Y)*{sc}':b='b(X,Y)*{sc}'")
        if p.get("crt_warp"):
            parts.append("lenscorrection=k1=0.06:k2=0.06")
        log.debug(f"crt freq={freq} floor={floor:.2f}")

    if p.get("vhs_on"):
        blur  = float(p["vhs_blur"])
        noise = int(p["vhs_noise"])
        shift = int(p["vhs_shift"])
        parts.append(f"gblur=sigma={blur:.1f}:sigmaV=0.2")
        parts.append(f"noise=alls={noise}:allf=t+u")
        if shift > 0:
            parts.append(f"rgbashift=rh={shift}:bh=-{shift}")
        log.debug(f"vhs blur={blur} noise={noise} shift={shift}")

    if not parts:
        log.debug("build_vf: no active filters")
        return None

    # ── 6. REVERSE — always final ─────────────────────────────────────────
    if p.get("reverse_on"):
        parts.append("reverse")
        log.debug("reverse: frames will be played backwards")

    inner = ",".join(parts)
    # Normalize to 1280:720 at the very start of the inner chain.
    # This is critical when banner stitching has changed the frame dimensions
    # before the vf chain runs — without this, scale/geq filters that assume
    # 1280x720 input will fail or produce wrong results.
    inner = f"scale=1280:720:flags=lanczos,{inner}"
    vf = (
        f"split=2[main][aorig],[main]alphaextract[aalpha],"
        f"[aorig]format=rgb24,{inner},format=rgba[rgb_out],"
        f"[rgb_out][aalpha]alphamerge"
    )
    log.debug(f"vf ({len(vf)} chars)")
    return vf


# ══════════════════════════════════════════════════════════════════════════
#  TINT COLOR PRESETS
# ══════════════════════════════════════════════════════════════════════════
TINT_PRESETS = [
    ("None",    0,   1.0),
    ("Red",     0,   3.5),
    ("Orange",  25,  3.5),
    ("Yellow",  50,  3.5),
    ("Lime",    80,  3.5),
    ("Green",   110, 3.5),
    ("Cyan",    160, 3.5),
    ("Blue",    215, 3.5),
    ("Purple",  265, 3.5),
    ("Pink",    300, 3.5),
    ("Magenta", 330, 3.5),
    ("Warm",    20,  1.8),
    ("Cool",    195, 1.8),
    ("Sepia",   28,  1.0),
]

# ══════════════════════════════════════════════════════════════════════════
#  FILTER PRESETS
# ══════════════════════════════════════════════════════════════════════════
FILTER_PRESETS = {
    "PS1 Style": {
        "desc": "Low-res pixel blocks + color crush.\nAdjust PS1 Resolution slider for NES→PS1→SVGA.",
        "params": {
            "ps1_on": True, "ps1_level": 3,
            "levels_on": True, "levels_saturation": 1.2,
            "levels_contrast": 1.1, "levels_brightness": 0.0,
        }
    },
    "Acid Trip": {
        "desc": "Oscillating hue shifts + CRT scanlines.\nColors pulse through the animation.",
        "params": {
            "tint_on": True, "tint_hue": 200, "tint_sat": 2.0, "tint_mono": False,
            "tint_anim_on": True, "tint_swing": 120, "tint_period": 14,
            "crt_on": True, "crt_freq": 4, "crt_depth": 0.5,
            "levels_on": True, "levels_contrast": 1.2, "levels_brightness": -0.05,
            "levels_saturation": 1.0,
        }
    },
    "Pip-Boy": {
        "desc": "Fallout terminal phosphor green display.\nGreen mono recolor + VHS grain + CRT scanlines.",
        "params": {
            "tint_on": True, "tint_hue": 110, "tint_sat": 6.0, "tint_mono": True,
            "vhs_on": True, "vhs_blur": 1.5, "vhs_noise": 8, "vhs_shift": 3,
            "crt_on": True, "crt_freq": 8, "crt_depth": 0.5,
        }
    },
    "Pixel + CRT": {
        "desc": "Chunky pixelization with CRT scanlines.\nClassic retro gaming look.",
        "params": {
            "pixel_on": True, "pixel_size": 6,
            "crt_on": True, "crt_freq": 4, "crt_depth": 0.65,
        }
    },
    "VHS Retro": {
        "desc": "Fuzzy analog tape with chroma bleed + color boost.",
        "params": {
            "vhs_on": True, "vhs_blur": 2.5, "vhs_noise": 14, "vhs_shift": 6,
            "levels_on": True, "levels_saturation": 1.8, "levels_contrast": 1.1,
            "levels_brightness": 0.0,
            "crt_on": True, "crt_freq": 4, "crt_depth": 0.4,
        }
    },
    "Neon Arcade": {
        "desc": "Hyper-saturated with heavy bloom. Bright surfaces glow.",
        "params": {
            "neon_on": True, "neon_sat": 3.5, "neon_bloom": 14, "neon_opacity": 0.75,
            "crt_on": True, "crt_freq": 4, "crt_depth": 0.45,
        }
    },
    "Pencil Sketch": {
        "desc": "Greyscale pencil drawing. Edges become dark lines on light paper.",
        "params": {
            "sketch_on": True, "sketch_sigma": 7, "sketch_mode": "bw",
        }
    },
    "Sepia Film": {
        "desc": "Classic sepia tone with soft focus and film grain.",
        "params": {
            "sepia_on": True,
            "blur_on": True, "blur_sigma": 1.5,
            "vhs_on": True, "vhs_blur": 0.5, "vhs_noise": 5, "vhs_shift": 0,
            "levels_on": True, "levels_contrast": 1.1, "levels_brightness": 0.05,
            "levels_saturation": 1.0,
        }
    },
    "Glitch": {
        "desc": "Digital corruption — heavy chroma shift and noise.",
        "params": {
            "vhs_on": True, "vhs_blur": 0.5, "vhs_noise": 18, "vhs_shift": 10,
            "tint_on": True, "tint_hue": 180, "tint_sat": 2.5, "tint_mono": False,
            "crt_on": True, "crt_freq": 3, "crt_depth": 0.6,
        }
    },
    "Gameboy": {
        "desc": "Mono green with pixel chunking + LCD grid.\nClassic handheld retro.",
        "params": {
            "pixel_on": True, "pixel_size": 4,
            "pixel_lcd": True, "pixel_lcd_thick": 1, "pixel_lcd_opacity": 0.55,
            "levels_on": True, "levels_saturation": 0.0,
            "levels_contrast": 1.6, "levels_brightness": -0.1,
            "tint_on": True, "tint_hue": 110, "tint_sat": 4.0, "tint_mono": True,
        }
    },
    "Neon Glow + Pixel": {
        "desc": "Pixelated blocks with vivid neon bloom bleeding between them.",
        "params": {
            "pixel_on": True, "pixel_size": 8,
            "neon_on": True, "neon_sat": 3.0, "neon_bloom": 12, "neon_opacity": 0.65,
        }
    },
    "Thermal Camera": {
        "desc": "False-color FLIR thermal imaging look.\nDark=purple/blue, mid=green, bright=red/white.",
        "params": {
            "thermal_on": True,
        }
    },
}

# ══════════════════════════════════════════════════════════════════════════
#  DEFAULT PARAM VALUES  (used by Reset All)
# ══════════════════════════════════════════════════════════════════════════
PARAM_DEFAULTS = {
    # booleans (all _on keys default False unless listed here)
    "reverse_on":       False,
    "tint_mono":        False,
    "tint_anim_on":     False,
    "crt_warp":         False,
    "sketch_bw":        False,
    "sketch_inv":       False,
    "sketch_grey":      False,
    # sketch mode
    "sketch_mode":      "bw",
    # sliders
    "pixel_size":       8,
    "pixel_lcd":        False,
    "halftone_cell":    8,
    "halftone_dot_scale": 0.85,
    "halftone_bw":      False,
    "pixel_lcd_thick":  1,
    "pixel_lcd_opacity":0.6,
    "dither_size":      5,
    "ps1_level":        3,
    "crt_freq":         4,
    "crt_depth":        0.65,
    "vhs_blur":         1.5,
    "vhs_noise":        8,
    "vhs_shift":        3,
    "tint_hue":         0,
    "tint_sat":         4.0,
    "tint_swing":       60,
    "tint_period":      14,
    "levels_brightness":0.0,
    "levels_contrast":  1.0,
    "levels_saturation":1.0,
    "posterize_levels": 4,
    "sharpen_amt":      1.5,
    "blur_sigma":       4.0,
    "neon_sat":         3.0,
    "neon_bloom":       12,
    "neon_opacity":     0.7,
    "glow_sigma":       10,
    "glow_opacity":     0.4,
    "sketch_sigma":     6,
    "sketch_tint_hue":  110,
    "thermal_on":       False,
    "sketch_tint_sat":  4.0,
    "sketch_mode":      "bw",
}

# ══════════════════════════════════════════════════════════════════════════
#  COLORS
# ══════════════════════════════════════════════════════════════════════════
C = {
    "bg":        "#1a1a2e",
    "panel":     "#16213e",
    "accent":    "#0f3460",
    "highlight": "#e94560",
    "text":      "#eaeaea",
    "muted":     "#777",
    "green":     "#00b894",
    "orange":    "#fdcb6e",
    "blue":      "#74b9ff",
}

# ══════════════════════════════════════════════════════════════════════════
#  WIDGET HELPERS
# ══════════════════════════════════════════════════════════════════════════
def lbl(parent, text, fg, font, **kw):
    return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=fg, font=font, **kw)

def btn(parent, text, cmd, bg, fg=None, **kw):
    return tk.Button(parent, text=text, command=cmd, bg=bg,
                     fg=fg or C["text"], relief="flat", cursor="hand2", **kw)

# ══════════════════════════════════════════════════════════════════════════
#  MAIN UI CLASS
# ══════════════════════════════════════════════════════════════════════════
class FilterUI(tk.Tk):
    def __init__(self):
        super().__init__()
        log.info("FilterUI init")
        self.title("WebP Filter Studio")
        self.configure(bg=C["bg"])
        self.resizable(True, True)
        self.minsize(1060, 720)
        self._tmp_dirs = []
        self._prev_img = None
        self._prev_win = None
        self.params    = {}
        self._init_fonts()
        self._build_ui()
        self._refresh_file_list()
        log.info("FilterUI ready")

    def _init_fonts(self):
        self.fn_h1    = tkfont.Font(family="Courier New", size=14, weight="bold")
        self.fn_h2    = tkfont.Font(family="Courier New", size=11, weight="bold")
        self.fn_label = tkfont.Font(family="Courier New", size=9)
        self.fn_small = tkfont.Font(family="Courier New", size=8)

    # ── Layout ────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = tk.Frame(self, bg=C["bg"])
        root.pack(fill="both", expand=True, padx=10, pady=8)
        left = tk.Frame(root, bg=C["panel"], width=230)
        left.pack(side="left", fill="y", padx=(0,8))
        left.pack_propagate(False)
        self._build_sidebar(left)
        right = tk.Frame(root, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True)
        self._build_main(right)

    def _build_sidebar(self, p):
        lbl(p, "INPUT FILES", C["highlight"], self.fn_h2).pack(pady=(10,4), padx=8, anchor="w")
        lf = tk.Frame(p, bg=C["panel"]); lf.pack(fill="both", expand=True, padx=6)
        sb = tk.Scrollbar(lf, bg=C["accent"]); sb.pack(side="right", fill="y")
        self.file_list = tk.Listbox(
            lf, yscrollcommand=sb.set, bg=C["accent"], fg=C["text"],
            selectbackground=C["highlight"], font=self.fn_small,
            borderwidth=0, highlightthickness=0, activestyle="none"
        )
        self.file_list.pack(fill="both", expand=True)
        sb.config(command=self.file_list.yview)
        self.file_list.bind("<<ListboxSelect>>", self._on_file_select)
        self.banner_lbl = lbl(p, "banner: none", C["muted"], self.fn_small)
        self.banner_lbl.pack(fill="x", padx=8, pady=(2,0))
        btn(p, "⟳ Refresh", self._refresh_file_list, C["accent"]).pack(fill="x", padx=6, pady=4)
        lbl(p, "PREVIEW", C["highlight"], self.fn_h2).pack(pady=(8,2), padx=8, anchor="w")
        self.thumb_lbl = tk.Label(p, bg="#000", text="no preview",
                                  fg=C["muted"], font=self.fn_small, height=8)
        self.thumb_lbl.pack(padx=6, fill="x")
        btn(p, "▶ Preview Frame", self._preview,
            C["highlight"], fg="#fff").pack(fill="x", padx=6, pady=(4,2))

    def _build_main(self, p):
        lbl(p, "FILTER STUDIO", C["highlight"], self.fn_h1).pack(anchor="w", pady=(2,0))
        lbl(p, "mix and match — adjust — render", C["muted"], self.fn_small).pack(anchor="w")
        nb = ttk.Notebook(p)
        nb.pack(fill="both", expand=True, pady=(6,0))
        ftab = tk.Frame(nb, bg=C["bg"]); nb.add(ftab, text="  FILTERS  ")
        self._build_filters_tab(ftab)
        ptab = tk.Frame(nb, bg=C["bg"]); nb.add(ptab, text="  PRESETS  ")
        self._build_presets_tab(ptab)
        btab = tk.Frame(nb, bg=C["bg"]); nb.add(btab, text="  BANNER STITCH  ")
        self._build_banner_tab(btab)
        bot = tk.Frame(p, bg=C["panel"], pady=6)
        bot.pack(fill="x", side="bottom")
        self._build_bottom(bot)

    # ── Filters tab ───────────────────────────────────────────────────────
    def _build_filters_tab(self, p):
        canvas = tk.Canvas(p, bg=C["bg"], highlightthickness=0)
        sb     = ttk.Scrollbar(p, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); canvas.pack(fill="both", expand=True)
        self.fframe = tk.Frame(canvas, bg=C["bg"])
        win = canvas.create_window((0,0), window=self.fframe, anchor="nw")
        self.fframe.bind("<Configure>",
                         lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        # ── PLAYBACK ─────────────────────────────────────────────────────
        g = self._group(self.fframe, "PLAYBACK")
        sec, _ = self._section(g, "Reverse Animation", "reverse")
        tk.Label(sec, bg=C["panel"], fg=C["orange"], font=self.fn_small,
                 text="WARNING: any video/animation content in the render will play in reverse."
                 ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0,2))
        tk.Label(sec, bg=C["panel"], fg=C["muted"], font=self.fn_small,
                 text="Reverses the frame order of the output webp animation."
                 ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0,4))

        # ── PIXEL & LOW-RES ───────────────────────────────────────────────
        g = self._group(self.fframe, "PIXEL & LOW-RES")

        sec, _ = self._section(g, "Pixelize", "pixel")
        self._slider(sec, "Pixel size (divisor)", "pixel_size", 2, 20, 8, 1, 0)
        self._checkbox(sec, "LCD grid overlay", "pixel_lcd", False, 1, 0)
        self._slider(sec, "Grid thickness (px)", "pixel_lcd_thick", 1, 4, 1, 1, 2)
        self._slider(sec, "Grid opacity (0=clear 1=black)", "pixel_lcd_opacity", 0.0, 1.0, 0.6, 0.05, 3)

        sec, _ = self._section(g, "Dither + Color Crush", "dither")
        self._slider(sec, "Block size (divisor)", "dither_size", 2, 12, 5, 1, 0)

        sec, _ = self._section(g, "PS1 / Low-Res", "ps1")
        # Single resolution slider — maps 1-5 to named sizes
        self.params["ps1_level"] = tk.IntVar(value=3)
        tk.Label(sec, text="Resolution", bg=C["panel"], fg=C["text"],
                 font=self.fn_small).grid(row=0, column=0, sticky="w", padx=(0,8))
        sl = tk.Scale(sec, variable=self.params["ps1_level"],
                      from_=1, to=5, resolution=1, orient="horizontal",
                      bg=C["panel"], fg=C["text"], troughcolor=C["accent"],
                      highlightthickness=0, font=self.fn_small, length=180,
                      showvalue=False, sliderlength=14,
                      activebackground=C["highlight"],
                      command=lambda v: self._update_ps1_label())
        sl.grid(row=0, column=1, sticky="w")
        self.ps1_label = tk.Label(sec, text=PS1_LABEL[3], bg=C["panel"],
                                  fg=C["blue"], font=self.fn_small)
        self.ps1_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0,2))

        # ── CRT & SCANLINES ───────────────────────────────────────────────
        g = self._group(self.fframe, "CRT & SCANLINES")

        sec, _ = self._section(g, "CRT Scanlines", "crt")
        self._slider(sec, "Scanline period (px)",      "crt_freq",  2,   12,  4,    1,    0)
        self._slider(sec, "Darkness  (0=black 1=off)", "crt_depth", 0.0, 1.0, 0.65, 0.05, 1)
        self._checkbox(sec, "Lens warp", "crt_warp", False, 2, 0)

        sec, _ = self._section(g, "VHS", "vhs")
        self._slider(sec, "Blur sigma",        "vhs_blur",  0.5, 4.0, 1.5, 0.5, 0)
        self._slider(sec, "Noise",             "vhs_noise", 0,   20,  8,   1,   1)
        self._slider(sec, "Chroma shift (px)", "vhs_shift", 0,   10,  3,   1,   2)

        # ── COLOR & TONES ─────────────────────────────────────────────────
        g = self._group(self.fframe, "COLOR & TONES")

        sec, _ = self._section(g, "Color Tint", "tint")
        self._build_tint_picker(sec)

        sec, _ = self._section(g, "Brightness / Contrast / Saturation", "levels")
        self._slider(sec, "Brightness",  "levels_brightness",  -0.5, 0.5, 0.0, 0.05, 0)
        self._slider(sec, "Contrast",    "levels_contrast",     0.5, 3.0, 1.0, 0.10, 1)
        self._slider(sec, "Saturation",  "levels_saturation",   0.0, 4.0, 1.0, 0.10, 2)

        sec, _ = self._section(g, "Sepia Tone", "sepia")

        sec, _ = self._section(g, "Posterize", "posterize")
        self._slider(sec, "Color levels  (2=brutal  16=subtle)",
                     "posterize_levels", 2, 16, 4, 1, 0)

        # ── SHARPENING & GLOW ─────────────────────────────────────────────
        g = self._group(self.fframe, "SHARPENING & GLOW")

        sec, _ = self._section(g, "Sharpen", "sharpen")
        self._slider(sec, "Amount", "sharpen_amt", 0.5, 5.0, 1.5, 0.5, 0)

        sec, _ = self._section(g, "Blur / Dreamy", "blur")
        self._slider(sec, "Sigma", "blur_sigma", 1.0, 20.0, 4.0, 1.0, 0)

        sec, _ = self._section(g, "Neon Bloom", "neon")
        self._slider(sec, "Saturation boost", "neon_sat",     1.0, 5.0, 3.0, 0.5,  0)
        self._slider(sec, "Bloom radius",      "neon_bloom",   4,   24,  12,  2,    1)
        self._slider(sec, "Bloom opacity",     "neon_opacity", 0.1, 1.0, 0.7, 0.05, 2)

        sec, _ = self._section(g, "Soft Glow", "glow")
        self._slider(sec, "Radius",  "glow_sigma",   4,   24, 10,   2,    0)
        self._slider(sec, "Opacity", "glow_opacity", 0.1, 1.0, 0.4, 0.05, 1)

        # ── ARTISTIC ──────────────────────────────────────────────────────
        g = self._group(self.fframe, "ARTISTIC")

        sec, _ = self._section(g, "Halftone", "halftone")
        self._slider(sec, "Cell size (px)  — dot pitch", "halftone_cell", 4, 30, 8, 1, 0)
        self._slider(sec, "Dot size  (0.3=small  1.0=solid)", "halftone_dot_scale", 0.3, 1.0, 0.85, 0.05, 1)
        self._checkbox(sec, "BW mode  (dark dots on transparent)", "halftone_bw", False, 2, 0)
        tk.Label(sec, bg=C["panel"], fg=C["muted"], font=self.fn_small,
                 text="Note: halftone is Pillow-processed — may be slow on long animations."
                 ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(2,0))

        sec, _ = self._section(g, "Thermal Camera", "thermal")
        tk.Label(sec, bg=C["panel"], fg=C["muted"], font=self.fn_small,
                 text="FLIR heat map: dark=purple/blue  mid=green  bright=red/white"
                 ).grid(row=0, column=0, columnspan=3, sticky="w", pady=2)

        sec, _ = self._section(g, "Sketch / Pencil", "sketch")
        self._slider(sec, "Line softness (sigma)", "sketch_sigma", 2, 20, 6, 1, 0)

        # Single StringVar radio group — no duplicate widgets
        self.params["sketch_mode"] = tk.StringVar(value="bw")
        mode_frame = tk.Frame(sec, bg=C["panel"])
        mode_frame.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4,2))
        for label, val in [("BW", "bw"), ("Color", "color"),
                            ("Inverted", "inverted"), ("Tinted", "tinted")]:
            tk.Radiobutton(
                mode_frame, text=label, value=val,
                variable=self.params["sketch_mode"],
                bg=C["panel"], fg=C["text"],
                selectcolor=C["highlight"],
                activebackground=C["panel"],
                font=self.fn_small
            ).pack(side="left", padx=6)

        # Tint sub-controls shown below the mode selector
        tint_sub = tk.Frame(sec, bg=C["panel"])
        tint_sub.grid(row=2, column=0, columnspan=3, sticky="w", pady=(2,0))

        # Sketch tint hue and sat params (separate from main tint filter)
        self.params["sketch_tint_hue"] = tk.DoubleVar(value=110)
        self.params["sketch_tint_sat"] = tk.DoubleVar(value=4.0)

        tk.Label(tint_sub, text="Tint color:", bg=C["panel"],
                 fg=C["text"], font=self.fn_small).grid(row=0, column=0, sticky="w", padx=(0,6))

        # Color swatch row (reuse same presets)
        import colorsys as _tcs
        def _hrgb(h, s=0.85, v=0.85):
            r,g,b = _tcs.hsv_to_rgb(h/360,s,v)
            return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

        swatch_frame = tk.Frame(tint_sub, bg=C["panel"])
        swatch_frame.grid(row=0, column=1, columnspan=6, sticky="w")
        _sketch_tint_presets = [
            ("Red",0,3.5),("Orange",25,3.5),("Yellow",50,3.5),
            ("Green",110,3.5),("Cyan",160,3.5),("Blue",215,3.5),
            ("Purple",265,3.5),("Pink",300,3.5),("Magenta",330,3.5),
        ]
        for i,(name,hue,sat) in enumerate(_sketch_tint_presets):
            tk.Button(
                swatch_frame, text=name,
                bg=_hrgb(hue), fg="#fff",
                font=self.fn_small, relief="flat", cursor="hand2",
                width=6, pady=1,
                command=lambda h=hue,s=sat: (
                    self.params["sketch_tint_hue"].set(h),
                    self.params["sketch_tint_sat"].set(s)
                )
            ).grid(row=0, column=i, padx=1)

        tk.Label(tint_sub, text="Hue (°)", bg=C["panel"],
                 fg=C["text"], font=self.fn_small).grid(row=1, column=0, sticky="w", pady=2)
        tk.Scale(tint_sub, variable=self.params["sketch_tint_hue"],
                 from_=-180, to=180, resolution=1, orient="horizontal",
                 bg=C["panel"], fg=C["text"], troughcolor=C["accent"],
                 highlightthickness=0, font=self.fn_small, length=180,
                 showvalue=True, sliderlength=14, activebackground=C["highlight"]
                 ).grid(row=1, column=1, sticky="w")

        tk.Label(tint_sub, text="Saturation", bg=C["panel"],
                 fg=C["text"], font=self.fn_small).grid(row=2, column=0, sticky="w")
        tk.Scale(tint_sub, variable=self.params["sketch_tint_sat"],
                 from_=0.0, to=12.0, resolution=0.1, orient="horizontal",
                 bg=C["panel"], fg=C["text"], troughcolor=C["accent"],
                 highlightthickness=0, font=self.fn_small, length=180,
                 showvalue=True, sliderlength=14, activebackground=C["highlight"]
                 ).grid(row=2, column=1, sticky="w")

    def _update_ps1_label(self):
        lvl = int(self.params["ps1_level"].get())
        self.ps1_label.configure(text=PS1_LABEL.get(lvl, ""))

    def _build_tint_picker(self, parent):
        """Color preset swatches + fine controls + mono mode + animate."""
        import colorsys as cs

        def hue_to_rgb(h, s=0.85, v=0.85):
            r,g,b = cs.hsv_to_rgb(h/360, s, v)
            return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

        self.params["tint_hue"]  = tk.DoubleVar(value=0)
        self.params["tint_sat"]  = tk.DoubleVar(value=4.0)
        self.params["tint_mono"] = tk.BooleanVar(value=False)

        # Color swatch grid
        grid = tk.Frame(parent, bg=C["panel"])
        grid.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0,6))
        cols = 7
        for i, (name, hue, sat) in enumerate(TINT_PRESETS):
            r, c = divmod(i, cols)
            bg_c = hue_to_rgb(hue) if name != "None" else "#3a3a3a"
            tk.Button(
                grid, text=name, bg=bg_c, fg="#fff",
                font=self.fn_small, relief="flat", cursor="hand2",
                width=7, pady=2,
                command=lambda h=hue, s=sat: self._apply_tint(h, s)
            ).grid(row=r, column=c, padx=1, pady=1)

        # Mono recolor toggle
        tk.Checkbutton(
            parent, text="Mono recolor (desaturate then tint — works on any image)",
            variable=self.params["tint_mono"],
            bg=C["panel"], fg=C["blue"],
            selectcolor=C["highlight"], activebackground=C["panel"],
            font=self.fn_small
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0,4))

        # Fine control sliders
        tk.Label(parent, text="Hue angle (°)", bg=C["panel"],
                 fg=C["text"], font=self.fn_small).grid(row=2, column=0, sticky="w")
        tk.Scale(parent, variable=self.params["tint_hue"],
                 from_=-180, to=180, resolution=1, orient="horizontal",
                 bg=C["panel"], fg=C["text"], troughcolor=C["accent"],
                 highlightthickness=0, font=self.fn_small, length=200,
                 showvalue=True, sliderlength=14, activebackground=C["highlight"]
                 ).grid(row=2, column=1, sticky="w")

        tk.Label(parent, text="Saturation", bg=C["panel"],
                 fg=C["text"], font=self.fn_small).grid(row=3, column=0, sticky="w")
        tk.Scale(parent, variable=self.params["tint_sat"],
                 from_=0.0, to=12.0, resolution=0.1, orient="horizontal",
                 bg=C["panel"], fg=C["text"], troughcolor=C["accent"],
                 highlightthickness=0, font=self.fn_small, length=200,
                 showvalue=True, sliderlength=14, activebackground=C["highlight"]
                 ).grid(row=3, column=1, sticky="w")

        # Animate
        self.params["tint_anim_on"] = tk.BooleanVar(value=False)
        tk.Checkbutton(parent, text="Animate (oscillate hue)",
                       variable=self.params["tint_anim_on"],
                       bg=C["panel"], fg=C["text"], selectcolor=C["highlight"],
                       activebackground=C["panel"], font=self.fn_small
                       ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(4,0))

        self.params["tint_swing"]  = tk.DoubleVar(value=60)
        self.params["tint_period"] = tk.DoubleVar(value=14)
        for row, label, key, from_, to, res in [
            (5, "  Swing (°)",  "tint_swing",  10, 180, 10),
            (6, "  Period (s)", "tint_period",  2,  30,  1),
        ]:
            tk.Label(parent, text=label, bg=C["panel"],
                     fg=C["text"], font=self.fn_small).grid(row=row, column=0, sticky="w")
            tk.Scale(parent, variable=self.params[key],
                     from_=from_, to=to, resolution=res, orient="horizontal",
                     bg=C["panel"], fg=C["text"], troughcolor=C["accent"],
                     highlightthickness=0, font=self.fn_small, length=200,
                     showvalue=True, sliderlength=14, activebackground=C["highlight"]
                     ).grid(row=row, column=1, sticky="w")

    def _apply_tint(self, hue, sat):
        self.params["tint_hue"].set(hue)
        self.params["tint_sat"].set(sat)
        log.debug(f"tint preset hue={hue} sat={sat}")

    # ── Presets tab ───────────────────────────────────────────────────────
    def _build_presets_tab(self, p):
        hdr = tk.Frame(p, bg=C["bg"]); hdr.pack(fill="x", padx=12, pady=(10,4))
        lbl(hdr, "PRESETS", C["highlight"], self.fn_h2).pack(side="left")
        lbl(hdr, "  — load then tweak in Filters tab", C["muted"], self.fn_small).pack(side="left")

        canvas = tk.Canvas(p, bg=C["bg"], highlightthickness=0)
        sb     = ttk.Scrollbar(p, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); canvas.pack(fill="both", expand=True)
        pf = tk.Frame(canvas, bg=C["bg"])
        win = canvas.create_window((0,0), window=pf, anchor="nw")
        pf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        self.preset_status = lbl(p, "", C["green"], self.fn_small)
        self.preset_status.pack(side="bottom", padx=12, pady=4, anchor="w")

        for i, (name, meta) in enumerate(FILTER_PRESETS.items()):
            r, c = divmod(i, 2)
            card = tk.Frame(pf, bg=C["panel"]); card.grid(row=r, column=c, padx=6, pady=4, sticky="nsew")
            pf.columnconfigure(c, weight=1)
            tk.Label(card, text=name, bg=C["accent"], fg=C["highlight"],
                     font=self.fn_h2, anchor="w", padx=8).pack(fill="x")
            tk.Label(card, text=meta["desc"], bg=C["panel"], fg=C["text"],
                     font=self.fn_small, justify="left", anchor="w",
                     padx=8, pady=4, wraplength=340).pack(fill="x")
            btn(card, "Load Preset", lambda n=name: self._load_preset(n),
                C["highlight"], fg="#fff", pady=3
                ).pack(fill="x", padx=8, pady=(0,8))

    def _load_preset(self, name):
        meta = FILTER_PRESETS.get(name)
        if not meta: return
        log.info(f"Loading preset: {name}")
        for k, v in self.params.items():
            if k.endswith("_on"):
                try: v.set(False)
                except: pass
        for k, val in meta["params"].items():
            if k in self.params:
                try: self.params[k].set(val)
                except Exception as e: log.warning(f"preset {k}={val}: {e}")
        self.preset_status.configure(text=f"✓ Loaded: {name}")
        if hasattr(self, "ps1_label"): self._update_ps1_label()

    # ── Banner tab ────────────────────────────────────────────────────────
    def _build_banner_tab(self, p):
        f = tk.Frame(p, bg=C["bg"]); f.pack(fill="both", expand=True, padx=16, pady=12)

        # ── Enable ────────────────────────────────────────────────────────
        self.banner_enabled = tk.BooleanVar(value=False)
        tk.Checkbutton(f, text="Enable banner stitching",
                       variable=self.banner_enabled, bg=C["bg"], fg=C["text"],
                       selectcolor=C["highlight"], activebackground=C["bg"],
                       font=self.fn_label).grid(row=0, column=0, columnspan=4,
                                                sticky="w", pady=(0,10))

        # ── Orientation ───────────────────────────────────────────────────
        tk.Label(f, text="Orientation:", bg=C["bg"], fg=C["text"],
                 font=self.fn_small).grid(row=1, column=0, sticky="w", padx=(0,8))
        self.banner_orientation = tk.StringVar(value="auto")
        orient_frame = tk.Frame(f, bg=C["bg"])
        orient_frame.grid(row=1, column=1, columnspan=3, sticky="w")
        for label, val in [("Auto-detect", "auto"),
                            ("Horizontal", "horizontal"),
                            ("Vertical",   "vertical")]:
            tk.Radiobutton(orient_frame, text=label, value=val,
                           variable=self.banner_orientation,
                           bg=C["bg"], fg=C["text"], selectcolor=C["highlight"],
                           activebackground=C["bg"], font=self.fn_small,
                           command=self._update_banner_size_label
                           ).pack(side="left", padx=6)

        # ── Size slider ───────────────────────────────────────────────────
        self._banner_size_label_var = tk.StringVar(value="Banner height (px):")
        tk.Label(f, textvariable=self._banner_size_label_var,
                 bg=C["bg"], fg=C["text"],
                 font=self.fn_small).grid(row=2, column=0, sticky="w", padx=(0,8), pady=(8,0))
        self.banner_height = tk.IntVar(value=120)
        tk.Scale(f, variable=self.banner_height, from_=20, to=600, resolution=10,
                 orient="horizontal", bg=C["bg"], fg=C["text"], troughcolor=C["accent"],
                 highlightthickness=0, font=self.fn_small, length=240,
                 showvalue=True, sliderlength=14, activebackground=C["highlight"]
                 ).grid(row=2, column=1, columnspan=3, sticky="w", pady=(8,0))
        tk.Label(f, text="  H: 720p hero ≈ 80–160px  |  V: use banner native width ÷ 4",
                 bg=C["bg"], fg=C["muted"], font=self.fn_small
                 ).grid(row=3, column=1, columnspan=3, sticky="w", pady=(0,8))

        # ── Overlap ───────────────────────────────────────────────────────
        tk.Label(f, text="Overlap:", bg=C["bg"], fg=C["text"],
                 font=self.fn_small).grid(row=4, column=0, sticky="w", padx=(0,8))
        self.banner_overlap = tk.IntVar(value=0)
        tk.Scale(f, variable=self.banner_overlap, from_=0, to=100, resolution=5,
                 orient="horizontal", bg=C["bg"], fg=C["text"], troughcolor=C["accent"],
                 highlightthickness=0, font=self.fn_small, length=240,
                 showvalue=True, sliderlength=14, activebackground=C["highlight"]
                 ).grid(row=4, column=1, columnspan=3, sticky="w")
        tk.Label(f, text="  0% = outside frame  |  100% = fully on top of animation",
                 bg=C["bg"], fg=C["muted"], font=self.fn_small
                 ).grid(row=5, column=1, columnspan=3, sticky="w", pady=(0,8))

        # ── Position grid ─────────────────────────────────────────────────
        tk.Label(f, text="Position:", bg=C["bg"], fg=C["text"],
                 font=self.fn_small).grid(row=6, column=0, sticky="nw", padx=(0,8))
        self.banner_position = tk.StringVar(value="bot-center")
        pos_frame = tk.Frame(f, bg=C["bg"])
        pos_frame.grid(row=6, column=1, columnspan=3, sticky="w")
        self._pos_buttons = {}
        for r, row_vals in enumerate([
            ["top-left","top-center","top-right"],
            ["mid-left","mid-center","mid-right"],
            ["bot-left","bot-center","bot-right"],
        ]):
            for c, val in enumerate(row_vals):
                b = tk.Button(pos_frame, text=val.replace("-","\n"), width=8, height=2,
                              bg=C["accent"], fg=C["text"], activebackground=C["highlight"],
                              font=self.fn_small, relief="flat", cursor="hand2",
                              command=lambda v=val: self._set_pos(v))
                b.grid(row=r, column=c, padx=2, pady=2)
                self._pos_buttons[val] = b
        self._set_pos("bot-center")

        # ── Info ─────────────────────────────────────────────────────────
        tk.Label(f, text=(
            "banners/  —  gb.png matches gb_dark_720p.webp  (prefix before first _)\n"
            "Formats: .png  .jpg  .jpeg  .webp  (alpha auto-cropped)\n"
            "Output is always padded back to original file resolution with transparency."
        ), bg=C["bg"], fg=C["muted"], font=self.fn_small, justify="left"
        ).grid(row=7, column=0, columnspan=4, sticky="w", pady=(10,0))

    def _update_banner_size_label(self):
        o = self.banner_orientation.get()
        if o == "vertical":
            self._banner_size_label_var.set("Banner width (px):")
        else:
            self._banner_size_label_var.set("Banner height (px):")

    def _resolve_orientation(self, banner_path):
        """Return actual orientation — auto-detect if set to 'auto'."""
        o = self.banner_orientation.get()
        if o == "auto":
            return detect_banner_orientation(banner_path)
        return o

    def _set_pos(self, val):
        self.banner_position.set(val)
        for k, b in self._pos_buttons.items():
            b.configure(bg=C["highlight"] if k==val else C["accent"])

    # ── Bottom bar ────────────────────────────────────────────────────────
    def _build_bottom(self, p):
        row1 = tk.Frame(p, bg=C["panel"]); row1.pack(fill="x", padx=10, pady=(2,0))
        tk.Label(row1, text="Output:", bg=C["panel"],
                 fg=C["text"], font=self.fn_small).pack(side="left", padx=(0,4))
        self.out_name = tk.Entry(row1, bg=C["accent"], fg=C["text"],
                                  font=self.fn_small, insertbackground=C["text"],
                                  width=24, relief="flat")
        self.out_name.insert(0, "filtered")
        self.out_name.pack(side="left", padx=(0,8))

        for text, cmd, bg, fg in [
            ("▶ Render Selected",  self._render_selected,         C["green"],     "#000"),
            ("▶▶ Render All",      self._render_all,              C["orange"],    "#000"),
            ("↺ Reset All",        self._reset_all,               C["accent"],    C["text"]),
            ("📂 Output",          lambda: os.startfile(OUTPUT_DIR), C["accent"], C["text"]),
            ("📋 Log",             lambda: os.startfile(LOG_FILE),   C["accent"], C["text"]),
        ]:
            btn(row1, text, cmd, bg, fg=fg, padx=6).pack(side="left", padx=2)

        self.progress = ttk.Progressbar(p, mode="indeterminate")
        self.progress.pack(padx=10, pady=3, fill="x")
        self.status_lbl = lbl(p, "idle", C["muted"], self.fn_small)
        self.status_lbl.pack(fill="x", padx=10)
        lbl(p, "LOG", C["highlight"], self.fn_small).pack(anchor="w", padx=10)
        lf = tk.Frame(p, bg=C["panel"]); lf.pack(fill="x", padx=10, pady=(0,4))
        sb = tk.Scrollbar(lf); sb.pack(side="right", fill="y")
        self.log_widget = tk.Text(lf, height=5, bg="#0d1117", fg=C["text"],
                                   font=self.fn_small, yscrollcommand=sb.set,
                                   relief="flat", state="disabled", wrap="word")
        self.log_widget.pack(fill="x")
        sb.config(command=self.log_widget.yview)

    # ── Widget helpers ────────────────────────────────────────────────────
    def _group(self, parent, title):
        outer = tk.Frame(parent, bg=C["bg"]); outer.pack(fill="x", padx=4, pady=(10,2))
        tk.Label(outer, text=f"── {title} ──", bg=C["bg"],
                 fg=C["blue"], font=self.fn_label).pack(anchor="w", padx=4)
        inner = tk.Frame(outer, bg=C["bg"]); inner.pack(fill="x")
        return inner

    def _section(self, parent, label, key_prefix):
        outer = tk.Frame(parent, bg=C["panel"]); outer.pack(fill="x", padx=4, pady=2)
        hdr   = tk.Frame(outer, bg=C["accent"]); hdr.pack(fill="x")
        en    = tk.BooleanVar(value=False); self.params[f"{key_prefix}_on"] = en
        tk.Checkbutton(hdr, variable=en, text=label,
                       bg=C["accent"], fg=C["text"], selectcolor=C["highlight"],
                       activebackground=C["accent"], font=self.fn_label,
                       anchor="w", relief="flat"
                       ).pack(side="left", padx=8, pady=3)
        body = tk.Frame(outer, bg=C["panel"]); body.pack(fill="x", padx=10, pady=(0,5))
        return body, en

    def _slider(self, parent, label, key, from_, to, default, res=1, row=0):
        tk.Label(parent, text=label, bg=C["panel"], fg=C["text"],
                 font=self.fn_small, anchor="w"
                 ).grid(row=row, column=0, sticky="w", padx=(0,8), pady=1)
        var = tk.DoubleVar(value=default); self.params[key] = var
        tk.Scale(parent, variable=var, from_=from_, to=to, resolution=res,
                 orient="horizontal", bg=C["panel"], fg=C["text"],
                 troughcolor=C["accent"], highlightthickness=0, font=self.fn_small,
                 length=180, showvalue=True, sliderlength=14,
                 activebackground=C["highlight"]
                 ).grid(row=row, column=1, sticky="w", pady=1)
        return var

    def _checkbox(self, parent, label, key, default=False, row=0, col=2):
        var = tk.BooleanVar(value=default); self.params[key] = var
        tk.Checkbutton(parent, text=label, variable=var,
                       bg=C["panel"], fg=C["text"], selectcolor=C["highlight"],
                       activebackground=C["panel"], font=self.fn_small
                       ).grid(row=row, column=col, sticky="w", padx=4)
        return var

    # ── Logging ───────────────────────────────────────────────────────────
    def _ui_log(self, msg, color=None):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_widget.configure(state="normal")
        tag = f"t{ts}{id(msg)}"
        self.log_widget.insert("end", f"[{ts}] {msg}\n", tag)
        if color: self.log_widget.tag_configure(tag, foreground=color)
        self.log_widget.see("end")
        self.log_widget.configure(state="disabled")
        log.info(f"UI: {msg}")

    def _status(self, msg):
        self.status_lbl.configure(text=msg)

    # ── File list ─────────────────────────────────────────────────────────
    def _refresh_file_list(self):
        self.file_list.delete(0, "end")
        files = sorted(glob.glob(os.path.join(INPUT_DIR, "*.webp")))
        for f in files: self.file_list.insert("end", os.path.basename(f))
        if files: self.file_list.select_set(0); self._on_file_select(None)
        self._ui_log(f"Found {len(files)} file(s) in input/")

    def _on_file_select(self, event):
        sel = self.file_list.curselection()
        if not sel: return
        name = self.file_list.get(sel[0])
        self.out_name.delete(0,"end")
        self.out_name.insert(0, f"{os.path.splitext(name)[0]}_filtered")
        bp = find_banner(name)
        self.banner_lbl.configure(
            text=f"banner: {os.path.basename(bp)}" if bp else "banner: none",
            fg=C["green"] if bp else C["muted"])
        frame = first_frame(os.path.join(INPUT_DIR, name))
        if frame: self._set_thumb(frame)

    def _set_thumb(self, img):
        t = img.copy(); t.thumbnail((210,140))
        self._thumb_photo = ImageTk.PhotoImage(t)
        self.thumb_lbl.configure(image=self._thumb_photo, text="")

    def _get_params(self):
        return {k: v.get() for k, v in self.params.items()}

    # ── Reset all ─────────────────────────────────────────────────────────
    def _reset_all(self):
        log.info("Reset all params")
        for k, v in self.params.items():
            if k.endswith("_on"):
                try: v.set(False)
                except: pass
            elif k in PARAM_DEFAULTS:
                try: v.set(PARAM_DEFAULTS[k])
                except Exception as e: log.warning(f"reset {k}: {e}")
        if hasattr(self, "ps1_label"): self._update_ps1_label()
        self._ui_log("All filters reset to defaults.", C["blue"])

    # ── Preview popup ─────────────────────────────────────────────────────
    def _preview(self):
        sel = self.file_list.curselection()
        if not sel: messagebox.showwarning("No file", "Select a file first."); return
        name = self.file_list.get(sel[0])
        path = os.path.join(INPUT_DIR, name)
        p    = self._get_params()
        vf   = build_vf(p)
        log.info(f"Preview: {name} filter={'yes' if vf else 'no'}")
        self._ui_log("Generating preview...", C["orange"])
        self._status("Generating preview...")
        self.progress.start(10)

        def worker():
            try:
                frame = first_frame(path)
                if not frame:
                    self.after(0, lambda: self._ui_log("Could not read frame.", C["highlight"]))
                    self.after(0, self.progress.stop); return
                tmp = tempfile.mkdtemp(prefix="ffui_prev_")
                inp = os.path.join(tmp, "frame_0000.png")
                out = os.path.join(tmp, "preview.png")
                frame.save(inp)
                orig_w, orig_h = frame.size
                # Apply Pillow halftone to the single preview frame if enabled
                if p.get("halftone_on"):
                    apply_halftone_to_frames(
                        tmp,
                        cell      = max(3, int(p.get("halftone_cell", 6))),
                        bw_mode   = bool(p.get("halftone_bw", False)),
                        dot_scale = float(p.get("halftone_dot_scale", 0.85)),
                    )

                if vf:
                    r  = _run_shell(_ffmpeg_cmd(inp, out, vf, 1.0, single=True), timeout=30)
                    ok = r.returncode == 0
                    if not ok: log.error(f"Preview ffmpeg: {r.stderr[-400:]}")
                else:
                    shutil.copy(inp, out); ok = True
                # Apply banner AFTER filter (same as render pipeline)
                if ok and self.banner_enabled.get():
                    bp = find_banner(name)
                    if bp:
                        orient  = self._resolve_orientation(bp)
                        banner  = load_banner(bp, self.banner_height.get(), orient)
                        if banner:
                            fr       = Image.open(out).convert("RGBA")
                            stitched = stitch(fr, banner,
                                             self.banner_position.get(),
                                             self.banner_overlap.get() / 100.0)
                            fit_to_canvas(stitched, orig_w, orig_h).save(out)
                            log.debug(f"Preview banner stitched ({orient} "
                                      f"overlap={self.banner_overlap.get()}%)")

                def show():
                    self.progress.stop(); self._status("idle")
                    if ok and os.path.exists(out):
                        result = Image.open(out).convert("RGBA")
                        self._show_preview_popup(result, name)
                        self._ui_log("Preview ready.", C["green"])
                    else:
                        self._ui_log("Preview failed — check ffui_debug.log",
                                     C["highlight"])
                    shutil.rmtree(tmp, ignore_errors=True)
                self.after(0, show)
            except Exception as e:
                log.error(traceback.format_exc())
                self.after(0, lambda: self._ui_log(f"Preview error: {e}", C["highlight"]))
                self.after(0, self.progress.stop)

        threading.Thread(target=worker, daemon=True).start()

    def _show_preview_popup(self, img, title):
        if self._prev_win and self._prev_win.winfo_exists():
            self._prev_win.destroy()
        win = tk.Toplevel(self)
        win.title(f"Preview — {title}")
        win.configure(bg=C["bg"])
        win.resizable(True, True)
        self._prev_win = win
        iw, ih = img.size
        # Info bar
        info = tk.Frame(win, bg=C["panel"]); info.pack(fill="x")
        tk.Label(info, text=f"{title}  |  {iw}×{ih}",
                 bg=C["panel"], fg=C["text"], font=self.fn_small,
                 padx=8, pady=4).pack(side="left")
        tk.Button(info, text="✕ Close", command=win.destroy,
                  bg=C["highlight"], fg="#fff", font=self.fn_small,
                  relief="flat", cursor="hand2", padx=6
                  ).pack(side="right", padx=6, pady=2)
        # Scrollable canvas
        cf = tk.Frame(win, bg=C["bg"]); cf.pack(fill="both", expand=True)
        hbar = ttk.Scrollbar(cf, orient="horizontal")
        vbar = ttk.Scrollbar(cf, orient="vertical")
        canvas = tk.Canvas(cf, bg="#111", highlightthickness=0,
                           xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        hbar.config(command=canvas.xview)
        vbar.config(command=canvas.yview)
        hbar.pack(side="bottom", fill="x"); vbar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        # Fit to window initially
        disp = img.copy(); disp.thumbnail((900, 580), Image.LANCZOS)
        self._prev_img = ImageTk.PhotoImage(disp)
        canvas.create_image(0, 0, anchor="nw", image=self._prev_img)
        canvas.configure(scrollregion=(0, 0, disp.width, disp.height))
        win.geometry(f"{min(disp.width+20,920)}x{min(disp.height+60,620)}")
        self._set_thumb(img)

        def show_full():
            self._prev_img = ImageTk.PhotoImage(img)
            canvas.delete("all")
            canvas.create_image(0, 0, anchor="nw", image=self._prev_img)
            canvas.configure(scrollregion=(0, 0, iw, ih))
            win.geometry(f"{min(iw+20,1400)}x{min(ih+80,900)}")

        tk.Button(info, text="↔ Full Size", command=show_full,
                  bg=C["accent"], fg=C["text"], font=self.fn_small,
                  relief="flat", cursor="hand2", padx=6
                  ).pack(side="right", padx=4, pady=2)

    # ── Render ────────────────────────────────────────────────────────────
    def _render_one(self, name, out_suffix, on_done):
        path     = os.path.join(INPUT_DIR, name)
        out_path = os.path.join(OUTPUT_DIR, f"{out_suffix}.webp")
        p        = self._get_params()
        vf       = build_vf(p)
        b_on     = self.banner_enabled.get()
        bp       = find_banner(name) if b_on else None
        if not vf and not b_on:
            self._ui_log("Nothing enabled.", C["orange"]); on_done(False, "nothing"); return
        self._ui_log(f"Extracting: {name}", C["orange"]); self._status(f"Extracting: {name}")
        orig_w, orig_h = webp_size(path)
        tmp, fps = extract_frames(path)
        if not tmp:
            self._ui_log("Extraction failed.", C["highlight"]); on_done(False, "extract"); return
        # Apply Pillow-based halftone to frames if enabled (before ffmpeg)
        if p.get("halftone_on"):
            self._ui_log("Applying halftone...", C["blue"])
            self._status("Halftone...")
            apply_halftone_to_frames(
                tmp,
                cell      = max(3, int(p.get("halftone_cell", 6))),
                bw_mode   = bool(p.get("halftone_bw", False)),
                dot_scale = float(p.get("halftone_dot_scale", 0.85)),
            )

        frames_pat = os.path.join(tmp, "frame_%04d.png")
        if not vf: vf = "copy"
        self._ui_log(f"Rendering → {os.path.basename(out_path)} @ {fps:.1f}fps")
        self._status(f"Rendering: {os.path.basename(out_path)}")

        def done_cb(ok, msg):
            shutil.rmtree(tmp, ignore_errors=True)
            if not ok:
                self._ui_log("✗ Failed — check ffui_debug.log", C["highlight"])
                self._status("Error — check log")
                on_done(False, msg)
                return
            # ── Banner stitch AFTER filter render ────────────────────────
            if b_on and bp:
                orient = self._resolve_orientation(bp)
                self._ui_log(
                    f"Stitching banner: {os.path.basename(bp)} "
                    f"({orient}, overlap={self.banner_overlap.get()}%)", C["blue"])
                self._status("Stitching banner...")
                ok2 = stitch_banner_onto_output(
                    out_path, bp,
                    self.banner_height.get(),
                    self.banner_position.get(),
                    self.banner_overlap.get() / 100.0,
                    orient,
                    orig_w, orig_h
                )
                if not ok2:
                    self._ui_log("Banner stitch failed — output saved without banner.",
                                 C["orange"])
            elif b_on and not bp:
                self._ui_log(f"No banner found for '{name}'", C["muted"])
            sz = os.path.getsize(out_path) if os.path.exists(out_path) else 0
            self._ui_log(f"✓ {os.path.basename(out_path)} ({sz//1024} KB)", C["green"])
            self._status(f"Done: {os.path.basename(out_path)}")
            on_done(True, msg)

        run_ffmpeg(frames_pat, out_path, vf, fps, done_cb)

    def _render_selected(self):
        sel = self.file_list.curselection()
        if not sel: messagebox.showwarning("No file", "Select a file first."); return
        name = self.file_list.get(sel[0])
        sfx  = self.out_name.get().strip() or "filtered"
        self.progress.start(10)
        self._render_one(name, sfx, lambda ok,m: self.after(0, self.progress.stop))

    def _render_all(self):
        files = [self.file_list.get(i) for i in range(self.file_list.size())]
        if not files: messagebox.showwarning("No files", "No files in input/"); return
        self.progress.start(10)
        self._ui_log(f"Rendering all {len(files)} file(s)...", C["orange"])

        def next_file(i):
            if i >= len(files):
                self.after(0, self.progress.stop)
                self._ui_log("All done.", C["green"]); self._status("All done."); return
            n = files[i]
            self._ui_log(f"[{i+1}/{len(files)}] {n}", C["orange"])
            self._render_one(n, f"{os.path.splitext(n)[0]}_filtered",
                             lambda ok,m: self.after(0, lambda: next_file(i+1)))

        next_file(0)

    def on_close(self):
        for d in self._tmp_dirs: shutil.rmtree(d, ignore_errors=True)
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if not os.path.exists(FFMPEG):
        log.warning(f"FFmpeg not found: {FFMPEG}")
        print(f"\nWARNING: ffmpeg not found.\nPlace ffmpeg.exe in: {SCRIPT_DIR}\nor add to PATH.\n")
    app = FilterUI()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
    log.info("Exited")
