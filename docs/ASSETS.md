# FreeTVOS artwork specification

Every asset below is consumed by something concrete in the image. Nothing here
is decorative-only, and each entry says which file or package reads it.

## The one rule that governs all of it: overscan

Televisions still crop. Many sets, and nearly every set connected over HDMI
with a legacy mode, discard the outer edge of the frame. Broadcast practice
assumes it and so should we.

| Zone | Fraction of frame | On 1920x1080 | Rule |
|---|---|---|---|
| Action safe | inner 93% | 1786x1004, inset 67x38 | Nothing important outside this |
| Title safe | inner 90% | 1728x972, inset 96x54 | All text and logos inside this |

Background art bleeds to the full frame. Logos, wordmarks, and any text sit
inside title safe. A logo centred in the frame is always safe; a logo in a
corner usually is not.

## Viewing distance

Design for roughly 3 metres, not 50 centimetres. The practical consequences:
minimum body text of 24px at 1080p, minimum touch-equivalent focus target of
96x96px, and no hairline strokes below 2px, which disappear on a panel with
any sharpening applied. Contrast should clear WCAG AA at 4.5:1, and pure white
on pure black is worth avoiding because it blooms on OLED at low ambient light.

## Palette

Defined once in `brand/brand.env` and read by every build step.

| Token | Value | Use |
|---|---|---|
| `BRAND_BG` | `#0B0E14` | Page and shell ground |
| `BRAND_SURFACE` | `#151A23` | Tiles, cards, sheets |
| `BRAND_ACCENT` | `#3DDC97` | Focus ring, active state |
| `BRAND_ACCENT_ALT` | `#4EA8FF` | Links, secondary highlight |
| `BRAND_TEXT` | `#E6EAF2` | Primary text, deliberately not #FFF |
| `BRAND_TEXT_DIM` | `#8C97AB` | Secondary text |

## What to produce

### 1. Identity marks

| Asset | Format | Size | Notes |
|---|---|---|---|
| Logo mark | SVG | square viewBox | Must read at 48px; no gradients finer than 2px |
| Logo mark raster | PNG | 512, 256, 128, 64, 48, 32, 24, 22, 16 | Generated from the SVG |
| Wordmark | SVG | horizontal lockup | Separate file, not baked into the mark |
| Mark on light | SVG | square | A single-colour variant for light surfaces |

Install to `/usr/share/icons/hicolor/<size>/apps/freetvos.png` and
`/usr/share/icons/hicolor/scalable/apps/freetvos.svg`. Referenced by the
`LOGO=` key in os-release and by the About screen.

### 2. Boot splash (Plymouth)

Read by the `plymouth` package, configured through the kernel arguments in
`image/config.toml.in`.

| Asset | Format | Size | Notes |
|---|---|---|---|
| Splash logo | PNG, alpha | 640x640 | Centred; stays inside title safe at 1080p |
| Progress spinner | PNG sequence or single | 128x128 per frame | 24 or 36 frames if animated |
| Background | PNG | 1920x1080 | Flat `BRAND_BG` is fine and cheapest |

Plymouth scales one asset set across resolutions, so author at 1080p and let it
scale down. A 4K set will upscale the logo, which is why 640px is generous.

### 3. Shell wallpaper

Read by Plasma Bigscreen as the home screen ground.

| Asset | Format | Size | Notes |
|---|---|---|---|
| Wallpaper 4K | JPEG or PNG | 3840x2160 | The master |
| Wallpaper 1080p | JPEG or PNG | 1920x1080 | Downscaled variant |

Keep it dark and low-contrast in the upper third, where the shell draws the
clock and status. Busy wallpaper behind a tile grid makes focus state hard to
see, which is the single most important affordance on a remote-driven UI.

### 4. Service tiles

One per file in `webapps/apps.d`. These are what the home screen grid shows,
and they are the assets the project most needs.

| Asset | Format | Size | Notes |
|---|---|---|---|
| Tile icon | SVG | square | Preferred; scales to any grid density |
| Tile icon raster | PNG, alpha | 512x512 and 256x256 | Fallback |
| Wide banner | PNG | 1600x900, 16:9 | Optional, for a featured or hero row |

