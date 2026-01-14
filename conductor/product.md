# Product Guide - KaTrain Web UI & Smart Board Integration

## Initial Concept
The primary goal is to achieve and exceed feature parity between the new Web GUI and the existing Kivy-based Desktop GUI. A key driver for this development is the integration with a custom Smart Go Board (RK3588-based), requiring a split-engine architecture to balance local play with remote high-performance analysis.

## Target Users
*   **Existing KaTrain Desktop Users:** Transitioning to a modern, browser-based experience.
*   **Mobile Users:** Requiring a fully responsive and touch-optimized interface.
*   **Smart Board Users:** Owners of the RK3588-based device running a Ubuntu Kiosk environment. These users interact via a dedicated touch interface and require seamless transitions between local and cloud-based AI.

## Core Goals
*   **Surpass Desktop Functionality:** Deliver a superior feature set in the Web UI compared to the legacy Kivy implementation.
*   **Simplified Configuration:** Abstract engine and model settings (formerly "General & Engine Settings F8") away from the UI. The Web UI now acts as a pure client, delegating optimal model selection and management to the KataGo Engine.
*   **Intelligent Request Routing (Dual-Engine):** Implement logic to route lightweight "playing" requests to the local RK3588 CPU-based engine (Eigen mode) and heavy-duty "analysis" requests to high-performance remote GPU servers.

## Key Features & Requirements
*   **Dual-Engine Support:** Configurable support for two separate KataGo HTTP endpoints (Local and Cloud).
*   **Smart Board Optimization:** A high-performance, touch-friendly UI optimized for the RK3588's embedded browser environment.
*   **API-First Analysis:** Full integration with the KataGo Engine's API for result parsing and visualization, removing the need for local model management in the frontend.
*   **User Authentication & Security:** Implement a user login interface for all terminals. This ensures authorized access to the Web UI and manages secure connectivity (API keys/tokens) to the remote KataGo analysis services.
