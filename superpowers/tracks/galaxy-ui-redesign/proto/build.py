import io, os
OUT = 'galaxy-prototype.html'
logo = open('logo.txt').read().strip()
parts = []
parts.append(open('01-head.html', encoding='utf-8').read())
parts.append(open('03-app.css', encoding='utf-8').read())
parts.append(open('03b-legacy.css', encoding='utf-8').read())
parts.append(open('02-icons.html', encoding='utf-8').read())
parts.append(open('05-body.html', encoding='utf-8').read())
parts.append('<script>\nconst LOGO = "%s";\n</script>\n' % logo)
import glob
screen_files = sorted(glob.glob('07*-screens.js'))
for js in ['04-runtime.js'] + screen_files + ['10-v2.js', '06-shell.js', '09-overview.js', '08-events.js']:
    parts.append('<script>\n' + open(js, encoding='utf-8').read() + '\n</script>\n')
html = '\n'.join(parts)
open(OUT, 'w', encoding='utf-8').write(html)
print(OUT, len(html), 'bytes', round(len(html.encode())/1024, 1), 'KiB')
