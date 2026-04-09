---
name: ui-ux-pro-max
description: >
  UI/UX design intelligence. 50 styles, 21 palettes, 50 font pairings, 20 charts,
  9 stacks (React, Next.js, Vue, Svelte, SwiftUI, React Native, Flutter, Tailwind, shadcn/ui).
  Actions: plan, build, create, design, implement, review, fix, improve, optimize, enhance,
  refactor, check UI/UX code. Projects: website, landing page, dashboard, admin panel,
  e-commerce, SaaS, portfolio, blog, mobile app, .html, .tsx, .vue, .svelte.
  Elements: button, modal, navbar, sidebar, card, table, form, chart.
  Styles: glassmorphism, claymorphism, minimalism, brutalism, neumorphism, bento grid,
  dark mode, responsive, skeuomorphism, flat design.
  Topics: color palette, accessibility, animation, layout, typography, font pairing,
  spacing, hover, shadow, gradient.
  Integrations: shadcn/ui MCP for component search and examples.
---

# UI/UX Pro Max - Design Intelligence

Searchable database of UI styles, color palettes, font pairings, chart types, product recommendations, UX guidelines, and stack-specific best practices.

## How to Use This Skill

When you need to design or implement UI components, use the provided scripts to get professional recommendations.

### 1. Generate a Complete Design System

Use `design_system.py` to get a comprehensive recommendation including pattern, style, colors, and typography.

```bash
python3 .gemini/skills/ui-ux-pro-max/scripts/design_system.py "SaaS dashboard" --project-name "My Dashboard" --format markdown
```

### 2. Search Specific Domains

Use `search.py` to find specific UI/UX data.

```bash
python3 .gemini/skills/ui-ux-pro-max/scripts/search.py "<keyword>" --domain <domain> [-n <max_results>]
```

**Available Domains:**
- `product`: Product type recommendations (SaaS, e-commerce, portfolio, etc.)
- `style`: UI styles, colors, effects (glassmorphism, minimalism, etc.)
- `typography`: Font pairings, Google Fonts
- `color`: Color palettes by product type
- `landing`: Page structure, CTA strategies
- `chart`: Chart types, library recommendations
- `ux`: Best practices, anti-patterns
- `prompt`: AI prompts, CSS keywords

### 3. Get Stack-Specific Guidelines

```bash
python3 .gemini/skills/ui-ux-pro-max/scripts/search.py "<keyword>" --stack <stack_name>
```

**Available Stacks:**
- `html-tailwind` (Default)
- `react`
- `nextjs`
- `vue`
- `svelte`
- `swiftui`
- `react-native`
- `flutter`

## Professional UI Rules

- **No emoji icons**: Use SVG (Heroicons, Lucide).
- **Stable hover states**: Use transitions, avoid layout shifts.
- **Cursor pointer**: Always add to clickable elements.
- **Contrast**: Ensure 4.5:1 minimum for light mode text.
- **Responsive**: Design for 320px to 1440px.

## Pre-Delivery Checklist

- [ ] Icons are consistent and from a professional set.
- [ ] Transitions are smooth (150-300ms).
- [ ] Hover states provide clear feedback.
- [ ] Focus states are visible for keyboard navigation.
- [ ] Accessibility: Alt text for images, labels for form inputs.
- [ ] Tested in both light and dark modes (if applicable).
