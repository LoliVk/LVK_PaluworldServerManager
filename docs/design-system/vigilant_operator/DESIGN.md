---
name: Vigilant Operator
colors:
  surface: '#f9f9f9'
  surface-dim: '#dadada'
  surface-bright: '#f9f9f9'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3f3'
  surface-container: '#eeeeee'
  surface-container-high: '#e8e8e8'
  surface-container-highest: '#e2e2e2'
  on-surface: '#1a1c1c'
  on-surface-variant: '#40493d'
  inverse-surface: '#2f3131'
  inverse-on-surface: '#f1f1f1'
  outline: '#707a6c'
  outline-variant: '#bfcab8'
  surface-tint: '#236c20'
  primary: '#003a04'
  on-primary: '#ffffff'
  primary-container: '#1a6e1a'
  on-primary-container: '#7cc870'
  inverse-primary: '#8cd97e'
  secondary: '#335ea1'
  on-secondary: '#ffffff'
  secondary-container: '#8fb6ff'
  on-secondary-container: '#144688'
  tertiary: '#620938'
  on-tertiary: '#ffffff'
  tertiary-container: '#7f244f'
  on-tertiary-container: '#ff95be'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#a7f698'
  primary-fixed-dim: '#8cd97e'
  on-primary-fixed: '#002201'
  on-primary-fixed-variant: '#005308'
  secondary-fixed: '#d7e3ff'
  secondary-fixed-dim: '#abc7ff'
  on-secondary-fixed: '#001b3f'
  on-secondary-fixed-variant: '#134687'
  tertiary-fixed: '#ffd9e4'
  tertiary-fixed-dim: '#ffb0cc'
  on-tertiary-fixed: '#3e0021'
  on-tertiary-fixed-variant: '#7e234e'
  background: '#f9f9f9'
  on-background: '#1a1c1c'
  surface-variant: '#e2e2e2'
  tertiary-amber: '#773400'
  error-red: '#b00000'
  terminal-bg: '#ffffff'
  terminal-text: '#111111'
typography:
  display-title:
    fontFamily: Work Sans
    fontSize: 20px
    fontWeight: '700'
    lineHeight: 28px
  modal-title:
    fontFamily: Work Sans
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-base:
    fontFamily: Work Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Work Sans
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-caps:
    fontFamily: Work Sans
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.05em
  status-badge:
    fontFamily: Work Sans
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
  code-log:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  micro-helper:
    fontFamily: Work Sans
    fontSize: 10px
    fontWeight: '400'
    lineHeight: 12px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  window-margin: 24px
  panel-gap: 16px
  row-height: 32px
---

## Brand & Style

The design system embodies **Windows 11 Utility Professionalism** fused with **Tactical Game Management**. It is designed for server administrators who require the precision and dependability of a system-level diagnostic tool, yet desire a visual connection to the vibrant, nature-integrated world of Palworld. The brand personality is technical, reliable, and vigilant.

The visual style is **Corporate / Modern** with a high-density, "Bento Box" layout. It leverages clean, structured cards and panels common in modern OS settings, but distinguishes itself with high-contrast tactical status indicators and a distinctive "Forest Green" primary palette. The UI prioritizes information scannability and operational safety, using explicit color weights to separate neutral monitoring from high-impact system actions.

**Design Principles:**
- **Reliable Precision:** Every pixel should feel intentional and aligned to a strict 4px grid, echoing the stability required for server management.
- **Systematic Scannability:** Use specialized typography and color-coding to make technical logs and network IPs readable at a glance.
- **Safety Boundaries:** Administrative actions (stops, updates, deletes) must have unique visual signatures to prevent accidental input.

## Colors

The palette is functionally driven, using chromaticity to communicate system health and operational readiness.

- **Primary (Forest Green):** Reserved for "Ready" states, successful diagnostics, and the primary "Start Server" action. It represents the healthy "Online" pulse of the environment.
- **Secondary (Admin Blue):** Used for informational system utilities, network navigation, and non-destructive management tools.
- **Tertiary (Amber):** Dedicated to warnings and conditions requiring attention, such as pending updates or missing admin privileges.
- **Error (Red):** Used exclusively for high-risk actions like "Stop Server" or critical failure states.
- **Neutral:** A clean, multi-tiered gray system that provides a professional backdrop, mimicking the Windows 11 surface logic.

