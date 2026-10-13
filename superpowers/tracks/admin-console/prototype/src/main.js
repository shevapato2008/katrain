// ---------- Boot ----------
(() => { const h = location.hash.slice(1); if (pages[h]) S.page = h; })();
render();
