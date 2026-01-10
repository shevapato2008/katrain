We are about to develop a new module named "Life & Death" ("死活棋" in Chinese) in addition to the current "Human vs. Human" and "Human vs. AI" modules.
(1) We have developed a scraping tool to get the corresponding SGF files (sample files @data/life-n-death/2D/*.sgf) from 101weiqi.com.
  (1.1) After choosing "Life & Death" module, you can choose the problems by level of strength then you'll be brought to a page where problems are listed like what Image #1 shows. 
  
(2) For a specific problem, 101weiqi.com presents it like Image #2, in which the problem always has an initial state, i.e. a bunch of black and white stones.
  (2.1) You can continue to play until the problem is resolved. In the SGF file, we already include possibly several solutions to a problem. 
  (2.2) You can load the file using the
  existing frontend board. However, it is highly prefered to show only a small portion of the board where the initial stones are placed. We also need to have some backend
  logics: for example, you can show a pop-up window to notify the user they have placed