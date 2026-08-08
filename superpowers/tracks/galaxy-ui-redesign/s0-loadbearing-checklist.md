# S0 承重结构实测 · 清单（**先写死关系式，后读数**）

触发判定（反查）：把 S0 撤回去，`MainLayout` 从三块变回两块，
左边栏的 `height` 从 `100%` 变回 `100vh` —— **页面上元素的高度来源与裁切边界会变**，触发。

改动前后的链：

```
改前  body → [ 左边栏(height:100vh) | main(overflow:auto) ]
改后  body → 外层 column(100vh, hidden)
              ├ 顶栏 52 (flex:none)
              └ 中间行 (flex:1 1 auto, **minHeight:0**, hidden)
                  ├ 左边栏 (height:100%, minHeight:0, column)
                  │    ├ 导航 List (flexGrow:1, **minHeight:0, overflowY:auto**)  ←该滚的是它
                  │    └ 身份块 (flex:none)
                  └ main (flexGrow:1, minWidth:0, minHeight:0, overflow:auto)
```

**该滚的是谁**：左边栏的导航 `List` **它自己**，不是它的祖先、不是 `main`、不是 `body`。

## 造数据

导航默认只有 8 项，1440×900 下装得下 —— **装得下时量出来的数一概不算**。
量之前把导航项灌到两屏以上（注入到 `nav` 里），再量。

## 判据（关系式先写死，具体像素只记录不作判据）

| # | 量什么 | 关系式期望 |
|---|---|---|
| 1 | 顶栏占位 | `topbar.height === 52` |
| 2 | 高度传递 | `row.clientHeight === innerHeight - 52`（顶栏吃掉的正好是 52，不多不少） |
| 3 | 页面不滚 | `document.documentElement.scrollHeight === clientHeight` 且 `body` 同理 |
| 4 | 左边栏不越界 | `sidebar.getBoundingClientRect().bottom <= innerHeight`（改前 `100vh` 会超出正好 52） |
| 5 | **能不能滚** | 灌满后 `nav.scrollHeight > nav.clientHeight` |
| 6 | 程序化滚 | 写入 `nav.scrollTop = 99999` 后**读回非 0** |
| 7 | **手指拨得动** | 真浏览器派发一次滚轮事件，`nav.scrollTop` 变化量 ≠ 0（程序化能滚 ≠ 拨得动） |
| 8 | 滚的是它不是祖先 | 滚动后 `row.scrollTop === 0` 且 `document.documentElement.scrollTop === 0` |
| 9 | 身份块贴得住 | 导航滚到底后，身份块 `rect.bottom <= innerHeight` 且 `rect.top >= 0`（它 `flex:none`，不在滚动容器里） |
| 10 | 没被祖先裁掉 | 身份块 border box 完整落在中间行的裁切框内 |

不适用项必须写「不适用 + 一句为什么」，不许空过。

## 视口

1440×900（标准档）与 1024×768（窄档）各一次。
`main` 内容区的滚动归 S1（右边栏），本切片不量 —— S0 没有改 `main` 内部任何东西。
