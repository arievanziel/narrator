# GUI Variant Screenshots — AI Analysis Index

## Overview

This directory contains 110 screenshots of 11 GUI variants for an AI storytelling narrator app. Each variant was captured in 10 different UI states. The purpose is to allow a visual AI to analyze the UI controls and suggest improvements.

## Screenshot Format

- Resolution: 2560x1600 (2x device scale, viewport 1280x800)
- Format: PNG
- Naming convention: `{variant-name}_{state-id}.png`

## Variants

### Base Versions (2)

| Variant | File | Description |
|---------|------|-------------|
| base-ink-extended | ink-extended.html | Base light version with floating circle buttons. The original Ink aesthetic. |
| base-ink-dark | ink-dark.html | Dark version of the base with warm dark palette. |

### Standard Variants (6)

| Variant | File | Control Approach |
|---------|------|-----------------|
| v1-bookmark | v1-bookmark.html | Side panel toggles as vertical bookmark/pull-tabs at screen edges. Top/bottom bars use horizontal bookmark-style tabs that stay visible as use-cues and move with the bars. |
| v2-topbar-cmd | v2-topbar-cmd.html | All controls in a thin always-visible top bar (30px). Side panel toggles, bottom bar toggle — everything in one place. No floating buttons. Top bar cannot be hidden. |
| v3-edge-rails | v3-edge-rails.html | Thin 3px vertical rails on screen edges for side panels. Thin 2px horizontal rails for top/bottom bars. Tiny dots at rail centers as use-cues. Pure geometry — no buttons, no text. |
| v4-audio-hub | v4-audio-hub.html | Audio bar is the control hub. When expanded: panel/bar toggles on its right side. When collapsed: tiny dots on the line provide access. Everything from the audio bar. |
| v5-ultra-minimal | v5-ultra-minimal.html | Everything is 4px dots and 1px lines. Click dots to toggle. Hover enlarges to 6px. No text, no icons, no buttons. Maximum minimalism. |
| v9-circle-buttons | v9-circle-buttons.html | Round circle buttons everywhere: half-round tabs on screen edges for side panels, half-round tabs at center for top/bottom bars, small circle toggles in the top bar, and small circle toggles in the audio bar. All locations sync active state. |

### Creative / Book-Inspired Variants (3)

| Variant | File | Control Approach |
|---------|------|-----------------|
| v6-ribbons | v6-ribbons.html | Silk ribbon bookmarks hanging from the top edge with subtle sway animation. Each ribbon has an icon at its tip. Ribbons shorten when "pulled" (panel open). Tapered ends, sheen animation, drop shadows. |
| v7-dog-ears | v7-dog-ears.html | Foldable triangular corners at the four corners of the reading area. Click to fold/unfold. Each corner controls a panel or bar. Corners lift on hover. Drop shadows for 3D depth. Icon labels on folds. |
| v8-margin-marks | v8-margin-marks.html | Pencil annotation marks in the margins — hand-drawn looking brackets and underlines. Marks darken on hover. Italic serif labels appear on hover. Active state gets a subtle outline. |

## States Captured

Each variant was captured in these 10 states:

| State ID | Description | What to Look For |
|----------|-------------|------------------|
| default | Everything collapsed/hidden, just reading | How unobtrusive the controls are when reading. Is the reading area clean? Are controls discoverable? |
| left-panel | Left panel open (character/inventory) | How the left panel toggle looks when active. Does the toggle move correctly? Is the panel content readable? |
| right-panel | Right panel open (settings) | How the settings panel toggle looks when active. Is the settings panel readable? |
| both-panels | Both side panels open simultaneously | Do both panels work together? Is the reading area still usable? Do both toggles show active state? |
| topbar | Top bar visible (status bar) | Does the top bar show HP, AC, level, turn, location, time? Do the side panel toggles move down with the top bar? |
| bottombar | Bottom bar visible (info bar) | Does the bottom bar show location, save status, TTS model? Is the bottom bar tab above the audio line? |
| all-bars | All bars visible (top + bottom) | Do both bars work together? Is the layout balanced? |
| audio-expanded | Audio bar expanded (full controls) | Does the audio bar show play/pause, progress, label, time, skip buttons, collapse button? Is the progress line a single continuous line (not split)? |
| left-audio | Left panel + audio expanded | Do the panel and audio bar coexist well? |
| everything | Everything open (both panels + both bars + audio) | The maximum information state. Is it overwhelming or manageable? Do all controls work together? |

## What to Analyze

When reviewing these screenshots, please consider:

1. **Control discoverability**: Can a new user figure out how to open panels and bars? Are the controls visible enough without being intrusive?

2. **Control positioning**: Do the side panel toggles move correctly when the top bar opens/closes? Are they vertically attached to the side panel area, not stuck at the screen top?

3. **Audio bar**: Is the collapsed audio line a single continuous line (not split in two)? Does the expanded audio bar show all controls properly?

4. **Bottom bar tab**: Is the bottom bar reopening tab visible above the audio line? Is it clickable?

5. **Visual hierarchy**: Does the reading area remain the focus? Do controls recede when not needed?

6. **Aesthetic consistency**: Does each variant maintain the quiet Ink aesthetic (monochrome, serif, minimal)? Do the creative variants feel book-like?

7. **State transitions**: Do controls move smoothly between states? Are there any visual glitches or overlaps?

8. **Information density**: In the "everything" state, is the layout too crowded? Which variant handles maximum information best?

9. **Variant comparison**: Which variant has the best balance of discoverability and unobtrusiveness? Which creative variant is most successful as a book metaphor?

10. **Specific issues to check**:
    - v2: Are the command buttons visible and clickable in the top bar?
    - v3: Are the edge rails visible enough to discover?
    - v4: Are the audio hub controls accessible in both collapsed and expanded states?
    - v5: Are the ultra-minimal dots too small to find?
    - v6: Do the ribbons look like silk bookmarks? Is the sway animation subtle?
    - v7: Do the dog-ears look like folded page corners? Are the icons visible?
    - v8: Do the pencil marks look hand-drawn? Are the labels readable on hover?
    - v9: Are the circle buttons consistent across all three locations (edges, top bar, audio bar)?

## File Listing

All screenshots are in this directory. The manifest.json file contains a machine-readable list of all screenshots with their variant, state, and description.
