import { test, expect } from '@playwright/test';

test('place a stone on the board', async ({ page }) => {
  await page.goto('/');
  await page.waitForLoadState('networkidle');

  // Check initial state
  const initialStonesCount = await page.evaluate(() => {
    // We can't easily access React state from here, but we can check for elements if we had them.
    // However, we can listen to the WebSocket or check if API calls were made.
    return 0; // dummy
  });

  // Click on the board (centerish)
  const board = page.locator('canvas');
  const box = await board.boundingBox();
  if (!box) throw new Error("Board not found");

  // Clicking center of 19x19 board (approximately)
  // The board is 800x800 in drawing pixels.
  // We click the center of the canvas.
  await board.click({ position: { x: box.width / 2, y: box.height / 2 } });

  // Wait for the move to be processed (state update)
  // We expect a POST request to /api/move
  const moveResponse = await page.waitForResponse(response => 
    response.url().includes('/api/move') && response.status() === 200
  );
  const data = await moveResponse.json();
  
  // Verify that a move was played
  expect(data.state.stones.length).toBeGreaterThan(0);
  console.log("Successfully played move:", data.state.last_move);
});
