---
name: Grifo Research Intelligence
colors:
  surface: "#f8f9ff"
  surface-dim: "#cbdbf5"
  surface-bright: "#f8f9ff"
  surface-container-lowest: "#ffffff"
  surface-container-low: "#eff4ff"
  surface-container: "#e5eeff"
  surface-container-high: "#dce9ff"
  surface-container-highest: "#d3e4fe"
  on-surface: "#0b1c30"
  on-surface-variant: "#424654"
  inverse-surface: "#213145"
  inverse-on-surface: "#eaf1ff"
  outline: "#737785"
  outline-variant: "#c2c6d6"
  surface-tint: "#0056cf"
  primary: "#0055cd"
  on-primary: "#ffffff"
  primary-container: "#2f6feb"
  on-primary-container: "#fffeff"
  inverse-primary: "#b1c5ff"
  secondary: "#5c5e66"
  on-secondary: "#ffffff"
  secondary-container: "#e1e2eb"
  on-secondary-container: "#62646c"
  tertiary: "#5b5d5f"
  on-tertiary: "#ffffff"
  tertiary-container: "#747678"
  on-tertiary-container: "#fffeff"
  error: "#ba1a1a"
  on-error: "#ffffff"
  error-container: "#ffdad6"
  on-error-container: "#93000a"
  primary-fixed: "#dae2ff"
  primary-fixed-dim: "#b1c5ff"
  on-primary-fixed: "#001947"
  on-primary-fixed-variant: "#00419f"
  secondary-fixed: "#e1e2eb"
  secondary-fixed-dim: "#c4c6cf"
  on-secondary-fixed: "#191c22"
  on-secondary-fixed-variant: "#44474e"
  tertiary-fixed: "#e1e2e4"
  tertiary-fixed-dim: "#c5c7c8"
  on-tertiary-fixed: "#191c1e"
  on-tertiary-fixed-variant: "#444749"
  background: "#f8f9ff"
  on-background: "#0b1c30"
  surface-variant: "#d3e4fe"
  highlight-keyword: "#ffe066"
  highlight-evidence: "#8ce99a"
  lacuna-accent: "#f03e3e"
  border-subtle: "#e2e8f0"
  surface-dark: "#12151b"
  surface-light: "#f6f7f9"
typography:
  display-lg:
    fontFamily: Hanken Grotesk
    fontSize: 48px
    fontWeight: "800"
    lineHeight: "1.1"
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: "600"
    lineHeight: "1.3"
  body-paper:
    fontFamily: Source Serif 4
    fontSize: 17px
    fontWeight: "400"
    lineHeight: "1.6"
  body-ui:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: "400"
    lineHeight: "1.5"
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: "700"
    lineHeight: "1"
    letterSpacing: 0.05em
  code-snippet:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: "400"
    lineHeight: "1.4"
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  sidebar-width: 300px
  max-content-width: 1180px
  gutter: 1.5rem
  stack-gap: 1rem
  section-padding: 2rem
---

## Brand & Style

The design system for this product is rooted in the "Modern Academic" aesthetic—a fusion of **Minimalism** and **Corporate/Technical** styles. It is designed to feel like a high-precision instrument for researchers, emphasizing density, clarity, and the promise of 100% local data privacy.

The UI avoids decorative flourishes in favor of purposeful whitespace and structural integrity. It draws inspiration from LaTeX-typeset papers and professional document editors, prioritizing information hierarchy and traceability. The emotional response should be one of "Reliable Authority" and "Focused Efficiency," reassuring the user that while the AI performs complex synthesis, the original source text is always one click away.

**Key Stylistic Pillars:**

- **Technical Density:** High information density without clutter, using subtle borders to compartmentalize data.
- **Academic Sobriety:** A serious tone that treats scientific PDFs with the respect of a professional workstation.
- **Traceability First:** Design patterns that always pair "AI Synthesis" with "Source Evidence."

## Colors

The palette is anchored by **Scholarly Blue**, a deep, professional primary color used for actions and brand identification. The background strategy utilizes a tiered system: **Neutral Light Gray** for general surfaces and **Deep Dark Slate** for high-contrast dark mode environments.

**Functional Highlights:**

