# KaTrain WebUI Redesign - Implementation Plan

## Design Concept: "Zen Precision"

A professional Go analysis interface that blends Japanese aesthetic sensibility with modern precision instrumentation. The design emphasizes clarity, focus, and refined details.

---

## Design System

### Visual Identity

**Aesthetic Direction:** "Zen Precision"
- Precision instrument meets traditional Japanese aesthetics
- Clean, professional, focused on analysis experience
- Subtle luxury through refined details and micro-interactions

### Typography

**Primary Fonts:**
- **IBM Plex Mono** - Technical data, numbers, coordinates, analysis values
  - Weight: 400 (Regular), 500 (Medium), 600 (SemiBold)
  - Usage: Move numbers, scores, percentages, technical readouts

- **Manrope** - UI labels, buttons, headers, body text
  - Weight: 400 (Regular), 600 (SemiBold), 700 (Bold)
  - Usage: Navigation, labels, descriptions, player names

**Type Scale:**
```
--font-xs: 0.75rem (12px)     // Small labels, metadata
--font-sm: 0.875rem (14px)    // Body text, secondary info
--font-base: 1rem (16px)      // Primary body text
--font-lg: 1.125rem (18px)    // Section headers
--font-xl: 1.25rem (20px)     // Panel titles
--font-2xl: 1.5rem (24px)     // Major headings
```

### Color Palette

**Base Colors:**
```css
/* Neutrals - Warm, refined grays */
--color-bg-primary: #0f0f0f      /* Deep charcoal background */
--color-bg-secondary: #1a1a1a    /* Elevated surfaces */
--color-bg-tertiary: #252525     /* Panels, cards */
--color-surface: #2a2a2a         /* Interactive surfaces */

--color-fg-primary: #f5f3f0      /* Primary text */
--color-fg-secondary: #b8b5b0    /* Secondary text */
--color-fg-tertiary: #7a7772     /* Subtle text */

/* Brand & Accent */
--color-accent: #4a6b5c          /* Muted jade - primary actions */
--color-accent-hover: #5d8270    /* Accent hover state */
--color-accent-light: #3f5d4f    /* Accent background */

/* Board & Game */
--color-board-bg: #d4a574        /* Warm wood tone */
--color-board-line: #8b6f47      /* Grid lines */
--color-stone-black: #0a0a0a     /* Black stones */
--color-stone-white: #f8f6f3     /* White stones */

/* Analysis Colors - Refined evaluation spectrum */
--color-eval-excellent: #30a06e  /* Green - excellent move */
--color-eval-good: #6fb359       /* Light green - good move */
--color-eval-ok: #c7b946         /* Yellow - okay move */
--color-eval-inaccuracy: #e89639 /* Orange - inaccuracy */
--color-eval-mistake: #e16b5c    /* Red - mistake */
--color-eval-blunder: #c73e64    /* Dark red - blunder */

/* Semantic Colors */
--color-success: #30a06e
--color-warning: #e89639
--color-error: #e16b5c
--color-info: #5b9bd5
```

### Spacing System

**Spatial Scale:**
```css
--space-xs: 0.25rem (4px)
--space-sm: 0.5rem (8px)
--space-md: 1rem (16px)
--space-lg: 1.5rem (24px)
--space-xl: 2rem (32px)
--space-2xl: 3rem (48px)
--space-3xl: 4rem (64px)
```

### Shadow System

**Depth Layers:**
```css
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3),
             0 1px 3px rgba(0, 0, 0, 0.15);

--shadow-md: 0 4px 6px rgba(0, 0, 0, 0.3),
             0 2px 4px rgba(0, 0, 0, 0.2);

--shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.3),
             0 4px 6px rgba(0, 0, 0, 0.2);

--shadow-xl: 0 20px 25px rgba(0, 0, 0, 0.35),
             0 10px 10px rgba(0, 0, 0, 0.25);

--shadow-board: 0 8px 32px rgba(0, 0, 0, 0.4),
                0 0 80px rgba(212, 165, 116, 0.05),
                inset 0 0 1px rgba(255, 255, 255, 0.1);
```

### Border Radius

```css
--radius-sm: 4px
--radius-md: 8px
--radius-lg: 12px
--radius-xl: 16px
--radius-full: 9999px
```

### Transitions

```css
--transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1)
--transition-base: 250ms cubic-bezier(0.4, 0, 0.2, 1)
--transition-slow: 350ms cubic-bezier(0.4, 0, 0.2, 1)
```

