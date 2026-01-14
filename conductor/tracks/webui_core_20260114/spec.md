# Spec: Web UI Core Infrastructure & Dual-Engine Routing

## Overview
This track focuses on building the foundational infrastructure for the new KaTrain Web UI. It includes a FastAPI-based backend, a React-based frontend, a user authentication system, and the core routing logic for the dual-engine setup (Local RK3588 vs. Cloud GPU).

## Functional Requirements

### 1. User Authentication
*   **Login Interface:** A dedicated login page in the Web UI.
*   **JWT-Based Security:** Use JSON Web Tokens for session management.
*   **User Persistence:** Simple user storage (SQLite/File-based) to manage access on local smart boards and web terminals.

### 2. Dual-Engine HTTP Routing
*   **Configuration:** Support for two distinct KataGo HTTP Analysis API endpoints:
    *   `LOCAL_KATAGO_URL`: For the RK3588 CPU-based engine.
    *   `CLOUD_KATAGO_URL`: For the remote GPU-based analysis server.
*   **Routing Logic:**
    *   **"Play" Requests:** Route to the `LOCAL_KATAGO_URL`.
    *   **"Analysis" Requests:** Route to the `CLOUD_KATAGO_URL`.
*   **API Client:** A robust HTTP client in Python to handle request forwarding, parsing, and error reporting.

### 3. Pure Client Architecture
*   The UI should not manage KataGo processes or models directly.
*   The UI communicates with the KaTrain Backend, which acts as a proxy/router to the KataGo engines.

## Technical Constraints
*   **Performance:** Backend routing must be asynchronous and low-latency.
*   **Compatibility:** Must run on RK3588 (Ubuntu Kiosk) and standard web browsers.
*   **Reliability:** Handle engine timeouts and unavailability gracefully.

## Success Criteria
*   Users can log in and see a persistent session.
*   "Play" requests are successfully fulfilled by a local engine endpoint.
*   "Analysis" requests are successfully fulfilled by a cloud engine endpoint.
*   The Web UI displays results from both engines correctly.
