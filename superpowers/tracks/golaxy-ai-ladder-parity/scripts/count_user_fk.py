#!/usr/bin/env python3
"""Count FK references to katrain's `users` table at any git ref.

Exists because the Phase 1 freeze doc (superpowers/shared/identity-vocabulary-freeze-2026-08-10.md)
cites a FK count that downstream tracks cannot reproduce: its generator
`identity-contract-matrix.py` is not part of the synced file set, and the freeze doc's
§7-3 count ("three tables") is an undercount.

The point of this script is that the number is *checkable at a ref*, so a reviewer never has
to trust a line number that has drifted. Line numbers move; the count and the table list do not.

Usage:
    python3 count_user_fk.py                 # working tree
    python3 count_user_fk.py 73ba868f        # the pin the freeze doc was written against
    python3 count_user_fk.py 73ba868f HEAD   # compare two refs

Exit status is always 0; this is a reporting tool, not a gate.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import OrderedDict

MODELS = "katrain/web/core/models_db.py"

TABLENAME_RE = re.compile(r"""__tablename__\s*=\s*["'](\w+)["']""")
COLUMN_RE = re.compile(r"^\s*(\w+)\s*=")
# Both the users.id row-ref FK and the users.uuid account-subject FK matter, for opposite reasons.
FK_RE = re.compile(r"""ForeignKey\(\s*["']users\.(id|uuid)["']""")

# Tables whose rows represent money. Losing their FK target is an accounting failure,
# not a gameplay failure -- this is why "preserve id" is a platform constraint and not a Go one.
BILLING = {"credit_transactions", "redeem_codes", "recharge_orders"}


def source_at(ref: str | None) -> str:
    if ref is None:
        with open(MODELS, encoding="utf-8") as fh:
            return fh.read()
    out = subprocess.run(["git", "show", f"{ref}:{MODELS}"], capture_output=True, text=True, check=False)
    if out.returncode != 0:
        sys.exit(f"cannot read {MODELS} at {ref}: {out.stderr.strip()}")
    return out.stdout


def scan(text: str) -> "OrderedDict[str, list[tuple[str, str, int]]]":
    """-> {table: [(column, target, line), ...]} in file order."""
    found: "OrderedDict[str, list[tuple[str, str, int]]]" = OrderedDict()
    table = None
    for lineno, line in enumerate(text.splitlines(), 1):
        name = TABLENAME_RE.search(line)
        if name:
            table = name.group(1)
        hit = FK_RE.search(line)
        if hit and table:
            col = COLUMN_RE.match(line)
            found.setdefault(table, []).append((col.group(1) if col else "?", hit.group(1), lineno))
    return found


def report(ref: str | None) -> "OrderedDict[str, list[tuple[str, str, int]]]":
    label = ref or "working tree"
    found = scan(source_at(ref))
    by_id = [(t, c, ln) for t, cols in found.items() for c, tgt, ln in cols if tgt == "id"]
    by_uuid = [(t, c, ln) for t, cols in found.items() for c, tgt, ln in cols if tgt == "uuid"]
    id_tables = {t for t, _, _ in by_id}

    print(f"\n=== {label} ===")
    print(f"FK -> users.id   : {len(by_id):>2} columns across {len(id_tables)} tables  (account_row_ref)")
    print(f"FK -> users.uuid : {len(by_uuid):>2} columns                        (account_subject)")
    print()
    for table, cols in found.items():
        for col, target, lineno in cols:
            mark = "  <-- BILLING" if table in BILLING else ""
            print(f"  users.{target:<4} <- {table:<32} {col:<15} :{lineno}{mark}")

    hit_billing = sorted(id_tables & BILLING)
    if hit_billing:
        print(f"\n  billing tables keyed on users.id: {', '.join(hit_billing)}")
        print("  => re-minting users.id during the Phase 3 account copy corrupts the credit ledger.")
    return found


def main() -> None:
    refs: list[str | None] = list(sys.argv[1:]) or [None]
    results = [(r, report(r)) for r in refs]

    if len(results) == 2:
        (ref_a, a), (ref_b, b) = results
        only_a = sorted(set(a) - set(b))
        only_b = sorted(set(b) - set(a))
        print(f"\n=== {ref_a or 'working tree'}  vs  {ref_b or 'working tree'} ===")
        print(f"  only in {ref_a or 'working tree'}: {', '.join(only_a) or '(none)'}")
        print(f"  only in {ref_b or 'working tree'}: {', '.join(only_b) or '(none)'}")
        print("\n  NOTE: a table present on one ref and not the other shifts every line number")
        print("  below it. Line-number offsets between refs are step changes, not uniform drift.")


if __name__ == "__main__":
    main()
