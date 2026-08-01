from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lvk_paluworld_server_manager import world_options
from lvk_paluworld_server_manager.world_options import (
    SettingField,
    WorldSaveInfo,
)

# ---------------------------------------------------------------------------
# find_world_saves
# ---------------------------------------------------------------------------


def test_find_world_saves_returns_empty_when_root_missing(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist"
    assert world_options.find_world_saves(missing) == []


def test_find_world_saves_discovers_worlds_with_world_option(tmp_path: Path) -> None:
    world_a = tmp_path / "AAAA"
    world_a.mkdir()
    (world_a / "WorldOption.sav").write_bytes(b"fake")
    (world_a / "Level.sav").write_bytes(b"fake")

    world_b_no_option = tmp_path / "BBBB"
    world_b_no_option.mkdir()
    (world_b_no_option / "Level.sav").write_bytes(b"fake")

    not_a_dir = tmp_path / "not_a_dir.txt"
    not_a_dir.write_text("hello")

    results = world_options.find_world_saves(tmp_path)

    assert [w.world_id for w in results] == ["AAAA"]
    assert results[0].world_option_path == world_a / "WorldOption.sav"
    assert results[0].world_dir == world_a


# ---------------------------------------------------------------------------
# get_setting_value / set_setting_value / validate_setting_value
# ---------------------------------------------------------------------------


def _properties_with(**settings: object) -> dict[str, object]:
    inner: dict[str, object] = {}
    for key, value in settings.items():
        if isinstance(value, str) and key in ("Difficulty", "DeathPenalty"):
            inner[key] = {
                "value": {"type": "Enum", "value": f"EPalDifficulty::{value}"},
                "type": "EnumProperty",
            }
        elif isinstance(value, bool):
            inner[key] = {"value": value, "type": "BoolProperty"}
        else:
            inner[key] = {"value": value, "type": "FloatProperty"}
    return {
        "OptionWorldData": {
            "value": {"Settings": {"value": inner, "type": "StructProperty"}},
            "type": "StructProperty",
        }
    }


def _float_field(key: str = "exp_rate") -> SettingField:
    return next(f for f in world_options.SETTING_FIELDS if f.key == key)


def _enum_field(key: str = "difficulty") -> SettingField:
    return next(f for f in world_options.SETTING_FIELDS if f.key == key)


def _bool_field(key: str = "enable_friendly_fire") -> SettingField:
    return next(f for f in world_options.SETTING_FIELDS if f.key == key)


def test_get_setting_value_returns_none_when_missing() -> None:
    field = _float_field()
    assert world_options.get_setting_value({}, field) is None


def test_get_setting_value_reads_float() -> None:
    field = _float_field("exp_rate")
    properties = _properties_with(ExpRate=2.5)
    assert world_options.get_setting_value(properties, field) == 2.5


def test_get_setting_value_reads_enum_choice() -> None:
    field = _enum_field("difficulty")
    properties = _properties_with(Difficulty="Normal")
    assert world_options.get_setting_value(properties, field) == "Normal"


def test_set_setting_value_updates_float_in_place() -> None:
    field = _float_field("exp_rate")
    properties = _properties_with(ExpRate=1.0)
    world_options.set_setting_value(properties, field, 3.0)
    assert world_options.get_setting_value(properties, field) == 3.0


def test_set_setting_value_updates_enum_preserving_prefix() -> None:
    field = _enum_field("difficulty")
    properties = _properties_with(Difficulty="Normal")
    world_options.set_setting_value(properties, field, "Hard")
    node = properties["OptionWorldData"]["value"]["Settings"]["value"]["Difficulty"]  # type: ignore[index]
    assert node["value"]["value"] == "EPalDifficulty::Hard"


def test_set_setting_value_raises_when_unsupported() -> None:
    field = _float_field("exp_rate")
    with pytest.raises(world_options.ValidationError):
        world_options.set_setting_value({}, field, 1.0)


def test_validate_setting_value_float_range() -> None:
    field = _float_field("exp_rate")
    assert world_options.validate_setting_value(field, "2.5") == 2.5
    with pytest.raises(world_options.ValidationError):
        world_options.validate_setting_value(field, -1.0)


def test_validate_setting_value_int_range() -> None:
    field = next(f for f in world_options.SETTING_FIELDS if f.key == "server_player_max_num")
    assert world_options.validate_setting_value(field, "32") == 32
    with pytest.raises(world_options.ValidationError):
        world_options.validate_setting_value(field, "0")
    with pytest.raises(world_options.ValidationError):
        world_options.validate_setting_value(field, "999")


def test_validate_setting_value_bool_accepts_strings() -> None:
    field = _bool_field()
    assert world_options.validate_setting_value(field, "true") is True
    assert world_options.validate_setting_value(field, "no") is False
    with pytest.raises(world_options.ValidationError):
        world_options.validate_setting_value(field, "maybe")


def test_validate_setting_value_enum_choices() -> None:
    field = _enum_field()
    assert world_options.validate_setting_value(field, "Hard") == "Hard"
    with pytest.raises(world_options.ValidationError):
        world_options.validate_setting_value(field, "Impossible")


def test_apply_settings_applies_all_or_none_on_error() -> None:
    properties = _properties_with(ExpRate=1.0, Difficulty="Normal")
    with pytest.raises(world_options.ValidationError):
        world_options.apply_settings(
            properties, {"exp_rate": 2.0, "difficulty": "NotAChoice"}
        )
    # exp_rate must remain unchanged since the whole batch was rejected.
    assert world_options.get_setting_value(properties, _float_field("exp_rate")) == 1.0


def test_apply_settings_applies_valid_changes() -> None:
    properties = _properties_with(ExpRate=1.0)
    world_options.apply_settings(properties, {"exp_rate": 4.0})
    assert world_options.get_setting_value(properties, _float_field("exp_rate")) == 4.0


def test_get_available_settings_reports_unknown_as_none() -> None:
    properties = _properties_with(ExpRate=1.0)
    available = {
        field.key: value for field, value in world_options.get_available_settings(properties)
    }
    assert available["exp_rate"] == 1.0
    assert available["difficulty"] is None


def test_unknown_json_properties_are_preserved_through_apply_settings() -> None:
    properties = _properties_with(ExpRate=1.0)
    properties["SomeUnknownField"] = {"value": "keep-me", "type": "StrProperty"}
    world_options.apply_settings(properties, {"exp_rate": 5.0})
    assert properties["SomeUnknownField"] == {"value": "keep-me", "type": "StrProperty"}


# ---------------------------------------------------------------------------
# create_world_backup
# ---------------------------------------------------------------------------


def test_create_world_backup_raises_when_world_dir_missing(tmp_path: Path) -> None:
    with pytest.raises(world_options.BackupError):
        world_options.create_world_backup(tmp_path / "missing", tmp_path / "backups")


def test_create_world_backup_creates_zip_with_world_option(tmp_path: Path) -> None:
    world_dir = tmp_path / "world" / "AAAA"
    world_dir.mkdir(parents=True)
    (world_dir / "WorldOption.sav").write_bytes(b"world-option-bytes")
    (world_dir / "Level.sav").write_bytes(b"level-bytes")
    players_dir = world_dir / "Players"
    players_dir.mkdir()
    (players_dir / "0001.sav").write_bytes(b"player-bytes")

    backups_root = tmp_path / "Backups"
    fixed_now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    archive_path = world_options.create_world_backup(world_dir, backups_root, now=lambda: fixed_now)

    assert archive_path.exists()
    assert archive_path.name == "AAAA_20260102_030405.zip"
    with zipfile.ZipFile(archive_path) as zf:
        names = zf.namelist()
    assert any(name.endswith("WorldOption.sav") for name in names)
    assert any(name.endswith("Level.sav") for name in names)
    assert any(name.endswith("0001.sav") for name in names)


def test_create_world_backup_raises_if_archive_missing_world_option(tmp_path: Path) -> None:
    world_dir = tmp_path / "world" / "AAAA"
    world_dir.mkdir(parents=True)
    (world_dir / "Level.sav").write_bytes(b"level-bytes")  # no WorldOption.sav

    backups_root = tmp_path / "Backups"

    with pytest.raises(world_options.BackupError):
        world_options.create_world_backup(world_dir, backups_root)


# ---------------------------------------------------------------------------
# backup_all_world_saves
# ---------------------------------------------------------------------------


def test_backup_all_world_saves_creates_verified_archive_for_every_world(tmp_path: Path) -> None:
    save_games_root = tmp_path / "SaveGames" / "0"
    for world_id in ("AAAA", "BBBB"):
        world_dir = save_games_root / world_id
        world_dir.mkdir(parents=True)
        (world_dir / "WorldOption.sav").write_bytes(f"option-{world_id}".encode())
        (world_dir / "Level.sav").write_bytes(f"level-{world_id}".encode())

    backups_root = save_games_root / "Backups"
    backups_root.mkdir()
    (backups_root / "old-backup.zip").write_bytes(b"do-not-include")
    fixed_now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    archive_path = world_options.backup_all_world_saves(
        save_games_root,
        backups_root,
        is_server_running=lambda: False,
        now=lambda: fixed_now,
    )

    assert archive_path.name == "savegames_20260102_030405.zip"
    with zipfile.ZipFile(archive_path) as zf:
        names = zf.namelist()
    assert "AAAA/WorldOption.sav" in names
    assert "AAAA/Level.sav" in names
    assert "BBBB/WorldOption.sav" in names
    assert "BBBB/Level.sav" in names
    assert not any(name.startswith("Backups/") for name in names)


def test_backup_all_world_saves_refuses_while_server_running(tmp_path: Path) -> None:
    save_games_root = tmp_path / "SaveGames" / "0"
    world_dir = save_games_root / "AAAA"
    world_dir.mkdir(parents=True)
    (world_dir / "WorldOption.sav").write_bytes(b"option")
    backups_root = save_games_root / "Backups"

    with pytest.raises(world_options.ServerRunningError):
        world_options.backup_all_world_saves(
            save_games_root, backups_root, is_server_running=lambda: True
        )

    assert not backups_root.exists()


def test_backup_all_world_saves_raises_when_no_worlds_found(tmp_path: Path) -> None:
    save_games_root = tmp_path / "SaveGames" / "0"
    save_games_root.mkdir(parents=True)

    with pytest.raises(world_options.BackupError, match="No world saves found"):
        world_options.backup_all_world_saves(
            save_games_root,
            save_games_root / "Backups",
            is_server_running=lambda: False,
        )


# ---------------------------------------------------------------------------
# list_backup_archives
# ---------------------------------------------------------------------------


def test_list_backup_archives_verifies_and_sorts_zip_files(tmp_path: Path) -> None:
    save_games_root = tmp_path / "SaveGames" / "0"
    backups_root = save_games_root / "Backups"
    backups_root.mkdir(parents=True)
    older = backups_root / "savegames_20260102_030405.zip"
    newer = backups_root / "savegames_20260103_040506.zip"
    invalid = backups_root / "savegames_20260101_020304.zip"
    (backups_root / "notes.txt").write_text("ignore")
    for archive_path in (older, newer):
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("AAAA/WorldOption.sav", b"world options")
    with zipfile.ZipFile(invalid, "w") as archive:
        archive.writestr("README.txt", b"not a world archive")

    archives = world_options.list_backup_archives(save_games_root)

    assert [archive.path.name for archive in archives] == [newer.name, older.name, invalid.name]
    assert archives[0].created_at == datetime(2026, 1, 3, 4, 5, 6)
    assert archives[0].verified is True
    assert archives[2].verified is False
    assert archives[2].error == "Missing WorldOption.sav"


def test_list_backup_archives_marks_corrupt_zip_invalid(tmp_path: Path) -> None:
    save_games_root = tmp_path / "SaveGames" / "0"
    backups_root = save_games_root / "Backups"
    backups_root.mkdir(parents=True)
    corrupt = backups_root / "savegames_20260102_030405.zip"
    corrupt.write_bytes(b"not a zip")

    archives = world_options.list_backup_archives(save_games_root)

    assert len(archives) == 1
    assert archives[0].verified is False
    assert archives[0].error


# ---------------------------------------------------------------------------
# save_world_options
# ---------------------------------------------------------------------------


def _fake_world(tmp_path: Path) -> WorldSaveInfo:
    world_dir = tmp_path / "SaveGames" / "0" / "AAAA"
    world_dir.mkdir(parents=True)
    world_option_path = world_dir / "WorldOption.sav"
    world_option_path.write_bytes(b"original-bytes")
    return WorldSaveInfo(
        world_id="AAAA", world_option_path=world_option_path, world_dir=world_dir
    )


def test_save_world_options_refuses_when_server_running(tmp_path: Path) -> None:
    world = _fake_world(tmp_path)
    gvas_file = MagicMock()
    gvas_file.properties = _properties_with(ExpRate=1.0)

    with pytest.raises(world_options.ServerRunningError):
        world_options.save_world_options(
            world,
            gvas_file,
            0x31,
            {"exp_rate": 2.0},
            tmp_path / "Backups",
            is_server_running=lambda: True,
        )

    # Original file must remain untouched.
    assert world.world_option_path.read_bytes() == b"original-bytes"


def test_save_world_options_full_flow(tmp_path: Path) -> None:
    world = _fake_world(tmp_path)
    gvas_file = MagicMock()
    gvas_file.properties = _properties_with(ExpRate=1.0)

    encoded_bytes = b"new-encoded-bytes"

    with (
        patch.object(world_options, "encode_gvas", return_value=encoded_bytes) as mock_encode,
        patch.object(
            world_options,
            "decode_sav_bytes",
            return_value=(MagicMock(), 0x31),
        ) as mock_decode,
    ):
        result = world_options.save_world_options(
            world,
            gvas_file,
            0x31,
            {"exp_rate": 9.0},
            tmp_path / "Backups",
            is_server_running=lambda: False,
        )

    assert result.sav_path == world.world_option_path
    assert result.backup_path.exists()
    assert world.world_option_path.read_bytes() == encoded_bytes
    assert not world.world_option_path.with_name("WorldOption.sav.tmp").exists()
    mock_encode.assert_called_once()
    mock_decode.assert_called_once_with(encoded_bytes)


def test_save_world_options_rejects_invalid_changes_without_writing(tmp_path: Path) -> None:
    world = _fake_world(tmp_path)
    gvas_file = MagicMock()
    gvas_file.properties = _properties_with(ExpRate=1.0)

    with pytest.raises(world_options.ValidationError):
        world_options.save_world_options(
            world,
            gvas_file,
            0x31,
            {"exp_rate": -5.0},
            tmp_path / "Backups",
            is_server_running=lambda: False,
        )

    assert world.world_option_path.read_bytes() == b"original-bytes"


def test_save_world_options_restores_properties_on_encode_failure(tmp_path: Path) -> None:
    world = _fake_world(tmp_path)
    gvas_file = MagicMock()
    original_properties = _properties_with(ExpRate=1.0)
    gvas_file.properties = original_properties

    with patch.object(
        world_options, "encode_gvas", side_effect=world_options.SaveEncodeError("boom")
    ), pytest.raises(world_options.SaveEncodeError):
        world_options.save_world_options(
            world,
            gvas_file,
            0x31,
            {"exp_rate": 9.0},
            tmp_path / "Backups",
            is_server_running=lambda: False,
        )

    # The original file is untouched and the in-memory properties were
    # restored to their pre-edit state.
    assert world.world_option_path.read_bytes() == b"original-bytes"
    assert gvas_file.properties is original_properties
