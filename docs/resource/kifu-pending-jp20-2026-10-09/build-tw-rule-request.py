"""Freeze four finite TW codepoint mappings for 安东阳向 → 安東陽向."""

import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from katrain.web.kifu.name_orthographic import EXCLUDED_CHARACTERS, EXCLUDED_NAMES, VERSION


DIRECTORY = Path(__file__).parent
UNIHAN_ZIP = Path("/tmp/kifu-tw20-Unihan-17.0.0.zip")
UNIHAN_URL = "https://www.unicode.org/Public/17.0.0/ucd/Unihan.zip"
UNIHAN_SHA256 = "f7a48b2b545acfaa77b2d607ae28747404ce02baefee16396c5d2d7a8ef34b5e"
MOE_PDF = Path("/tmp/kifu-tw20-moe-strokes.pdf")
MOE_TEXT = Path("/tmp/kifu-tw20-moe-strokes.txt")
MOE_URL = ("https://ws.moe.edu.tw/001/Upload/userfiles/"
           "%E9%99%84%E8%A1%A8-%E7%B0%A1%E5%8C%96%E5%AD%97%E5%B0%8D%E7%85%A7"
           "%E6%A8%99%E6%BA%96%E5%AD%97-%E7%AD%86%E7%95%AB%E5%BA%8F.pdf")
MOE_SHA256 = "5e7173d5aa11064d3d5662d5ce4723626f2b4d2122da264f7d63e946a5815434"


def main():
    archive = UNIHAN_ZIP.read_bytes()
    assert hashlib.sha256(archive).hexdigest() == UNIHAN_SHA256
    assert hashlib.sha256(MOE_PDF.read_bytes()).hexdigest() == MOE_SHA256
    moe_pages = MOE_TEXT.read_text().split("\f")
    rows = json.loads((DIRECTORY / "unsigned-manifest.json").read_text())["rows"]
    pairs = {}
    examples = {}
    for row in rows:
        if row["environment"] != "PROD" or row["target_language"] != "tw":
            continue
        original, target = row["cn_display"], row["candidate_tw_display"]
        assert len(original) == len(target)
        assert original not in EXCLUDED_NAMES
        assert not set(original + target) & EXCLUDED_CHARACTERS
        for index, (source, output) in enumerate(zip(original, target)):
            assert source not in pairs or pairs[source] == output
            pairs[source] = output
            examples.setdefault(source, []).append({"player_id": row["player_id"], "position": index})
    with zipfile.ZipFile(UNIHAN_ZIP) as zipped:
        lines = zipped.read("Unihan_Variants.txt").decode("utf-8").splitlines()
    variants = {}
    for line in lines:
        if not line or line.startswith("#"):
            continue
        point, property_name, value = line.split("\t")
        if property_name == "kTraditionalVariant":
            variants[chr(int(point[2:], 16))] = line
    scoped, mappings = [], []
    moe_locators = []
    for source, output in sorted(pairs.items(), key=lambda pair: ord(pair[0])):
        point = f"U+{ord(source):04X}"
        line = variants.get(source)
        if line is not None:
            assert f"U+{ord(output):04X}" in line.split("\t")[2].split()
            location = f"Unihan_Variants.txt: {point} kTraditionalVariant"
        else:
            assert source == output
            location = f"Unihan_Variants.txt: {point} has no kTraditionalVariant record"
        moe_match = None
        if source != output:
            pattern = re.compile(re.escape(source) + r"\s*－\s*" + re.escape(output))
            matches = [(number, text.strip()) for number, page in enumerate(moe_pages, 1)
                       for text in page.splitlines() if pattern.search(text)]
            assert len(matches) == 1, (source, output, matches)
            page, text = matches[0]
            moe_match = {"input": source, "output": output, "pdf_page": page,
                         "extracted_line": text}
            moe_locators.append(moe_match)
            normative_version = "臺灣教育部《簡化字對照標準字表》筆畫序"
            normative_url = MOE_URL
            location = f"PDF physical page {page}: {source}－{output}"
        else:
            normative_version = "Unicode 17.0.0 Unihan_Variants.txt"
            normative_url = UNIHAN_URL
        scoped.append({"input": source, "output": output, "unihan_line": line,
                       "moe_locator": moe_match, "examples": examples[source]})
        mappings.append({
            "input": source, "output": output,
            "normative_version": normative_version,
            "normative_url": normative_url,
            "location": location,
            # This is a proposed *finite-name* reviewer assertion, not a
            # conclusion from Unihan alone. The rule remains unsigned.
            "human_name_applicable": True,
        })
    assert len(mappings) == 4
    assert sum(row["input"] != row["output"] for row in mappings) == 2
    evidence = {
        "source_url": UNIHAN_URL, "source_sha256": UNIHAN_SHA256,
        "source_file": "Unihan_Variants.txt", "normative_version": "Unicode 17.0.0",
        "moe_source_url": MOE_URL, "moe_source_sha256": MOE_SHA256,
        "moe_title": "臺灣教育部《簡化字對照標準字表》筆畫序",
        "moe_changed_mapping_locators": moe_locators,
        "scoped_characters": scoped,
    }
    content = {
        "version": VERSION, "lang": "tw", "source_lang": "zh-Hans",
        "source_script": "Hans", "target_script": "Hant", "target_region": "TW",
        "mappings": mappings,
        "excluded_characters": sorted(EXCLUDED_CHARACTERS),
        "excluded_names": sorted(EXCLUDED_NAMES),
        "exceptions_checked": True,
    }
    (DIRECTORY / "Unicode-17.0-scoped-variants.json").write_text(
        json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    from katrain.web.kifu.name_evidence import registry_sha256
    request = {
        "status": "pending_independent_rule_approval", "content": content,
        "production": {
            "producer_id": "/root/next_batch_source_recovery",
            "producer_model": "GPT-6 (exact runtime variant unavailable)",
            "produced_at": datetime.now(timezone.utc).isoformat(),
            "content_sha256": registry_sha256(content),
        },
    }
    (DIRECTORY / "unsigned-tw-rule-request.json").write_text(
        json.dumps(request,
                   ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    print("finite mappings", len(mappings), "changed", len(moe_locators),
          "content sha256", request["production"]["content_sha256"])


if __name__ == "__main__":
    main()
