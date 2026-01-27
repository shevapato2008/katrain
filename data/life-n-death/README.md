# 死活题题库管理

## 目录结构

```
data/life-n-death/
├── 3D/              # 3段难度题目
│   ├── 1014.sgf
│   └── ...
├── 4D/              # 4段难度题目
│   └── ...
├── index.json       # 自动生成的索引文件
└── README.md        # 本文件
```

## SGF文件规范

```sgf
(;GM[1]FF[4]CA[UTF-8]SZ[19]
GN[Q-1014]                    ; 题目编号（文件名应与此一致）
C[黑先 死活题]                 ; 提示，包含"手筋"/"官子"可自动识别题型
AB[pa][rd][pb]...             ; 黑子初始位置
AW[nc][qf][oa]...             ; 白子初始位置
PL[B]                         ; 先手方 B=黑先 W=白先
SO[https://...]               ; 来源（可选）

(;B[qd]...C[恭喜答对])         ; 正确变化
(;B[ka]...C[失败，重来吧])      ; 错误变化
)
```

## 日常操作

### 添加新题目

1. 将SGF文件放入对应难度目录（如 `3D/1234.sgf`）
2. 运行同步脚本：
   ```bash
   python scripts/generate_tsumego_index.py
   python scripts/sync_tsumego_db.py --dry-run
   python scripts/sync_tsumego_db.py
   ```

### 调整题目难度

1. 移动文件：`mv data/life-n-death/3D/1014.sgf data/life-n-death/4D/`
2. 运行同步脚本
3. 用户进度自动保留（按题号追踪）

### 批量添加新难度

1. 创建目录：`mkdir data/life-n-death/5D`
2. 放入SGF文件
3. 运行同步脚本

## 题型自动识别

| 关键词 | 分类 | 标识 |
|--------|------|------|
| 手筋 | 手筋题 | tesuji |
| 官子 | 官子题 | endgame |
| 其他 | 死活题 | life-death |

## 注意事项

- **题号唯一**：不同难度目录下不要有相同文件名
- **编码格式**：UTF-8
- **Git提交**：修改后记得提交 index.json
