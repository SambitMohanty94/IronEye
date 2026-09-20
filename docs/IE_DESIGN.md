# DESIGN.md — IronEye Design System & UI/UX Specification

## 1. Executive Summary & Aesthetic Direction
IronEye uses an Industrial Security Operations Center (SOC) visual system optimized for dark control rooms, reduced glare, visual hierarchy, and instant comprehension during critical hazard events.

The layout adapts seamlessly across Desktop Video Walls, Laptops, iPadOS/Android Tablets, and iOS/Android Handhelds.

## 2. Color System & Primitive Tokens

The color palette is calibrated on a 6-step cool slate scale:
- `primitive-slate-900` (#191D23): Deep dark canvas base[cite: 1, 2]
- `primitive-slate-700` (#57707A): Deep slate cyan surface container base[cite: 1, 2]
- `primitive-slate-500` (#7E919F): Cool mid-slate structural borders and dividers[cite: 1, 2]
- `primitive-slate-300` (#979DAB): Soft muted slate secondary typography[cite: 1, 2]
- `primitive-mauve-200` (#C5BAC4): Muted mauve-tint neutral for highlights and hover rings[cite: 1, 2]
- `primitive-slate-50`  (#DEDCDC): Off-white canvas text and light surface[cite: 1, 2]

### Hazard Severity Indicators
- **CRITICAL:** `#FF1744` (Crimson Red — Fire, Smoke, Fall, Breach)
- **WARNING:**  `#FFD600` (Amber Yellow — Transient PPE violation)
- **SAFE:**     `#00E676` (Mint Green — Compliant, Normal Zone)
- **TELEMETRY:**`#00E5FF` (Cyan — Connected Stream, System OK)

## 3. Semantic CSS Variables

```css
:root {
  --color-slate-900: #191D23; /*[cite: 1, 2] */
  --color-slate-700: #57707A; /*[cite: 1, 2] */
  --color-slate-500: #7E919F; /*[cite: 1, 2] */
  --color-slate-300: #979DAB; /*[cite: 1, 2] */
  --color-mauve-200: #C5BAC4; /*[cite: 1, 2] */
  --color-slate-50:  #DEDCDC; /*[cite: 1, 2] */

  --hazard-critical: #FF1744;
  --hazard-warning:  #FFD600;
  --hazard-safe:     #00E676;
  --hazard-info:     #00E5FF;

  --bg-canvas: var(--color-slate-900); /*[cite: 1, 2] */
  --bg-surface: #1F242C;
  --bg-surface-elevated: rgba(87, 112, 122, 0.22); /*[cite: 1, 2] */
  --border-subtle: rgba(87, 112, 122, 0.35); /*[cite: 1, 2] */
  --border-strong: var(--color-slate-500); /*[cite: 1, 2] */
  --text-primary: var(--color-slate-50); /*[cite: 1, 2] */
  --text-secondary: var(--color-slate-300); /*[cite: 1, 2] */
  --text-tertiary: var(--color-slate-500); /*[cite: 1, 2] */
  --accent-action: var(--color-slate-700); /*[cite: 1, 2] */
}