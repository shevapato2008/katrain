# Product Guidelines - KaTrain Web UI

## Visual Design Philosophy
*   **Responsive & Adaptive Core:** The UI must maintain high usability across desktop browsers, mobile devices, and the RK3588 kiosk mode. Layouts should fluidly adapt to screen aspect ratios.
*   **Touch-First Interaction:** Prioritize large hit targets (buttons, menu items) and gesture support (swiping to navigate game history). This is critical for the Smart Board hardware and mobile users.
*   **Smart Information Density:** Implement a hierarchical information display. High-density analysis data (win rates, score leads) should be readily available on desktop, while being collapsible or simplified on mobile and smart board views to maintain clarity.
*   **Minimalist & Focused Aesthetic:** Reduce visual noise. The Go board should remain the primary focus, with UI elements utilizing transparency or contextual appearing/disappearing to avoid cluttering the board space.

## User Interaction & Experience
*   **Consistent Login Experience:** A unified login flow across all platforms to access personalized settings and remote analysis.
*   **Seamless Engine Transitions:** The UI should clearly but subtly indicate whether the current analysis is being handled by the "Local Play" engine or the "Cloud Analysis" engine.
*   **Kiosk-Optimized Navigation:** For smart boards, navigation should be simple and fail-safe, preventing users from accidentally exiting the application or accessing OS-level settings.

## Technical Standards
*   **Performance on Low-Power Hardware:** Web components and animations must be optimized for the RK3588's embedded browser to ensure a smooth 60fps experience.
*   **Pure Client Architecture:** The frontend must remain decoupled from engine configuration, relying entirely on standardized API responses for game state and analysis.