---

## Layout Architecture

### Overall Structure

```
┌─────────────────────────────────────────────────────────────┐
│ TopBar - Minimal, floating controls & analysis toggles      │
├─────────────────────────────────────────────────────────────┤
│ ┌──────────────────────┐  ┌──────────────────────────────┐ │
│ │                      │  │  Analysis Panel (Floating)   │ │
│ │                      │  │  ┌────────────────────────┐  │ │
│ │                      │  │  │ Player Cards           │  │ │
│ │                      │  │  └────────────────────────┘  │ │
│ │   Go Board           │  │  ┌────────────────────────┐  │ │
│ │   (Central Focus)    │  │  │ Top Moves List         │  │ │
│ │                      │  │  │ • Move 1: K4           │  │ │
│ │   Canvas with        │  │  │ • Move 2: D4           │  │ │
│ │   overlays           │  │  │ • Move 3: Q16          │  │ │
│ │                      │  │  └────────────────────────┘  │ │
│ │                      │  │  ┌────────────────────────┐  │ │
│ │                      │  │  │ Score Graph            │  │ │
│ └──────────────────────┘  │  └────────────────────────┘  │ │
│                           └──────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ Control Bar - Navigation buttons (floating, centered)      │
└─────────────────────────────────────────────────────────────┘
```

### Responsive Breakpoints

```css
--breakpoint-mobile: 640px
--breakpoint-tablet: 768px
--breakpoint-desktop: 1024px
--breakpoint-wide: 1280px
```

**Mobile (< 768px):**
- Stack vertically: Board → Controls → Analysis Panel
- Collapsible analysis panel
- Simplified graph

**Desktop (≥ 768px):**
- Side-by-side layout
- Board on left (flexible, maintains aspect ratio)
- Analysis panel on right (fixed width: 360px)

---

## Component Specifications

### 1. TopBar Component

