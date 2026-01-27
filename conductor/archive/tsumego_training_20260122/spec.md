# Track Specification: Life and Death (Tsumego) Training Module

## Overview
Implement an interactive "Life and Death" (Tsumego) training module within the Galaxy Web UI. This module will allow users to select difficulty levels, solve problems interactiveley on a board, and track their progress, mirroring the experience of professional Go training platforms like 19x19.com.

## Functional Requirements

### 1. Data Processing (Pre-computation)
- **SGF Filtering & Extraction**: A Python script to process SGF files in `data/life-n-death/`.
    - Filter by type: Only include "死活题" (Life & Death) for the initial launch, though support for "手筋题" (Tesuji) and "官子题" (Endgame) should be architected.
    - Extract metadata: Level (3D, 4D), Problem ID, Type, and Accuracy Rate (from `GC` tag).
- **Offline Verification**: Use KataGo to verify SGF solutions and potentially identify "best" variations if the SGF is ambiguous.
- **Output**: Generate a structured `problems.json` (or similar) mapping levels to problem metadata and file paths.

### 2. Galaxy Web UI - Training Module
- **Level/Unit Navigation**: 
    - A bento-grid or card-based menu to select difficulty (3D, 4D).
    - A problem selection grid showing problem status (Unsolved/Solved).
- **Interactive Board**:
    - Load the initial state of the SGF.
    - Support interactive play (Black to play by default based on SGF).
    - **Validation**: Compare user moves against the SGF branches.
    - **Feedback**: Immediate visual feedback (Success/Failure overlays).
- **Problem Controls**:
    - **Hint**: Show the next correct move from the SGF.
    - **Restart**: Reset the current problem.
    - **Navigation**: Next/Previous problem buttons.
- **Progress Tracking**:
    - Save completion status (Problem ID, timestamp, attempts) to a local `user_progress.json`.
    - Display checkmarks on solved problems in the selection menu.

## Non-Functional Requirements
- **Responsive Layout**: The board and sidebar should adapt to browser window sizes.
- **Performance**: Instant board updates and fast navigation between problems.

## Acceptance Criteria
- [ ] Pre-computation script successfully generates a filtered problem list.
- [ ] Galaxy UI displays the level and problem selection menus.
- [ ] User can play out a problem, receive a "Correct" message upon finishing a valid variation.
- [ ] Hint button reveals the next move.
- [ ] Progress is saved and persists across app restarts.

## Out of Scope
- Automated machine-learning clustering of problems by sub-topic (e.g., "Eye Space").
- Real-time KataGo analysis during gameplay (use pre-computed SGF logic only).
- Multiplayer/Competitive Tsumego modes.
