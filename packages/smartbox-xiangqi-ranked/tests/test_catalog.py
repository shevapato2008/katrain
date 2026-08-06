import ast
import inspect
from dataclasses import replace

import pytest

from smartbox_xiangqi_ranked.catalog import (
    ACTIVE_CATALOG_VERSION,
    SUPPORTED_CATALOGS,
    EngineProfile,
    profile_hash,
)


EXPECTED = {
    1: ("新手", 1010, 10_000, None, 128, 180, 130, 0.30, 200, 700, 2.0, False),
    2: ("入门", 1260, 10_000, None, 20, 165, 120, 0.27, 185, 630, 2.0, False),
    3: ("初级", 1510, 16_000, None, 12, 130, 88, 0.20, 150, 500, 1.9, True),
    4: ("中级", 1760, 24_000, None, 10, 105, 70, 0.155, 125, 410, 1.85, True),
    5: ("高级", 1960, 40_000, None, 8, 85, 55, 0.115, 100, 330, 1.75, True),
    6: ("精英", 2160, 60_000, None, 6, 66, 42, 0.085, 80, 260, 1.65, True),
    7: ("大师", 2360, 100_000, None, 4, 50, 31, 0.06, 60, 200, 1.5, True),
    8: ("特级", 2560, 120_000, None, 3, 23, 14, 0.028, 33, 115, 1.35, True),
    9: ("满血", 2900, None, 1200, 1, None, None, 0.0, None, None, 1.0, True),
}
EXPECTED_HASHES = {
    1: "6cd19ce04c5b4e3e8ba68af24710bd4c1b7c68082d78e3552b92452a9e07b593",
    2: "013524bf9f5b7b6033e65058f2894246697853d635329db98885c586e17abb69",
    3: "9ae9c8eae3302c455273143ab7bc19f8d8ba50d50df059941d2fdf6e9ebf2c9a",
    4: "20c877fddcd246d9528be3f59d7c26b7e7174439b82e53142002f7c750b94086",
    5: "cf74d19dc6e4e744ea6fbc773f7da4051466958efeb3052d5cbec664426277db",
    6: "44edac3c5181c8e3a5e57da3c1107f3a5baef37266db370f22589c0436eb8e39",
    7: "10d810515ec1c7cc97db07501244993ef75b434de4736c79677a0afbe9cb4bcc",
    8: "bd753ae518bcbebe89423a00f66a9e851a704d1954cf3c694c6b690cb3cb06d7",
    9: "f8052c3b769b02e7a6a2a4d462069d974653a3effe8c0abee0027da4c3b0235c",
}
R0_EXPECTED_HASHES = {
    1: "6cd19ce04c5b4e3e8ba68af24710bd4c1b7c68082d78e3552b92452a9e07b593",
    2: "013524bf9f5b7b6033e65058f2894246697853d635329db98885c586e17abb69",
    3: "9ae9c8eae3302c455273143ab7bc19f8d8ba50d50df059941d2fdf6e9ebf2c9a",
    4: "20c877fddcd246d9528be3f59d7c26b7e7174439b82e53142002f7c750b94086",
    5: "cf74d19dc6e4e744ea6fbc773f7da4051466958efeb3052d5cbec664426277db",
    6: "44edac3c5181c8e3a5e57da3c1107f3a5baef37266db370f22589c0436eb8e39",
    7: "10d810515ec1c7cc97db07501244993ef75b434de4736c79677a0afbe9cb4bcc",
    8: "4756a3851eaee5cdf2a443c86ffc30618c591e33eda1b14242f1c5cfc70b63b2",
    9: "f8052c3b769b02e7a6a2a4d462069d974653a3effe8c0abee0027da4c3b0235c",
}


def _public_tuple(profile: EngineProfile) -> tuple[object, ...]:
    return (
        profile.name,
        profile.anchor,
        profile.nodes,
        profile.movetime_ms,
        profile.multipv,
        profile.window_cp,
        profile.temp_cp,
        profile.p,
        profile.band_lo,
        profile.band_hi,
        profile.sharp_gain,
        profile.resignation_enabled,
    )


def test_active_catalog_is_the_exact_nine_level_production_snapshot():
    catalog = SUPPORTED_CATALOGS[ACTIVE_CATALOG_VERSION]

    assert ACTIVE_CATALOG_VERSION == catalog.version == "pikafish-r1"
    assert [profile.level for profile in catalog.profiles] == list(range(1, 10))
    assert [profile.anchor for profile in catalog.profiles] == sorted(profile.anchor for profile in catalog.profiles)
    assert {profile.level: _public_tuple(profile) for profile in catalog.profiles} == EXPECTED
    assert {profile.level: profile.profile_hash for profile in catalog.profiles} == EXPECTED_HASHES
    assert all(profile.resignation_score_cp == 500 for profile in catalog.profiles)
    assert all(profile.resignation_move_count == 3 for profile in catalog.profiles)


