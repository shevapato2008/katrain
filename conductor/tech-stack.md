# Tech Stack - KaTrain Web UI & Smart Board

## Frontend
*   **Framework:** React (with TypeScript)
*   **Styling:** CSS/SCSS (Optimized for performance on RK3588)
*   **State Management:** React Hooks / Context API
*   **Build Tool:** Vite (or similar modern tool for fast builds and HMR)

## Backend (API & Proxy)
*   **Language:** Python 3.9+
*   **Framework:** FastAPI
*   **Server:** Uvicorn
*   **Bulk Sync API:** Implementation of `/api/config/bulk` for efficient, atomic synchronization of complex settings objects.
*   **Request Handling:** `httpx` (for asynchronous communication with KataGo engines)

## AI Engine Integration
*   **Protocol:** KataGo HTTP Analysis API
*   **Dual Engine Routing:**
    *   **Local Engine:** CPU-based KataGo (Eigen mode) on RK3588.
    *   **Cloud Engine:** GPU-based KataGo on remote servers.

## Deployment & Security
*   **Infrastructure:** Ubuntu Kiosk mode (RK3588 Hardware)
*   **Containerization:** Docker
*   **Authentication:** JWT (JSON Web Tokens) using `python-jose[cryptography]` and `passlib[bcrypt]` for password hashing.
*   **Reverse Proxy:** Nginx (Recommended for production/public access)
