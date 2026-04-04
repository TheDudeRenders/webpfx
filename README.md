# WebP Filter Studio

A desktop GUI tool for applying visual filters to animated `.webp` files — built for emulation frontend logo animations (ES-DE, Batocera, etc.) but works on any animated WebP.

![Preview](preview.webp)

> ⚠️ **AISLOP ALERT:** This tool was vibecoded with AI in like an hour. It works, but the code is what it is. Use at your own risk.

---

## Features

- **13+ filters** organized in groups: Pixelize, Dither, PS1/Low-Res, CRT Scanlines, VHS, Color Tint (with mono recolor), Brightness/Contrast/Saturation, Sepia, Posterize, Thermal Camera, Sharpen, Blur, Neon Bloom, Soft Glow, Sketch/Pencil, Halftone, Reverse Animation
- **12 presets**: PS1 Style, Acid Trip, Pip-Boy, Pixel+CRT, VHS Retro, Neon Arcade, Pencil Sketch, Sepia Film, Glitch, Gameboy, Neon Glow+Pixel, Thermal Camera
- **Banner stitching**: auto-match banner images to animations by filename prefix, with position grid, overlap slider, and orientation detection
- **Live preview**: single-frame preview popup before committing to a full render
- **Render Selected** or **Render All** with progress logging
- **Reset All** button to clear all filters back to defaults
- Fully logged to `ffui_debug.log` for debugging

---

## Requirements

- **Python 3.8+** — [python.org](https://www.python.org/downloads/) or Windows Store
- **Pillow** — install with pip (see below)
- **FFmpeg** — either on system PATH or placed as `ffmpeg.exe` in the same folder as the script

---

## Installation

### 1. Install Python

Download from [python.org](https://www.python.org/downloads/) and install. During installation check **"Add Python to PATH"**.

The Windows Store version also works fine.

### 2. Install Pillow

Open a terminal or command prompt and run:

```
pip install Pillow
```

**or if that doesnt work**

```
python -m pip install pillow
```

### 3. Get FFmpeg

Download a full build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) (Windows) or [ffmpeg.org](https://ffmpeg.org/download.html).

Either:
- Add `ffmpeg` to your system PATH, **or**
- Place `ffmpeg.exe` directly in the same folder as `webpfx.py`

### 4. Download and set up the folder

Download **GUI.7z** from the [latest release](https://github.com/TheDudeRenders/webpfx/releases) and extract it.

> ⚠️ **Do not use the "Source code" zip** that GitHub auto-generates on the release page — download **GUI.7z** specifically.

You should end up with a folder that looks like this:
```
webpfx/
├── ffmpeg_filter_ui.py
├── PLACE FFMPEG.EXE HERE OR ADD TO PATH    ← see step 3
├── input/                                  ← put your .webp files here
├── output/                                 ← filtered results appear here
└── banners/                                ← (optional) banner images
```

The `input/`, `output/`, and `banners/` folders are created automatically on first run if they don't exist.

## Usage

### Running the tool

Double-click `webpfx.py`

### Basic workflow

1. Drop your animated `.webp` files into the `input/` folder
2. Click **Refresh** in the file list if you don't see them
3. Select a file, pick a preset or enable filters and adjust sliders (You can pick a preset and then adjust sliders in the filters tab)
4. Click **Preview Frame** to see a single-frame preview before rendering
5. Click **Render Selected** or **Render All**
6. Results appear in `output/`

There is also a Reset All button at the bottom to reset all filters and revert back to defaults

### Filters tab

Filters are grouped by category. Enable a filter with its checkbox then adjust sliders. Multiple filters stack in a fixed processing order: pixel/color effects first, then sharpening/glow, then CRT/VHS on top.

### Presets tab

Click **Load Preset** to zero all filters and apply a preset configuration. You can then tweak individual sliders before rendering.

### Banner Stitch tab

Place banner images in the `banners/` folder named to match your animation prefix:

```
banners/gc.png     matches    input/GC_dark_720p.webp
banners/nes.png    matches    input/NES_light_720p.webp
banners/gba.png    matches    input/GBA_dark_720p.webp
```

Matching uses the prefix before the first underscore, case-insensitive. Enable banner stitching, set height, overlap, and position, then render. Output is always padded back to the original animation resolution with transparency.
The tool handles both vertical and horizontal banners and will auto detect the orientation. You can adjust manually with the toggles.

---

## Troubleshooting

- **Crashes on launch** — check `ffui_debug.log` in the script folder
- **Preview fails** — FFmpeg not found; check PATH or place `ffmpeg.exe` in the script folder
- **Banner not matching** — check the log for `find_banner:` lines showing what prefix was searched
- **Halftone is slow** — it's processed frame by frame in Python rather than ffmpeg; expected on long animations

---

## License

Do whatever you want with it.