def test_profiles_and_supported_catalog_snapshots_are_immutable():
    catalog = SUPPORTED_CATALOGS[ACTIVE_CATALOG_VERSION]
    with pytest.raises((AttributeError, TypeError)):
        catalog.profiles[0].nodes = 1
    with pytest.raises(TypeError):
        SUPPORTED_CATALOGS["new"] = catalog


@pytest.mark.parametrize(
    "field,value",
    [
        ("nodes", 10_001),
        ("movetime_ms", 999),
        ("multipv", 127),
        ("window_cp", 181),
        ("temp_cp", 131),
        ("p", 0.31),
        ("band_lo", 201),
        ("band_hi", 701),
        ("sharp_gain", 2.1),
        ("resignation_enabled", True),
        ("resignation_score_cp", 501),
        ("resignation_move_count", 4),
        ("anchor", 1011),
    ],
)
def test_every_search_sampling_and_resignation_field_changes_profile_hash(field, value):
    original = SUPPORTED_CATALOGS[ACTIVE_CATALOG_VERSION].profiles[0]
    changed = replace(original, **{field: value})
    assert profile_hash(changed) != original.profile_hash


def test_profile_hash_binds_the_versioned_move_selector_and_only_move_threshold():
    original = SUPPORTED_CATALOGS[ACTIVE_CATALOG_VERSION].profiles[0]
    assert original.move_selector_version == "xiangqi-strength-v1"
    assert original.only_move_loss_cp == 100
    assert profile_hash(replace(original, move_selector_version="xiangqi-strength-v2")) != original.profile_hash
    assert profile_hash(replace(original, only_move_loss_cp=101)) != original.profile_hash


def test_catalog_retains_a_complete_old_snapshot_for_existing_outbox_events():
    assert "pikafish-r0" in SUPPORTED_CATALOGS
    retained = SUPPORTED_CATALOGS["pikafish-r0"]
    assert len(retained.profiles) == 9
    assert [profile.level for profile in retained.profiles] == list(range(1, 10))
    assert all(profile_hash(profile) == profile.profile_hash for profile in retained.profiles)
    assert retained.profiles[7].nodes == 150_000
    assert retained.profiles[7].profile_hash != SUPPORTED_CATALOGS[ACTIVE_CATALOG_VERSION].profiles[7].profile_hash


def test_r0_is_a_fixed_independent_source_snapshot_not_derived_from_active_profiles():
    import smartbox_xiangqi_ranked.catalog as catalog_module

    retained = SUPPORTED_CATALOGS["pikafish-r0"]
    active = SUPPORTED_CATALOGS[ACTIVE_CATALOG_VERSION]
    assert all(old is not current for old, current in zip(retained.profiles, active.profiles))
    assert {profile.level: profile.profile_hash for profile in retained.profiles} == R0_EXPECTED_HASHES

    tree = ast.parse(inspect.getsource(catalog_module))
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(
            isinstance(target, ast.Name) and target.id == "_R0_PROFILES"
            for target in ([node.target] if isinstance(node, ast.AnnAssign) else node.targets)
        )
    )
    assert "_ACTIVE_PROFILES" not in {node.id for node in ast.walk(assignment) if isinstance(node, ast.Name)}


def test_constructing_a_changed_r1_profile_cannot_change_r0_serialization_or_hashes():
    from smartbox_xiangqi_ranked.catalog import profile_public_config
    from smartbox_xiangqi_ranked.canonical import canonical_json

    retained = SUPPORTED_CATALOGS["pikafish-r0"]
    before = tuple(
        (canonical_json(profile_public_config(profile)), profile.profile_hash) for profile in retained.profiles
    )
    changed_r1 = replace(SUPPORTED_CATALOGS[ACTIVE_CATALOG_VERSION].profiles[0], nodes=999_999)
    assert profile_hash(changed_r1) != EXPECTED_HASHES[1]
    after = tuple(
        (canonical_json(profile_public_config(profile)), profile.profile_hash) for profile in retained.profiles
    )
    assert after == before


def test_catalog_contains_no_runtime_paths_or_secrets():
    forbidden = {"path", "binary", "secret", "token", "password", "api_key"}
    for catalog in SUPPORTED_CATALOGS.values():
        for profile in catalog.profiles:
            assert not any(
                fragment in field.lower() for field in profile.__dataclass_fields__ for fragment in forbidden
            )
