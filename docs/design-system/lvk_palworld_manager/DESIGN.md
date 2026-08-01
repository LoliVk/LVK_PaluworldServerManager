---
name: LVK Palworld Manager
colors:
  surface: '#f9f9f9'
  surface-dim: '#dadad9'
  surface-bright: '#f9f9f9'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f4f3f3'
  surface-container: '#EEEEEE'
  surface-container-high: '#e8e8e8'
  surface-container-highest: '#e2e2e2'
  on-surface: '#1a1c1c'
  on-surface-variant: '#40493D'
  inverse-surface: '#2f3131'
  inverse-on-surface: '#f1f1f0'
  outline: '#707A6C'
  outline-variant: '#C0C9B9'
  surface-tint: '#236c20'
  primary: '#003a04'
  on-primary: '#ffffff'
  primary-container: '#1A6E1A'
  on-primary-container: '#7cc870'
  inverse-primary: '#8cd97e'
  secondary: '#335ea1'
  on-secondary: '#ffffff'
  secondary-container: '#8fb6ff'
  on-secondary-container: '#144688'
  tertiary: '#620938'
  on-tertiary: '#ffffff'
  tertiary-container: '#7f244f'
  on-tertiary-container: '#ff96be'
  error: '#BA1A1A'
  on-error: '#ffffff'
  error-container: '#FFDAD6'
  on-error-container: '#93000A'
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
  on-tertiary-fixed: '#3e0020'
  on-tertiary-fixed-variant: '#7e234e'
  background: '#F9F9F9'
  on-background: '#1a1c1c'
  surface-variant: '#e2e2e2'
  surface-lowest: '#FFFFFF'
  surface-low: '#F3F3F3'
  surface-high: '#E8E8E8'
  surface-highest: '#E2E2E2'
typography:
  display-title:
    fontFamily: Work Sans
    fontSize: 20px
    fontWeight: '700'
    lineHeight: 28px
  headline-lg:
    fontFamily: Work Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
  headline-lg-mobile:
    fontFamily: Work Sans
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  modal-title:
    fontFamily: Work Sans
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body:
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
  micro:
    fontFamily: Work Sans
    fontSize: 10px
    fontWeight: '400'
    lineHeight: 12px
  code-log:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
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
  sidebar-width: 288px
  header-height: 64px
  row-height: 32px
  max-width: 1440px
---

# LVK Palworld Server Manager Design System

## 1. Purpose

This document defines the visual and interaction standards for LVK Palworld Server Manager. It is derived from the reference screens in [`docs/design-system/`](docs/design-system/): Dashboard, Backup, World, and Stats.

Use these rules for new UI work so the application remains a calm, operational control panel: light surfaces, restrained green status emphasis, compact information density, and clear handling of destructive operations.

## 2. Design principles

- **Operational clarity first** — server state, warnings, and primary actions must be immediately scannable.
- **Semantic colour usage** — reserve green for positive/active states, blue for routine actions, and red for errors or destructive actions.
- **Dense but breathable** — preserve the established 4 / 8 / 12 / 16 / 24 px spacing rhythm.
- **Plain, trustworthy controls** — favour subtle borders, small corner radii, and low-elevation panels over decorative effects.
- **Safe by default** — write-locked, restore, delete, and other consequential actions require clear status, warning copy, and confirmation where appropriate.

## 3. Foundations

### 3.1 Colour tokens