**Implementation Note:** The `terminal-bg` and `terminal-text` tokens are strictly for code output and logs to ensure high contrast for monospaced data.

## Typography

This system uses a dual-type strategy. **Work Sans** provides a professional and approachable feel for all UI controls and standard labels. **JetBrains Mono** is reserved for technical data—such as IP addresses, timestamps, and terminal logs—where character distinctness (e.g., distinguishing `0` from `O`) is critical for administration.

- **Emphasis:** Use `label-caps` for section headers (e.g., "SYSTEM DIAGNOSTICS") to create a structured, utility-belt aesthetic.
- **Hierarchy:** `display-title` is used sparingly for main dashboard headings and hero status updates.
- **Precision:** `code-log` is applied to all scrolling terminal views and input fields containing network addresses.

## Layout & Spacing

The design system employs a **Fixed Grid** model optimized for high-density desktop utility windows. The layout is structured to prevent reflow, ensuring that critical status indicators remain in predictable positions during high-stress management tasks.

**Layout Philosophy:**
- **Base Unit:** A strict 4px rhythm.
- **The Bento Grid:** Information is chunked into logical panels. Panels are separated by a 16px (`lg`) gap.
- **Internal Rhythm:** 12px (`md`) padding is used within buttons and console views, while 8px (`sm`) is used for vertical list items in diagnostic rows.
- **Window Margins:** A consistent 24px (`xl`) margin surrounds the main application content to provide visual breathing room.

## Elevation & Depth

This system avoids expressive shadows in favor of **Tonal Layers** and **Subtle Outlines**, consistent with the Windows 11 "Mica" and "Acrylic" aesthetic.

- **Surface Layers:** The background sits at `surface-container-low` (#f3f3f3). Primary Bento cards sit at `surface-container-lowest` (#ffffff).
- **Outlines:** Cards and panels use a 1px border (`outline-variant`) at low opacity to define boundaries without adding visual weight.
- **Backdrop Blur:** Fixed headers and bottom navigation bars utilize `backdrop-blur-xl` to maintain context of the content scrolling beneath them while providing a clear interactive layer.
- **Tactile Feedback:** Buttons utilize a flat fill that darkens by 10% on hover and shifts 1px vertically on press to simulate physical engagement.

## Shapes

The design system uses a **Soft** shape language (4px base radius) to align with modern OS standards while maintaining a clean, technical edge.

- **Buttons & Inputs:** 4px (`rounded-lg`) corner radius.
- **Bento Cards:** 8px (`rounded-xl`) corner radius to clearly group large sections of information.
- **Status Badges:** Fully rounded ("Pill-shaped") to distinguish them as non-interactive status indicators.
- **Terminal View:** Sharp 0px corners are permitted for the log window to emphasize its raw, technical nature.

## Components

### Buttons
- **Primary (Start):** Solid `#005408` with white text. High prominence.
- **Secondary (Tools):** Solid `#335ea1` with white text. Used for diagnostics and backups.
- **Danger (Stop):** 2px Outlined `#b00000` with matching text. This "hollow" style requires more intentional focus than a solid fill, acting as a safety check.

### Diagnostic Panels
- Structured as "LabelFrames" with a subtle header label in `label-caps`.
- Rows consist of an icon, a label in `body-base`, and a status value (e.g., "READY") aligned to the right.

### Terminal / Live Console
- Background: `#ffffff`; Text: `#111111`.
- Uses `code-log` typography.
- New entries must use a subtle fade-in animation (`0.5s ease-out`).

### Input Fields
- White background with a 1px border. 
- Focused state uses a 2px `#335ea1` border.
- Monospaced font for all IP/Port inputs.

### Status Badges
- Small pill containers with a `●` leading icon.
- Green pulse animation for "LIVE" status to indicate active process monitoring.