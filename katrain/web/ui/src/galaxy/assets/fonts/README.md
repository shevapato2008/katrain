# Galaxy 中文字体子集

本目录只供 Galaxy 前端导入；不要从 KaTrain 通用 UI、桌面 UI 或全局样式入口引用 `galaxy-fonts.css`。生成产物只使用下列固定的比例字体输入。

## 上游与许可

- LXGW WenKai Regular / Medium：官方 v1.522 release，SIL Open Font License 1.1。
- Long Cang Regular：Google Fonts 仓库提交 `b7b1d76caa907473438546739b2ce3a92631adc3`，SIL Open Font License 1.1。
- 本目录中的 Regular、Medium、Long Cang 三种字体均依照 `OFL-1.1.txt` 的 SIL OFL 1.1 分发。

Long Cang 只保留品牌文字“智星盒”。LXGW WenKai Regular 映射到字重 400；Medium 映射到字重 500–700。中文 gettext catalog 的 cn、tw 字符优先进入第一个分片，其余允许的 CJK 字符按码点顺序稳定分片。ASCII、全角 Latin 字母与数字、kana、hangul 均不进入字体。

## 精确复现

从仓库根目录运行：

```sh
OUT=katrain/web/ui/src/galaxy/assets/fonts
uv run --with fonttools --with brotli python scripts/build_galaxy_fonts.py --output "$OUT"
```

生成器会把三个固定上游 TTF 缓存到 `/private/tmp/galaxy-font-sources`，逐一校验 SHA-256，且不会把 TTF 写入仓库。生产目录只清理生成器拥有的 WOFF2、CSS 和 manifest；非生产输出目录必须不存在或为空。

固定输入及其 `sources.json` 哈希为：

- `LXGWWenKai-Regular.ttf`：`39ad71264b588165b469e35e6afb162a378dacd1f95348160240ba9038ac3009`
- `LXGWWenKai-Medium.ttf`：`d4bdeb38a39151d74d084cba5090f8cb7d20bf83eedb78c35939ae70b9f4e3f6`
- `LongCang-Regular.ttf`：`e5bf2c3f24ef2327c6f136d8f73e2f9dfdf44896fdbeb35a9515f44777bb91bc`

`sources.json` 记录固定 URL、版本、许可、每个输入 SHA-256，以及所有生成输出的字节数与 SHA-256。manifest 中命令使用规范化的 `$OUT`，因此不同临时输出路径不会改变产物。
