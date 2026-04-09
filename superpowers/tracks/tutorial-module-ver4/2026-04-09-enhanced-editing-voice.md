# Enhanced Board Editing and Voice Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add lowercase letter support to the board editor with manual sequence control, and make tutorial figure narration editable with on-demand voice generation.

**Architecture:** We will extend the existing React `useBoardEditor` hook and `EditTool` types to support both uppercase and lowercase letters, along with a new input field in the toolbar to control the `nextLetter` state. For the voice feature, we'll create a new FastAPI endpoint that invokes `edge-tts` (refactoring logic from `scripts/generate_voice.py` into a new `services.py`), updating the figure's `audio_asset` in the database. The frontend `TutorialFigurePage` will be updated to support editing the `narration` text and calling this new endpoint to regenerate audio.

**Tech Stack:** React, TypeScript, Kivy (frontend), FastAPI, Python, edge-tts, SQLAlchemy (backend).

---

### Task 1: Update Frontend Types for Board Editing

**Files:**
- Modify: `katrain/web/ui/src/types/tutorial.ts`

- [ ] **Step 1: Update `EditTool` type**
Modify `katrain/web/ui/src/types/tutorial.ts` to replace the existing `'letter'` tool with `'letter_upper'` and `'letter_lower'`.

```typescript
// Look for export type EditTool = 'stone_b' | 'stone_w' | ...
// Replace 'letter' with 'letter_upper' | 'letter_lower'
export type EditTool = 'stone_b' | 'stone_w' | 'triangle' | 'square' | 'circle' | 'cross' | 'letter_upper' | 'letter_lower' | 'number' | 'clear';
```

- [ ] **Step 2: Commit**
```bash
git add katrain/web/ui/src/types/tutorial.ts
git commit -m "feat(ui): update EditTool type to support upper and lowercase letters"
```

### Task 2: Enhance `useBoardEditor` Hook

**Files:**
- Modify: `katrain/web/ui/src/galaxy/hooks/useBoardEditor.ts`

- [ ] **Step 1: Add `nextLetter` state and update `setActiveTool`**
In `katrain/web/ui/src/galaxy/hooks/useBoardEditor.ts`, add a `nextLetter` state and initialize it when tools change.

```typescript
import { useState } from 'react';

// Add state inside useBoardEditor hook
const [nextLetter, setNextLetter] = useState<string>('A');

// Update setActiveTool logic to reset nextLetter
const handleSetActiveTool = (tool: EditTool) => {
    setActiveTool(tool);
    if (tool === 'letter_upper') setNextLetter('A');
    if (tool === 'letter_lower') setNextLetter('a');
    if (tool === 'number') setNextNumber(1);
};
```

- [ ] **Step 2: Update `handleClick` to handle new letter tools**
Update the logic inside `handleClick` to check for `letter_upper` and `letter_lower`, use `nextLetter`, and increment it correctly.

```typescript
// Inside handleClick, replace the old 'letter' logic:
if (activeTool === 'letter_upper' || activeTool === 'letter_lower') {
    newMarks[key] = { type: 'letter', text: nextLetter };
    setNextLetter(String.fromCharCode(nextLetter.charCodeAt(0) + 1));
}
```

- [ ] **Step 3: Return new state from hook**
Make sure to expose `nextLetter` and `setNextLetter`.

```typescript
return {
    // ... existing returns
    nextLetter,
    setNextLetter,
    setActiveTool: handleSetActiveTool,
    // ...
};
```

- [ ] **Step 4: Commit**
```bash
git add katrain/web/ui/src/galaxy/hooks/useBoardEditor.ts
git commit -m "feat(ui): add nextLetter state and logic to useBoardEditor"
```

### Task 3: Update Board Edit Toolbar UI

**Files:**
- Modify: `katrain/web/ui/src/galaxy/components/tutorials/BoardEditToolbar.tsx`

- [ ] **Step 1: Replace 'letter' button with upper/lower buttons**
Update the buttons in `katrain/web/ui/src/galaxy/components/tutorials/BoardEditToolbar.tsx` and add an input for `nextLetter`.

```tsx
import TitleIcon from '@mui/icons-material/Title';
import TextFormatIcon from '@mui/icons-material/TextFormat';
import TextField from '@mui/material/TextField';
import Tooltip from '@mui/material/Tooltip';
import ToggleButton from '@mui/material/ToggleButton';

// Find the old letter button and replace it
<Tooltip title="大写字母">
    <ToggleButton value="letter_upper" aria-label="letter_upper">
        <TitleIcon />
    </ToggleButton>
</Tooltip>
<Tooltip title="小写字母">
    <ToggleButton value="letter_lower" aria-label="letter_lower">
        <TextFormatIcon />
    </ToggleButton>
</Tooltip>

// Add conditional TextField for nextLetter near the toolbar
{(activeTool === 'letter_upper' || activeTool === 'letter_lower') && (
    <TextField
        size="small"
        label="Next Letter"
        value={nextLetter}
        onChange={(e) => setNextLetter(e.target.value)}
        sx={{ width: 100, ml: 2 }}
    />
)}
```
*Note: Ensure `nextLetter` and `setNextLetter` are passed as props or extracted from the hook if the hook is called here.*

- [ ] **Step 2: Commit**
```bash
git add katrain/web/ui/src/galaxy/components/tutorials/BoardEditToolbar.tsx
git commit -m "feat(ui): add upper/lower letter buttons and input to BoardEditToolbar"
```

### Task 4: Create Backend TTS Service

**Files:**
- Create: `katrain/web/api/v1/services/tutorials_tts.py`

- [ ] **Step 1: Implement `generate_figure_audio`**
Create `katrain/web/api/v1/services/tutorials_tts.py` to handle `edge-tts` generation.

