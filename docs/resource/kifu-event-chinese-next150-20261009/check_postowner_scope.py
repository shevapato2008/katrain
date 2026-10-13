"""Small pure drift check for the post-owner frozen album boundary."""

from copy import deepcopy

from capture import post_owner_scope_reasons


def main():
    frozen = {"album_ids": [71],
              "scope_rows": [{"id": 71, "black_rank": "9p", "sgf_sha256": "a" * 64}],
              "scope_sha256": "b" * 64,
              "original_sgf_refs": [{"album_id": 71, "sgf_sha256": "a" * 64}],
              "full_physical_album_sha256": "c" * 64}
    member = {key: deepcopy(frozen[key]) for key in ("album_ids", "scope_rows", "scope_sha256")}
    assert post_owner_scope_reasons(frozen, frozen, member) == []
    changes = (
        ("album_ids", [72]),
        ("scope_rows", [{"id": 71, "black_rank": "8p", "sgf_sha256": "a" * 64}]),
        ("original_sgf_refs", [{"album_id": 71, "sgf_sha256": "d" * 64}]),
        ("full_physical_album_sha256", "e" * 64),
    )
    for key, value in changes:
        current = deepcopy(frozen)
        current[key] = value
        assert post_owner_scope_reasons(current, frozen, member), key
    print("pristine scope accepted; ID, rank/scope, SGF, and physical image drift rejected")


if __name__ == "__main__":
    main()
