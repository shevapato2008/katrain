# Galaxy 中文字体子集

本目录只供 Galaxy 前端导入；不要从 KaTrain 通用 UI、桌面 UI 或全局样式入口引用 `galaxy-fonts.css`。生成产物只使用下列固定的比例字体输入。

## 上游与许可

- LXGW WenKai Regular / Medium：官方 v1.522 release，依照未经修改的 `OFL-LXGW-WenKai.txt`（SIL OFL 1.1）分发。
- Long Cang Regular：Google Fonts 仓库提交 `b7b1d76caa907473438546739b2ce3a92631adc3`，依照未经修改的 `OFL-Long-Cang.txt`（SIL OFL 1.1）分发。

Long Cang 只保留品牌文字“智星盒”。LXGW WenKai Regular 映射到字重 400；Medium 映射到字重 500–700。中文 gettext catalog 的 cn、tw 字符优先进入第一个分片，其余允许的 CJK 字符按码点顺序稳定分片。ASCII、全角 Latin 字母与数字、kana、hangul 均不进入字体。

## 精确复现

从仓库根目录运行：

```sh
OUT=katrain/web/ui/src/galaxy/assets/fonts
uv run --with fonttools==4.61.1 --with brotli==1.2.0 python scripts/build_galaxy_fonts.py \
  --regular /private/tmp/galaxy-font-sources/LXGWWenKai-Regular.ttf \
  --medium /private/tmp/galaxy-font-sources/LXGWWenKai-Medium.ttf \
  --longcang /private/tmp/galaxy-font-sources/LongCang-Regular.ttf \
  --out "$OUT"
```

调用者须先把三个固定上游 TTF 放入上述 `/private/tmp/galaxy-font-sources` 路径。生成器对每个输入只打开一次，流式复制到同父私有 staging 并同步校验 SHA-256；后续生成只读取私有快照，不下载、不修改也不把 TTF 写入仓库。所有产物在 staging 完成；成功发布前先把旧生成资源移入同文件系统 backup，失败会完整回滚，成功时最后原子替换 manifest。非生产输出目录必须不存在或为空。

这是供受信任开发环境使用的本地生成器；运行期间不要让其他进程修改输入或输出路径。本工具不试图防御同权限恶意本地进程，因为该进程本就能直接修改仓库。

固定输入及其 `sources.json` 哈希为：

- `LXGWWenKai-Regular.ttf`：`39ad71264b588165b469e35e6afb162a378dacd1f95348160240ba9038ac3009`
- `LXGWWenKai-Medium.ttf`：`d4bdeb38a39151d74d084cba5090f8cb7d20bf83eedb78c35939ae70b9f4e3f6`
- `LongCang-Regular.ttf`：`e5bf2c3f24ef2327c6f136d8f73e2f9dfdf44896fdbeb35a9515f44777bb91bc`

`sources.json` 记录固定 URL、版本、许可、每个输入 SHA-256，固定工具链 `fonttools==4.61.1` / `brotli==1.2.0`，以及所有生成输出的字节数与 SHA-256。manifest 中命令使用规范化的 `$OUT`，因此不同临时输出路径不会改变产物。
