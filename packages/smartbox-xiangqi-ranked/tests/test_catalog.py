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
    1: "0eda775901eb617a0d09b805329d3a4c9c177f9b76faeaadaaec46c9c2bea9ca",
    2: "57c528bd3c3b39acccb78beac47777ee87285fccae495b14869d08eb858ae37e",
    3: "e0eb5605101c7968a6721215399c04244da98d6a10ca8e473f67db0ed646b6a2",
    4: "48a1792fd784400a2ebf24c9d169d719b7193bc5a164313db327a5f2cb8b181f",
    5: "41c26646b6182b2d87538b26c84fdc0ae219c7b66bef28cb6b4c55b716a2dcba",
    6: "2954aa6aaa48de0243138fb3536e28ba8c682c5427f6cbfffdb2078690378916",
    7: "ddd0ead289e8169874238fbb762d0698b7fbaa40ad401c658541c132af879d39",
    8: "cbe47980b2dcb414ec397af38408ec8b02219a0210c67c7658cafe2c58d72685",
    9: "bbdcd8f399bd4481c96d0bfc665db56ae3ea574d25ec8b20ed013bf9695cee17",
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


def test_catalog_retains_a_complete_old_snapshot_for_existing_outbox_events():
    assert "pikafish-r0" in SUPPORTED_CATALOGS
    retained = SUPPORTED_CATALOGS["pikafish-r0"]
    assert len(retained.profiles) == 9
    assert [profile.level for profile in retained.profiles] == list(range(1, 10))
    assert all(profile_hash(profile) == profile.profile_hash for profile in retained.profiles)
    assert retained.profiles[7].nodes == 150_000
    assert retained.profiles[7].profile_hash != SUPPORTED_CATALOGS[ACTIVE_CATALOG_VERSION].profiles[7].profile_hash


def test_catalog_contains_no_runtime_paths_or_secrets():
    forbidden = {"path", "binary", "secret", "token", "password", "api_key"}
    for catalog in SUPPORTED_CATALOGS.values():
        for profile in catalog.profiles:
            assert not any(
                fragment in field.lower() for field in profile.__dataclass_fields__ for fragment in forbidden
            )
