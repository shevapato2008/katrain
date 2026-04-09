# Report Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the "Report" module for analyzing and visualizing a user's `user_games` using KataGo engine, providing a 1st-level "My Reports" view (polling progress) and a 2nd-level "Report Detail" view (read-only analysis graph).

**Architecture:** 
1. Database tables for `report_tasks` (task tracking) and `report_task_moves` (per-move analysis results) tied to `user_games`.
2. FastAPI endpoints with ownership checks to start analysis, poll progress, and fetch move data.
3. Persistent background analyzer (`ReportAnalyzerService`) running in the FastAPI `lifespan` loop to process queued `report_tasks`.
4. React frontend built on top of the Galaxy layout. Level 1 (My Reports) reuses KifuLibrary layout for list + preview. Level 2 (Report Detail) reuses existing board and analysis components in a read-only mode.

**Tech Stack:** Python (FastAPI, SQLAlchemy), PostgreSQL/SQLite, React (MUI), three.js (via existing board).

---

### Task 1: Database Schema Expansion (SQLAlchemy)

**Files:**
- Modify: `katrain/web/core/models_db.py`
- Create: `tests/web_ui/test_reports_db.py`

- [ ] **Step 1: Add new models in `models_db.py`**

```python
# In katrain/web/core/models_db.py (add near UserGame / UserGameAnalysis)
class ReportTask(Base):
    __tablename__ = "report_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user_game_id = Column(String(32), ForeignKey("user_games.id"), nullable=False, index=True)
    report_type = Column(String(20), default="normal") # normal / deep
    requested_visits = Column(Integer, default=500)
    status = Column(String(20), default="pending") # pending / running / completed / failed
    total_moves = Column(Integer, default=0)
    analyzed_moves = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    user_game = relationship("UserGame", backref="report_tasks")
    moves = relationship("ReportTaskMove", back_populates="task", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_report_tasks_user_created", "user_id", "created_at"),
        Index("ix_report_tasks_game_type_created", "user_game_id", "report_type", "created_at"),
        Index("ix_report_tasks_status_created", "status", "created_at"),
    )

class ReportTaskMove(Base):
    __tablename__ = "report_task_moves"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("report_tasks.id"), nullable=False, index=True)
    move_number = Column(Integer, nullable=False)
    status = Column(String(16), default="success")
    winrate = Column(Float, nullable=True)
    score_lead = Column(Float, nullable=True)
    visits = Column(Integer, nullable=True)
    top_moves = Column(JSON, nullable=True)
    ownership = Column(JSON, nullable=True)
    actual_move = Column(String(8), nullable=True)
    actual_player = Column(String(1), nullable=True)
    delta_score = Column(Float, nullable=True)
    delta_winrate = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    task = relationship("ReportTask", back_populates="moves")

    __table_args__ = (
        UniqueConstraint('task_id', 'move_number', name='uq_report_task_move'),
    )
```

- [ ] **Step 2: Write DB Model Test**

```python
# Create tests/web_ui/test_reports_db.py
# 1. Create a dummy User and UserGame
# 2. Create a ReportTask tied to that UserGame
# 3. Create a ReportTaskMove tied to the ReportTask
# 4. Verify insertion and relationship traversing (e.g. task.moves, task.user_game)
```

- [ ] **Step 3: Commit**

```bash
git add katrain/web/core/models_db.py tests/web_ui/test_reports_db.py
git commit -m "db: add report_tasks and report_task_moves SQLAlchemy models with relationships"
```

### Task 2: Backend API Layer (Auth, Creation & Status)

**Files:**
- Create: `katrain/web/api/v1/endpoints/reports.py`
- Modify: `katrain/web/api/v1/api.py`
- Create: `tests/web_ui/test_reports_api.py`

- [ ] **Step 1: Create Endpoint File**

