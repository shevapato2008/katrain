# 棋盘木纹贴图

`darkwood_512.jpg` —— **Poly Haven，CC0**。

字节与象棋 / 国象 / 五子棋三家**完全相同**（`sha256 58e43174…`，51733 字节），
出处见 `smartbox-software/xiangqi/ui/src/skins.tsx:11`。三家都已上板。

## 为什么不放进 `src/kiosk-shell/`

那个目录是**从上游共享包整目录抄来的**，由 `MANIFEST.sha256` 逐文件钉住（209 条）。
这张图**不在上游那份清单里** —— 塞进去就等于伪造「和上游一致」。
落在这里，走 Vite import / CSS `url()`，和三家同构。

要不要把它推给上游共享资产包（四家共用一份、由上游 MANIFEST 管辖）是**另一件事**，
`scope.md:977` 那句「请 Fan 定」问的就是这个。