| Token | Value | Intended use |
| --- | --- | --- |
| `background`, `surface` | `#F9F9F9` | Application canvas and standard surface |
| `surface-container-lowest` | `#FFFFFF` | Primary cards and navigation surfaces |
| `surface-container-low` | `#F3F3F3` | Quiet grouped regions |
| `surface-container` | `#EEEEEE` | Inputs, secondary fills |
| `surface-container-high` | `#E8E8E8` | Hoverable control fill |
| `surface-container-highest` | `#E2E2E2` | Stronger neutral emphasis |
| `on-surface` | `#1A1C1C` | Primary text and icons |
| `on-surface-variant` | `#40493D` | Secondary text and icons |
| `outline` | `#707A6C` | Strong borders and inactive outlines |
| `outline-variant` | `#C0C9B9` | Dividers and low-emphasis borders |
| `primary` | `#005408` | Primary state, headings, status indicators |
| `primary-container` | `#005408` / `#1A6E1A` | Selected navigation and positive emphasis |
| `on-primary` | `#FFFFFF` | Text or icons on primary backgrounds |
| `secondary` | `#335EA1` | Routine primary actions such as Save and Restore |
| `error` | `#BA1A1A` | Error status and destructive emphasis |
| `error-container` | `#FFDAD6` | Error banners and destructive confirmation context |
| `on-error-container` | `#93000A` | Error banner content |
| `tertiary` | `#620938` | Limited tertiary categorisation only |

### 3.2 Typography

| Role | Font | Size / line height | Weight | Usage |
| --- | --- | --- | --- |
| Display title | Work Sans | 20 / 28 px | 700 | Page titles, major status headings |
| Large page title | Work Sans | 32 px | 700 | Prominent screen title or server state |
| Modal title | Work Sans | 16 / 24 px | 600 | Dialog headings, section headings |
| Body | Work Sans | 14 / 20 px | 400 | Default UI copy |
| Small body | Work Sans | 12 / 16 px | 400 | Supporting information |
| Label | Work Sans | 11 / 14 px | 700 | Uppercase labels, table headings, navigation |
| Status badge | Work Sans | 11 / 14 px | 600 | Compact status text |
| Micro helper | Work Sans | 10 / 12 px | 400 | Versions and low-priority hints |
| Code/log | JetBrains Mono | 12 / 18 px | 400 | Paths, timestamps, metrics, terminal output |

### 3.3 Spacing, shape, and elevation

| Token | Value | Usage |
| --- | --- | --- |
| `xs` | 4 px | Icon-to-label and micro gaps |
| `sm` | 8 px | Compact control and item gaps |
| `md` | 12 px | Standard inner padding / control gaps |
| `lg`, `panel-gap` | 16 px | Section gaps and card-internal spacing |
| `xl` | 24 px | Page and major-card padding |
| `window-margin` | 24 px | Desktop outer page margin |
| `row-height` | 32 px | Compact rows and controls |

- Default radius: 2 px; compact corners: 4 px; cards and controls: 8 px; pills: 12 px or full.
- Cards use white or near-white surfaces, optional `outline-variant` border at low opacity, and a subtle shadow only when separation is needed.

## 4. Layout

- Desktop navigation uses a 288 px left sidebar and a fixed 64 px top header.
- Content starts below the header and keeps a 24 px outer margin on desktop.
- Maximum wide-content width is 1440 px.

## 5. Components and states

### Navigation

- Group routes under concise uppercase labels such as `OPERATIONS` and `SYSTEM`.
- Default items use `on-surface-variant`; selected items use a `primary-container` fill with high-contrast primary text.
- Use Material Symbols Outlined icons at about 20 px, placed before labels.

### Buttons

- **Primary action:** `secondary` background with white text. Use for Save, Restore, and other routine committed actions.
- **Secondary action:** neutral or subtle primary treatment, with a visible label.
- **Icon action:** padded square icon control.
- **Destructive action:** use error styling only for actions that can remove or overwrite data.

### Cards, tables, and data

- Use `surface-container-lowest` for primary cards.
- Divide sections and table rows with low-opacity `outline-variant` lines.
- Table headers are uppercase labels; values such as timestamps, paths, sizes, and telemetry use `code-log` typography.

### Forms

- Inputs use a `surface-container` fill, compact radius, and clear focus border in `secondary`.

### Status, alerts, and dialogs

- Positive/online: green indicator.
- Informational/action: blue (`secondary`).
- Error/locked: `error-container` with `on-error-container` content and an error accent border.