```python
# katrain/web/api/v1/endpoints/reports.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from katrain.web.core import models_db
from katrain.web.api.v1.endpoints.auth import get_current_user

router = APIRouter()

class ReportTaskCreate(BaseModel):
    user_game_id: str
    report_type: str = "normal"
    force: bool = False

class ReportTaskStatus(BaseModel):
    id: int
    user_game_id: str
    status: str
    report_type: str
    total_moves: int
    analyzed_moves: int
    
    class Config:
        from_attributes = True

# Placeholder for dependencies
def get_db():
    pass # Replaced by actual get_db

@router.post("/", response_model=ReportTaskStatus)
async def create_report_task(task: ReportTaskCreate, current_user = Depends(get_current_user)):
    # TODO: implementation
    # 1. Verify ownership of user_game_id
    # 2. Check for existing pending/running tasks (idempotency)
    # 3. Create or return existing task
    raise HTTPException(status_code=501, detail="Not implemented")

@router.get("/", response_model=List[ReportTaskStatus])
async def list_report_tasks(current_user = Depends(get_current_user)):
    # TODO: fetch user's tasks (can also return user_games combined with latest report status)
    raise HTTPException(status_code=501, detail="Not implemented")

@router.get("/{task_id}", response_model=ReportTaskStatus)
async def get_report_status(task_id: int, current_user = Depends(get_current_user)):
    # TODO: fetch specific task, verify ownership
    raise HTTPException(status_code=501, detail="Not implemented")

@router.get("/{task_id}/moves")
async def get_report_moves(task_id: int, current_user = Depends(get_current_user)):
    # TODO: fetch all report_task_moves for task_id, verify ownership
    raise HTTPException(status_code=501, detail="Not implemented")
```

- [ ] **Step 2: Register Router in `api.py`**

```python
# In katrain/web/api/v1/api.py
from katrain.web.api.v1.endpoints import reports
# ...
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
```

- [ ] **Step 3: Write API Test (Failing/Mocked)**

```python
# Create tests/web_ui/test_reports_api.py
# Test POST /api/v1/reports with bad game_id (should 404 or 403)
# Test POST /api/v1/reports with valid game_id (idempotency)
# Test GET /api/v1/reports/{task_id}/moves
```

- [ ] **Step 4: Commit**

```bash
git add katrain/web/api/v1/endpoints/reports.py katrain/web/api/v1/api.py tests/web_ui/test_reports_api.py
git commit -m "feat(api): scaffold report API endpoints including moves and idempotency tests"
```

### Task 3: Backend Analyzer Service (DB-Backed Polling)

**Files:**
- Create: `katrain/web/report/analyzer.py`
- Modify: `katrain/web/server.py`

- [ ] **Step 1: Create `ReportAnalyzerService`**

```python
# katrain/web/report/analyzer.py
import asyncio
import logging
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ReportAnalyzerService:
    def __init__(self, session_factory, katago_url="http://127.0.0.1:8000"):
        self.session_factory = session_factory
        self.katago_url = katago_url
        self._running = False
        self._task = None

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._analysis_loop())
            logger.info("ReportAnalyzerService started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("ReportAnalyzerService stopped")

    async def _analysis_loop(self):
        while self._running:
            try:
                # 1. Stale task reset: find 'running' tasks updated > 5 mins ago -> set 'pending'
                # 2. Pick next 'pending' task
                # 3. Mark 'running', parse SGF to get total_moves
                # 4. Process each move, map report_type to requested_visits
                # 5. Insert to report_task_moves
                # 6. Update analyzed_moves, mark 'completed' when done
                pass
            except Exception as e:
                logger.error(f"Analysis loop error: {e}")
            await asyncio.sleep(5)
```

- [ ] **Step 2: Wire into FastAPI Lifespan**

```python
# In katrain/web/server.py
# Import ReportAnalyzerService and session_factory
# In lifespan(app: FastAPI):
#   report_analyzer = ReportAnalyzerService(SessionLocal)
#   report_analyzer.start()
#   yield
#   await report_analyzer.stop()
```

- [ ] **Step 3: Commit**

```bash
git add katrain/web/report/analyzer.py katrain/web/server.py
git commit -m "feat(backend): add ReportAnalyzerService with retry and stale task recovery"
```

### Task 4: Frontend Routing & Skeleton (Galaxy Layout)

**Files:**
- Modify: `katrain/web/ui/src/GalaxyApp.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.tsx`
- Create: `katrain/web/ui/src/galaxy/pages/report/ReportsPage.tsx`
- Create: `katrain/web/ui/src/galaxy/pages/report/ReportDetailPage.tsx`