**Purpose:** Minimal header with analysis toggles and menu access

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│ [☰]  KaTrain          [👁] [•] [🎯] [📊] [🗺]    Status │
└─────────────────────────────────────────────────────────┘
```

**Features:**
- Hamburger menu (left)
- Logo/wordmark
- Analysis toggle buttons (children, dots, hints, policy, ownership)
- Status indicator (right)
- Semi-transparent background with backdrop blur
- Floating appearance with subtle shadow

**Styling:**
- Height: 56px
- Background: `rgba(26, 26, 26, 0.9)` + `backdrop-filter: blur(10px)`
- Border-bottom: 1px solid `rgba(255, 255, 255, 0.05)`
- Fixed positioning with z-index layering

### 2. Board Component

**Purpose:** Central Go board with canvas rendering and overlays

**Visual Treatment:**
- Subtle glow effect around board
- Layered shadow for depth
- Smooth stone rendering with gradients
- Clean grid lines with proper anti-aliasing

**Canvas Layers:**
1. **Background Layer** - Board texture, wood grain
2. **Grid Layer** - Lines, star points, coordinates
3. **Stones Layer** - Black/white stones with shadows
4. **Overlay Layer** - Move hints, policy heatmap, ownership colors
5. **Interaction Layer** - Last move marker, hover ghost stone

**Styling Enhancements:**
- Board shadow: `var(--shadow-board)`
- Border-radius: `var(--radius-md)`
- Smooth scaling based on viewport
- Ghost stone on hover with 40% opacity

### 3. Analysis Panel (Sidebar)

**Purpose:** Floating panel showing analysis data, player info, and graph

**Structure:**
```
┌──────────────────────────┐
│  Player Cards            │
│  ┌────┐ vs ┌────┐       │
│  │ B  │    │ W  │       │
│  └────┘    └────┘       │
├──────────────────────────┤
│  Top Moves               │
│  1. K4    +2.3  42%     │
│  2. D4    +1.8  28%     │
│  3. Q16   +1.2  18%     │
├──────────────────────────┤
│  Score Graph             │
│  [Graph visualization]   │
└──────────────────────────┘
```

**Features:**
- Compact player cards with captures, rank, type
- Scrollable top moves list with evaluation colors
- Integrated score/winrate graph
- Move tree visualization (collapsible)

**Styling:**
- Width: 360px (desktop)
- Background: `var(--color-bg-tertiary)`
- Border-left: 1px solid `rgba(255, 255, 255, 0.05)`
- Smooth sections with dividers

### 4. Control Bar Component

**Purpose:** Navigation and game control buttons

**Layout:**
```
┌──────────────────────────────────────────────────────┐
│  [⏮] [◄◄] [◄] [●] [►] [►►] [⏭]  [Pass] [Resign] │
└──────────────────────────────────────────────────────┘
```

**Features:**
- Move navigation: Start, -10, -1, +1, +10, End
- Mistake navigation: Previous/Next mistake
- Action buttons: Pass, Resign, AI Move
- Rotate board button

**Styling:**
- Floating bar, centered below board
- Button groups with visual separation
- Icon buttons with labels on hover
- Background: `var(--color-bg-secondary)`
- Rounded corners: `var(--radius-lg)`
- Shadow: `var(--shadow-md)`

### 5. Player Card Component

**Purpose:** Compact display of player information

**Layout:**
```
┌────────────────┐
│ ⚫ Black        │
│ Human          │
│ Captures: 3    │
└────────────────┘
```

**Features:**
- Player color indicator
- Player type (Human/AI strategy)
- Capture count
- Active player highlight

**Styling:**
- Compact card design
- Accent border for active player
- Stone color visualization

### 6. Score Graph Component

**Purpose:** Visual history of game progression

**Features:**
- Win rate line graph
- Score estimate overlay (toggleable)
- Current move indicator
- Click to navigate to move
- Mistake markers (colored dots)

**Styling:**
- Height: 120px
- Dark background with grid lines
- Green (Black) vs White line colors
- Smooth SVG rendering
- Hover tooltips for move details

### 7. Hamburger Menu (Sidebar)

**Purpose:** Access to all settings and game management

**Structure:**
- New Game
- Load/Save SGF
- Player Setup (with swap)
- Settings sections (AI, Timer, Teacher, Engine, General)
- Language selector with flags
- Analyze game, Report

**Styling:**
- Drawer animation from left
- Semi-transparent backdrop
- Organized sections with icons
- Visual hierarchy with typography scale

---

## Interaction Patterns

### Hover States

**Buttons:**
- Background color shift
- Subtle scale (1.02x)
- Transition: `var(--transition-fast)`

**Board Intersections:**
- Ghost stone preview (40% opacity)
- Coordinate highlight

**Graph:**
- Vertical line indicator
- Tooltip with move info

### Active States

**Current Move:**
- Marker on board (inner circle)
- Highlighted in move list
- Graph indicator position

**Analysis Toggle:**
- Filled icon state
- Accent color border

### Loading States

**Analysis Updates:**
- Subtle pulse on analysis panel
- Shimmer on updating values
- Smooth fade-in for new data

### Animations

**Page Load:**
- Staggered fade-in of panels (50ms delay between)
- Board scales from 0.95x to 1x (300ms)

**Move Played:**
- Stone placement: Scale from 0.8x to 1x (200ms)
- Analysis update: Fade out old, fade in new (300ms)

**Panel Transitions:**
- Slide and fade for sidebar (250ms)
- Smooth height transitions for collapsible sections (200ms)

---

## Technical Implementation

### File Structure

```
katrain/web/ui/src/
├── styles/
│   ├── theme.css              # CSS variables, design tokens
│   ├── global.css             # Global styles, resets
│   └── animations.css         # Keyframes, transitions
├── components/
│   ├── Board.tsx              # Enhanced board component
│   ├── TopBar.tsx             # Redesigned top bar
│   ├── ControlBar.tsx         # Refined control bar
│   ├── AnalysisPanel.tsx      # Floating analysis panel
│   ├── PlayerCard.tsx         # Compact player cards
│   ├── ScoreGraph.tsx         # Enhanced graph
│   ├── Sidebar.tsx            # Hamburger menu
│   ├── NewGameDialog.tsx      # Game setup modal
│   └── AISettingsDialog.tsx   # AI configuration modal
└── App.tsx                    # Main app with new layout
```

### Key Libraries

- **React 18** - Component framework
- **TypeScript** - Type safety
- **Framer Motion** - Advanced animations (optional, use CSS primarily)
- **Recharts** or **D3** - Graph rendering (or custom SVG)

### Performance Considerations

1. **Canvas Optimization:**
   - Debounce board redraws (16ms / 60fps)
   - Layer-based rendering (only redraw changed layers)
   - OffscreenCanvas for stone pre-rendering

2. **Component Optimization:**
   - React.memo for expensive components
   - useMemo for analysis calculations
   - Virtual scrolling for long move lists

3. **Animation Performance:**
   - CSS transforms (GPU accelerated)
   - will-change property for animated elements
   - RequestAnimationFrame for canvas updates

---

## Implementation Phases

### Phase 1: Design System Setup (2-3 hours)
- [ ] Create theme.css with all design tokens
- [ ] Set up global.css with base styles
- [ ] Configure typography (font imports, fallbacks)
- [ ] Test design system in Storybook or isolated components

### Phase 2: Core Components (6-8 hours)
- [ ] Redesign Board.tsx with enhanced styling
- [ ] Rebuild TopBar.tsx with new layout
- [ ] Update ControlBar.tsx with refined buttons
- [ ] Redesign AnalysisPanel.tsx with floating card design
- [ ] Create new PlayerCard.tsx component
- [ ] Enhance ScoreGraph.tsx with better visuals

### Phase 3: Layout & Integration (4-6 hours)
- [ ] Update App.tsx with new layout structure
- [ ] Implement responsive behavior
- [ ] Test all component interactions
- [ ] Ensure feature parity with existing implementation

### Phase 4: Polish & Refinement (4-6 hours)
- [ ] Add micro-interactions and hover states
- [ ] Implement smooth transitions
- [ ] Refine spacing and alignment
- [ ] Test across browsers
- [ ] Accessibility audit (keyboard nav, ARIA labels)

### Phase 5: Advanced Features (Optional, 4-6 hours)
- [ ] Advanced animations (move playback, analysis reveal)
- [ ] Customizable themes (light mode option)
- [ ] Keyboard shortcuts overlay
- [ ] Performance optimization pass

---

## Accessibility Considerations

### Keyboard Navigation
- Tab order follows visual hierarchy
- All interactive elements focusable
- Visible focus indicators with accent color
- Escape key closes modals/drawers

### Screen Readers
- Semantic HTML structure
- ARIA labels for icon buttons
- Live regions for analysis updates
- Descriptive alt text for visual elements

### Color Contrast
- All text meets WCAG AA standards (4.5:1 minimum)
- Analysis colors distinguishable for colorblind users
- Option to increase contrast in settings

### Reduced Motion
- Respect `prefers-reduced-motion` media query
- Disable animations for users who prefer reduced motion
- Maintain functionality without animations

---

## Design Rationale

### Why "Zen Precision"?

1. **Honors Go's Heritage:** The aesthetic nods to Japanese design principles - simplicity, attention to detail, negative space (ma)

2. **Modern Professionalism:** Monospace typography and clean data presentation create a "precision instrument" feel appropriate for serious analysis

3. **Focus on Content:** The board remains central; UI elements support rather than compete with the game

4. **Refined Details:** Subtle shadows, textures, and transitions create a premium feel without distraction

5. **Scalable System:** Design tokens allow for future themes while maintaining consistency

### Differentiators from Generic Designs

✅ **Custom Typography Pairing** - IBM Plex Mono + Manrope (not overused combos)
✅ **Refined Color Palette** - Warm neutrals + muted jade (not purple gradients)
✅ **Asymmetric Layout** - Board emphasized, floating panels (not centered grids)
✅ **Contextual Aesthetic** - Design reflects Go culture and analysis needs
✅ **Attention to Detail** - Layered shadows, subtle textures, refined micro-interactions

---

## Next Steps

1. **Review & Approval:** Confirm design direction with team/stakeholders
2. **Asset Preparation:** Gather fonts, ensure licensing for IBM Plex Mono and Manrope
3. **Development Environment:** Set up with design tokens
4. **Iterative Implementation:** Build phase by phase, test frequently
5. **User Testing:** Gather feedback from Go players using the tool
6. **Refinement:** Polish based on real-world usage

---

## Resources

### Fonts
- **IBM Plex Mono:** https://fonts.google.com/specimen/IBM+Plex+Mono
- **Manrope:** https://fonts.google.com/specimen/Manrope

### Inspiration
- Traditional Go board aesthetics
- Braun design principles (Dieter Rams)
- Japanese minimalism (ma, wabi-sabi)
- Professional analysis tools (chess.com, lichess analysis board)
- Data visualization best practices

### Color Accessibility
- Use WebAIM Contrast Checker to verify all text meets WCAG standards
- Test evaluation colors with colorblind simulators

---

**Design Philosophy:** Every pixel serves the player's understanding of the game. Clarity through refinement.
