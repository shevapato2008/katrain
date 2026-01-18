import os
import re

# Define translations for CN and TW
TRANSLATIONS = {
    "cn": {
        "player:human": "人类",
        "ai:default": "推荐 (Recommended)",
        "ai:human": "类人 AI (Human-like)",
        "ai:pro": "历史职业棋手 (Historical Pro)",
        "ai:jigo": "和棋模式 (KataJigo)",
        "ai:antimirror": "反镜像 (KataAntiMirror)",
        "game:normal": "普通模式",
        "game:teach": "教学模式",
        "AI": "AI",
        "Human": "人类"
    },
    "tw": {
        "player:human": "人類",
        "ai:default": "推薦 (Recommended)",
        "ai:human": "類人 AI (Human-like)",
        "ai:pro": "歷史職業棋手 (Historical Pro)",
        "ai:jigo": "和棋模式 (KataJigo)",
        "ai:antimirror": "反鏡像 (KataAntiMirror)",
        "game:normal": "普通模式",
        "game:teach": "教學模式",
        "AI": "AI",
        "Human": "人類"
    }
}

# Fallback values for other languages (use the English label)
FALLBACKS = {
    "player:human": "Human",
    "ai:default": "Recommended",
    "ai:human": "Human-like",
    "ai:pro": "Historical Pro",
    "ai:jigo": "KataJigo",
    "ai:antimirror": "KataAntiMirror",
    "game:normal": "Normal",
    "game:teach": "Teaching",
    "AI": "AI",
    "Human": "Human"
}

LOCALES_DIR = "katrain/i18n/locales"

def update_po_file(lang, file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    lang_translations = TRANSLATIONS.get(lang, {})
    
    changed = False
    for msgid, fallback_msgstr in FALLBACKS.items():
        msgstr = lang_translations.get(msgid, fallback_msgstr)
        
        # Check if msgid already exists
        pattern = rf'^msgid "{re.escape(msgid)}"\nmsgstr ".*?"'
        replacement = f'msgid "{msgid}"\nmsgstr "{msgstr}"'
        
        if re.search(pattern, content, re.MULTILINE):
            # Update existing
            new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
            if new_content != content:
                content = new_content
                changed = True
        else:
            # Append new
            content += f'\n\nmsgid "{msgid}"\nmsgstr "{msgstr}"\n'
            changed = True
            
    if changed:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated {file_path}")

def main():
    for lang in os.listdir(LOCALES_DIR):
        po_path = os.path.join(LOCALES_DIR, lang, "LC_MESSAGES", "katrain.po")
        if os.path.exists(po_path):
            update_po_file(lang, po_path)

if __name__ == "__main__":
    main()