- [ ] **Step 1: Create Page Skeletons**

```tsx
// katrain/web/ui/src/galaxy/pages/report/ReportsPage.tsx
import React from 'react';
import { Box, Typography } from '@mui/material';

export default function ReportsPage() {
    return (
        <Box p={3}>
            <Typography variant="h4">My Reports</Typography>
        </Box>
    );
}

// katrain/web/ui/src/galaxy/pages/report/ReportDetailPage.tsx
import React from 'react';
import { useParams } from 'react-router-dom';
import { Box, Typography } from '@mui/material';

export default function ReportDetailPage() {
    const { taskId } = useParams();
    return (
        <Box p={3}>
            <Typography variant="h4">Report Detail: {taskId}</Typography>
        </Box>
    );
}
```

- [ ] **Step 2: Add Routes & Enable Sidebar Link**

```tsx
// In katrain/web/ui/src/GalaxyApp.tsx
import ReportsPage from './galaxy/pages/report/ReportsPage';
import ReportDetailPage from './galaxy/pages/report/ReportDetailPage';

// Inside <Routes><Route element={<MainLayout />}>
<Route path="report" element={<ReportsPage />} />
<Route path="report/:taskId" element={<ReportDetailPage />} />
```
```tsx
// In katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.tsx
// Change disabled: true to disabled: false for the Report path
{ text: t('analysis:report', 'Report'), icon: <AssessmentIcon />, path: '/galaxy/report', disabled: false },
```

- [ ] **Step 3: Commit**

```bash
git add katrain/web/ui/src/GalaxyApp.tsx katrain/web/ui/src/galaxy/pages/report/ katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.tsx
git commit -m "feat(ui): setup galaxy report routes and skeletons"
```

### Task 5: Frontend Level 1 - My Reports List & Polling

**Files:**
- Modify: `katrain/web/ui/src/galaxy/pages/report/ReportsPage.tsx`
- Create: `katrain/web/ui/src/galaxy/pages/report/ReportsPage.test.tsx`

- [ ] **Step 1: Implement `useReportTasks` Polling Hook**

```tsx
// inside ReportsPage.tsx or a hooks folder
import { useState, useEffect } from 'react';

function useReportTasks() {
    const [tasks, setTasks] = useState([]);
    
    useEffect(() => {
        // Poll every 2 seconds (only if there are pending/running tasks)
        const interval = setInterval(() => {
            // fetch /api/v1/reports
            // setTasks(data)
        }, 2000);
        return () => clearInterval(interval);
    }, []);

    return tasks;
}
```

- [ ] **Step 2: Implement dual-panel UI (KifuLibrary style)**

*Left Panel: Task List. Right Panel: SGF Preview of selected game.*
*The list data should combine all user_games and their report status.*
*Upload SGF workflow: Use existing `POST /api/v1/user-games/` to upload game, then trigger `POST /api/v1/reports`.*

- [ ] **Step 3: Write Frontend Test**

*Add a basic render test `katrain/web/ui/src/galaxy/pages/report/ReportsPage.test.tsx` verifying the layout.*

- [ ] **Step 4: Commit**

```bash
git add katrain/web/ui/src/galaxy/pages/report/ReportsPage.tsx katrain/web/ui/src/galaxy/pages/report/ReportsPage.test.tsx
git commit -m "feat(ui): implement report list polling, existing SGF import, and layout"
```

### Task 6: Frontend Level 2 - Report Detail Read-Only View

**Files:**
- Modify: `katrain/web/ui/src/galaxy/pages/report/ReportDetailPage.tsx`

- [ ] **Step 1: Implement detail layout reusing LiveBoard/ResearchBoard**

*Fetch `/api/v1/reports/{taskId}/moves` to get all snapshot data. Feed this data to existing graph components and board.*
*Ensure variations/branches either redirect to `/galaxy/research` or are handled read-only.*

- [ ] **Step 2: Commit**

```bash
git add katrain/web/ui/src/galaxy/pages/report/ReportDetailPage.tsx
git commit -m "feat(ui): implement report detail view using snapshot data"
```