- **Keyword Highlight (#ffe066):** Used exclusively for literal string matches (Scan results).
- **Evidence Highlight (#8ce99a):** Used for AI-extracted supporting passages.
- **Lacuna Accent:** A distinct red-tinted treatment is reserved for "Missing Research Gaps" to differentiate them from standard limitations.

**Usage Note:** Borders should remain low-contrast (#e2e8f0) to define sections without interrupting the reading flow. In dark mode, primary blue should be slightly desaturated to maintain accessibility against the deep slate background.

## Typography

This design system employs a dual-font strategy to separate the "Tool" from the "Content."

1.  **UI Interface:** Uses **Hanken Grotesk** for headlines to provide a modern, sharp edge, and **Inter** for all functional UI elements (menus, sidebars, buttons) due to its exceptional legibility at small sizes.
2.  **Document Content:** Uses **Source Serif 4** for all PDF-extracted text, summaries, and "Deep Reading" sections. This evokes the feel of a printed academic journal and reduces cognitive load during long-form reading.
3.  **Technical Metadata:** **JetBrains Mono** is used for DOIs, file paths, and terminal outputs to emphasize the "Local/Technical" nature of the processing.

**Responsive Scaling:** On mobile, `display-lg` scales down to 32px. UI body text remains fixed at 14px to maintain high density.

## Layout & Spacing

The layout uses a **Fixed Grid** model for the main workspace to ensure a consistent reading experience across large displays.

- **The Sidebar:** A 300px fixed column on the left houses the "Laboratory Controls" (Ollama connection, file queue, analysis parameters). It represents the "System" state.
- **The Main Stage:** Centered content area with a maximum width of 1180px.
- **The Triple-Tab System:** Results are organized by "Intent" (Skim, Scan, Deep Reading). This reduces navigation depth while maintaining high density.
- **Responsive Behavior:** Below 900px, the layout collapses into a single-column vertical flow where the sidebar becomes a collapsible top drawer.

**Rhythm:** Use an 8px base grid. Section headers should have 32px of top margin, while items within a list use 12px of spacing to maintain a "tight" professional feel.

## Elevation & Depth

To maintain the "Technical instrument" aesthetic, this design system avoids heavy shadows in favor of **Tonal Layers** and **Subtle Outlines**.

- **Surface Levels:** The background uses the neutral tertiary color. Active cards or focused sections use a pure white (or pure slate in dark mode) background with a 1px border.
- **Interactive Depth:** Buttons use a subtle 2px solid offset or a very tight, low-opacity shadow (4px blur, 10% opacity) to signify clickability without appearing "floaty."
- **Focus States:** High-contrast 2px blue borders are used to indicate the currently selected article or active input field.
- **Sidebar Separation:** A vertical 1px border clearly separates the control zone from the viewing zone, mimicking the interface of professional IDEs or engineering tools.

## Shapes

The shape language is **Soft (0.25rem)**. This provides a subtle modern touch that softens the "Technical" edge of the product without making it feel casual or playful.

- **Primary Components:** Buttons, input fields, and small chips use 0.25rem (4px) corner radii.
- **Container Elements:** Cards and major sections use `rounded-lg` (8px) for a slightly more defined container feel.
- **Status Indicators:** Small status dots (Online/Offline) are kept as perfect circles.
- **Selection Markers:** Vertical pills in the sidebar use a full round (pill-shape) on one side to indicate the active state.

## Components

### Buttons & Inputs

- **Primary Action:** Solid Blue (#2f6feb) with white text.
- **Technical Inputs:** Monospaced text inside inputs for model parameters.
- **Keywords Input:** Multiline text area that transforms strings into distinct, closable chips upon entry.

### The "Evidence Card"

A specific component used in "Deep Reading." It features the AI-generated synthesis in **Source Serif 4**, paired with a footer containing a "Source Citation" (e.g., _p. 4_). Clicking the citation highlights the corresponding text in the "Extraído" view.

### Progress Blocks

During analysis, articles should appear as stacked cards. The active article expands to show a "Step-by-Step" technical log (e.g., "Reading Block 4/12") using `code-snippet` typography.

### Lacuna Treatment

Sections identified as "Lacunas" (Research Gaps) should be styled with a subtle red-tinted background and a specific "Missing" icon to alert the researcher to unexplored territory.

### Data Tables

High-density tables for "Scan" and "Comparison" should use zebra-striping with the neutral tertiary color and 1px borders. Header rows use `label-caps` for a professional, institutional look.

### PDF Sidebar List

Items in the batch queue use leading icons (Checkmark, Hourglass, or Warning) with a progress ring for the currently processing file.