```python
import os
import asyncio
from pathlib import Path
import edge_tts
from sqlalchemy.orm import Session
# Adjust import path based on actual models location
from katrain.web.database.models import TutorialFigure

async def _generate_audio_async(text: str, output_path: str, voice: str = "zh-CN-YunxiNeural"):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def generate_figure_audio(db: Session, figure: TutorialFigure, text: str) -> str:
    """Generates audio for the given text and updates the figure's audio_asset."""
    # Define paths
    assets_dir = Path("data/tutorial_assets")
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"figure_{figure.id}_audio.mp3"
    filepath = assets_dir / filename
    
    # Generate audio
    asyncio.run(_generate_audio_async(text, str(filepath)))
    
    # Update figure
    asset_path = f"tutorial_assets/{filename}"
    figure.audio_asset = asset_path
    figure.narration = text
    db.commit()
    db.refresh(figure)
    
    return asset_path
```

- [ ] **Step 2: Commit**
```bash
git add katrain/web/api/v1/services/tutorials_tts.py
git commit -m "feat(backend): add generate_figure_audio service using edge-tts"
```

### Task 5: Add Generate Audio API Endpoint

**Files:**
- Modify: `katrain/web/api/v1/endpoints/tutorials.py`
- Modify: `katrain/web/api/v1/schemas/tutorials.py` (if needed for `NarrationUpdateRequest`)

- [ ] **Step 1: Define request schema**
In the appropriate schemas file (e.g., `katrain/web/api/v1/schemas/tutorials.py` or similar), add:
```python
from pydantic import BaseModel

class NarrationUpdateRequest(BaseModel):
    narration: str
```

- [ ] **Step 2: Add POST endpoint**
In `katrain/web/api/v1/endpoints/tutorials.py`:
```python
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from katrain.web.database.database import get_db
# Adjust model imports
from katrain.web.database.models import TutorialFigure
from katrain.web.api.v1.services.tutorials_tts import generate_figure_audio
# Adjust schema imports
from katrain.web.api.v1.schemas.tutorials import NarrationUpdateRequest

# Add this endpoint
@router.post("/figures/{figure_id}/generate-audio")
def generate_audio_for_figure(
    figure_id: int, 
    request: NarrationUpdateRequest,
    db: Session = Depends(get_db)
):
    figure = db.query(TutorialFigure).filter(TutorialFigure.id == figure_id).first()
    if not figure:
        raise HTTPException(status_code=404, detail="Figure not found")
        
    audio_asset = generate_figure_audio(db, figure, request.narration)
    
    return {"status": "success", "audio_asset": audio_asset, "narration": figure.narration}
```

- [ ] **Step 3: Commit**
```bash
git add katrain/web/api/v1/endpoints/tutorials.py
git commit -m "feat(backend): add POST /figures/{id}/generate-audio endpoint"
```

### Task 6: UI for Editable Narration & Voice Generation

**Files:**
- Modify: `katrain/web/ui/src/galaxy/pages/tutorials/TutorialFigurePage.tsx`

- [ ] **Step 1: Add state and edit button for narration**
Add state to toggle edit mode and store the edited text.

```tsx
import { useState, useEffect } from 'react';
import { TextField, Button, Box, Typography } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import RecordVoiceOverIcon from '@mui/icons-material/RecordVoiceOver';

// Inside component
const [isEditingNarration, setIsEditingNarration] = useState(false);
const [editedNarration, setEditedNarration] = useState(figure?.narration || '');

// Update when figure loads
useEffect(() => {
    if (figure) setEditedNarration(figure.narration || '');
}, [figure]);
```

- [ ] **Step 2: Implement generate audio handler**
```tsx
const handleGenerateAudio = async () => {
    try {
        const response = await fetch(`/api/v1/figures/${figureId}/generate-audio`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ narration: editedNarration }),
        });
        if (response.ok) {
            const data = await response.json();
            // Assuming there's a function to refresh the figure data or update local state
            setFigure(prev => prev ? { ...prev, audio_asset: data.audio_asset, narration: data.narration } : prev);
            setIsEditingNarration(false);
        }
    } catch (error) {
        console.error("Failed to generate audio", error);
    }
};
```

- [ ] **Step 3: Render editable narration and buttons**
```tsx
// Replace the static narration text section with:
<Box sx={{ mt: 2 }}>
    <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
        <Typography variant="h6">语音讲解</Typography>
        <Button 
            startIcon={<EditIcon />} 
            onClick={() => setIsEditingNarration(!isEditingNarration)} 
            size="small" 
            sx={{ ml: 2 }}
        >
            编辑
        </Button>
    </Box>
    
    {isEditingNarration ? (
        <Box>
            <TextField
                multiline
                fullWidth
                rows={4}
                value={editedNarration}
                onChange={(e) => setEditedNarration(e.target.value)}
                variant="outlined"
                sx={{ mb: 2 }}
            />
            <Button 
                variant="contained" 
                color="primary" 
                startIcon={<RecordVoiceOverIcon />}
                onClick={handleGenerateAudio}
            >
                生成语音并保存
            </Button>
            <Button onClick={() => setIsEditingNarration(false)} sx={{ ml: 1 }}>
                取消
            </Button>
        </Box>
    ) : (
        <Typography variant="body1">{figure?.narration}</Typography>
    )}
    
    {/* Ensure the existing audio player uses figure?.audio_asset appropriately */}
</Box>
```

- [ ] **Step 4: Commit**
```bash
git add katrain/web/ui/src/galaxy/pages/tutorials/TutorialFigurePage.tsx
git commit -m "feat(ui): make narration editable and add generate voice button"
```
