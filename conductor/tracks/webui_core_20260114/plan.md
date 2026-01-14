# Plan: Web UI Core Infrastructure & Dual-Engine Routing

## Phase 1: Infrastructure & Backend Scaffolding

- [x] **Task 1: Setup FastAPI Backend Structure** 0cf61e1
    - [x] Sub-task: Create the basic FastAPI application directory and files.
    - [x] Sub-task: Define basic configuration management (environment variables).
- [x] **Task 2: Implement Health Check & Engine Verification** 75f3a1c
    - [x] Sub-task: Write tests for health check endpoints.
    - [x] Sub-task: Implement `/health` endpoint that checks connectivity to configured KataGo engines.
- [ ] **Task: Conductor - User Manual Verification 'Infrastructure & Backend Scaffolding' (Protocol in workflow.md)**

## Phase 2: Authentication System

- [ ] **Task 1: User Data Persistence**
    - [ ] Sub-task: Write tests for user registration/lookup logic.
    - [ ] Sub-task: Implement a simple SQLite-based user repository.
- [ ] **Task 2: JWT Authentication API**
    - [ ] Sub-task: Write tests for the `/login` endpoint and token verification.
    - [ ] Sub-task: Implement JWT creation and middleware for protected routes.
- [ ] **Task 3: Basic Login UI**
    - [ ] Sub-task: Create a simple Login page in React.
    - [ ] Sub-task: Integrate with the `/login` API.
- [ ] **Task: Conductor - User Manual Verification 'Authentication System' (Protocol in workflow.md)**

## Phase 3: Dual-Engine Routing Logic

- [ ] **Task 1: Engine Configuration & Client**
    - [ ] Sub-task: Write tests for the internal KataGo HTTP client.
    - [ ] Sub-task: Implement an asynchronous HTTP client to communicate with external KataGo APIs.
- [ ] **Task 2: Request Routing Proxy**
    - [ ] Sub-task: Write tests for the routing logic (Play vs Analysis).
    - [ ] Sub-task: Implement the `/analyze` endpoint that routes requests based on payload to Local or Cloud engines.
- [ ] **Task: Conductor - User Manual Verification 'Dual-Engine Routing Logic' (Protocol in workflow.md)**

## Phase 4: Integration & Visualization

- [ ] **Task 1: Engine Status Visualization**
    - [ ] Sub-task: Add UI indicators to show which engine is currently processing.
- [ ] **Task 2: Final Integration Test**
    - [ ] Sub-task: Perform a full end-to-end test from UI login to successful dual-engine analysis results.
- [ ] **Task: Conductor - User Manual Verification 'Integration & Visualization' (Protocol in workflow.md)**