Name them to match the `ICON=` key already set in each `.app` file, so
`freetvos-netflix.svg`, `freetvos-plex.svg`, and so on. Install under
`/usr/share/icons/hicolor/scalable/apps/`.

A caution worth stating plainly: the service logos are trademarks belonging to
their owners. Using them to label a launcher that opens the real service is
ordinarily defensible as nominative use, but redistributing those marks inside
a downloadable image is a different act from a user placing them on their own
device. The safe pattern, and the one LibreELEC and similar projects use, is to
ship neutral generic tiles and let the first run fetch or the user supply the
real artwork.

### 5. Installer media

Only needed once `make iso` output is distributed.

| Asset | Format | Size | Notes |
|---|---|---|---|
| Anaconda sidebar | PNG | 800x600 | Left panel of the installer |
| Anaconda topbar | PNG | 800x45 | Product name strip |
| ISO volume icon | PNG | 512x512 | Shown when the image is mounted |

## Producing the raster sizes

Every PNG comes from an SVG, and none is drawn by hand, so a change to a master
reaches every size in one step:

```bash
tools/gen-assets.sh          # the derived SVGs, every PNG, then a coverage check
tools/gen-assets.sh png      # only the PNGs, after editing a master
```

It runs in a container holding `rsvg-convert` and Noto Sans, so nothing is
installed on the machine running it, and the image build needs no rasteriser:
it copies the finished PNGs. `make lint` runs the coverage check, which fails if
a service has no tile or any PNG is missing or the wrong size.

These are drawn by hand:

| Master | What it is |
|---|---|
| `brand/icons/freetvos.svg` | The mark on its tile |
| `brand/icons/freetvos-*.svg` | Every service and feature tile |
| `brand/logo/freetvos-glyph.svg` | The mark without its tile |
| `brand/logo/freetvos-mark-light.svg` | One colour, for light surfaces |
| `brand/logo/freetvos-small.svg` | The mark redrawn for 24px and below |
| `brand/splash/throbber.svg` | One spinner frame |

The wordmarks, banners, wallpaper, splash background and installer art are SVGs
too, written by `tools/gen-assets.py` from those masters and `brand/brand.env`.
Their text is outlined from Noto Sans, the interface's own font, so no PNG
depends on the fonts of whatever machine drew it. They are committed; edit what
they are made from, not them.

| Asset | Generated as | Read by |
|---|---|---|
| Mark, 512 down to 16 | `brand/png/hicolor/<size>/apps/freetvos.png` | os-release `LOGO=`, from `/usr/share/icons/hicolor` |
| Tiles, 512 and 256 | `brand/png/hicolor/<size>/apps/freetvos-*.png` | The same, beside each tile's SVG |
| Splash logo, 640 | `brand/png/splash/logo.png` | Plymouth, and the Plasma session splash |
| Wallpaper, 4K and 1080p | `brand/png/wallpaper/` | The home screen |
| Wordmark, dark and light | `brand/png/logo/freetvos-wordmark*.png` | Nothing in the image yet |
| Mark on light | `brand/png/logo/freetvos-mark-light.png` | Nothing in the image yet |
| Spinner, 24 frames at 128 | `brand/png/splash/throbber-*.png` | Nothing: the theme shows a still mark on purpose |
| Splash background, 1080p | `brand/png/splash/background.png` | Nothing: the theme paints the colour itself |
| Banners, 1600x900 | `brand/png/banners/freetvos-<id>.png` | Nothing yet: no screen has a featured row |
| Installer sidebar, topbar, volume icon | `brand/png/installer/` | Nothing: bootc-image-builder's ISO takes no artwork |

The small mark exists because the full one does not survive 16px: its stand and
foot smear into one blob and the play symbol becomes a speck. The small drawing
runs the tile to the edge and gives every part at least two pixels. It is used
at 24px and below; from 32px the full mark reads.
