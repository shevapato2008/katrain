# Track: User Authentication and Registration UI

## Goal
Improve the user authentication flow by allowing users to view the main page without being logged in and providing explicit "Login" and "Register" buttons.

## Tasks
- [x] **Backend:** Add a registration endpoint to `/api/v1/auth/register`.
- [x] **Frontend (API):** Add `register` method to `API` object in `api.ts`.
- [x] **Frontend (Components):** Create `RegisterDialog.tsx`.
- [x] **Frontend (UI):** Update `TopBar.tsx` or `Sidebar.tsx` to include Login/Register buttons when not authenticated.
- [x] **Frontend (Logic):** Refactor `App.tsx` to allow rendering the main UI even if `token` is null, while gatekeeping specific actions.
- [x] **Verification:** Test the registration and login flow manually.

## Progress
- Initialized track and plan.
- Implemented backend registration endpoint.
- Implemented `RegisterDialog` and updated `LoginDialog`.
- Refactored `App.tsx` to allow anonymous access.
- Integrated Login/Register/Logout buttons into `TopBar`.
