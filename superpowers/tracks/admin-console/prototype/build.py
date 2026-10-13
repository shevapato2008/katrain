import base64, re
from pathlib import Path
here = Path(__file__).parent; src = here / "src"
repo = Path('/Users/fan/Repositories/katrain-admin-console'); ui = repo / 'katrain/web/ui/src'
font = base64.b64encode((ui / 'galaxy/assets/fonts/longcang-brand.woff2').read_bytes()).decode()
logo = base64.b64encode((repo / 'katrain/img/logo-white.png').read_bytes()).decode()
admin = (ui / 'admin/AdminApp.css').read_text()
assert admin.count("@import url('../galaxy/assets/fonts/galaxy-fonts.css')") == 1
admin = admin.replace("@import url('../galaxy/assets/fonts/galaxy-fonts.css');", '')
css = '@font-face{font-family:"Galaxy Long Cang";src:url(data:font/woff2;base64,%s) format("woff2");font-display:swap;unicode-range:U+661F,U+667A,U+76D2}\n' % font
css += admin + '\n' + (ui / 'admin/cron/CronPage.css').read_text() + '\n' + (src / 'proto.css').read_text()
js = '\n'.join((src / f).read_text() for f in ('core.js', 'shell.js', 'pages-a.js', 'pages-b.js', 'capture.js', 'lab.js', 'main.js'))
js = js.replace('__LOGO__', 'data:image/png;base64,' + logo)
html = '<title>智星盒后台设计稿</title>\n<style>\n' + css + '\n</style>\n<div id="app" class="proto-scroll"></div>\n<script>\n"use strict";\n' + js + '\n</script>\n'
(here / 'index.html').write_text(html)
print(len(html) // 1024, 'KiB')
