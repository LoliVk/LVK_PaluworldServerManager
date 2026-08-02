"""Backend for discovering, inspecting, and safely editing ``WorldOption.sav``.

This module isolates all GVAS/JSON conversion logic (via
``palworld-save-tools``) from the Tkinter GUI so it can be unit tested
without a display and so decode/encode failures are surfaced as typed
exceptions the GUI can present to the user in Chinese/English.

Design constraints (see project decisions):

* Never guess at a world to edit — callers must discover worlds via
  :func:`find_world_saves` and let the user choose.
* Never write while the dedicated server is running — enforced in
  :func:`save_world_options` via the caller-supplied ``is_server_running``
  check, re-verified immediately before any mutation.
* Always create a full, verified backup of the *entire* selected world
  directory (not just ``WorldOption.sav``) before touching the real file.
* Missing/unsupported fields are reported as unavailable (``None``)
  rather than inventing default values.
"""

from __future__ import annotations

import copy
import json
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.json_tools import CustomEncoder
from palworld_save_tools.palsav import compress_gvas_to_sav, decompress_sav_to_gvas
from palworld_save_tools.paltypes import (
    DISABLED_PROPERTIES,
    PALWORLD_CUSTOM_PROPERTIES,
    PALWORLD_TYPE_HINTS,
)

#: Filename of the world-settings save file inside a world's save directory.
WORLD_OPTION_FILENAME = "WorldOption.sav"

#: Current Palworld servers persist the world state in ``Level.sav`` even
#: when ``WorldOption.sav`` is absent.
LEVEL_SAVE_FILENAME = "Level.sav"
_BACKUP_WORLD_SAVE_FILENAMES = (WORLD_OPTION_FILENAME, LEVEL_SAVE_FILENAME)

_BACKUP_ARCHIVE_TIMESTAMP = re.compile(r"^savegames_(\d{8}_\d{6})$")

#: Custom property decoders, excluding paths known to be broken/disabled.
#: ``WorldOption.sav`` does not contain any of these (they are Level.sav
#: constructs), but excluding them defensively avoids surprises if the
#: save format changes.
_ACTIVE_CUSTOM_PROPERTIES = {
    path: codec
    for path, codec in PALWORLD_CUSTOM_PROPERTIES.items()
    if path not in DISABLED_PROPERTIES
}


class WorldOptionsError(Exception):
    """Base class for all world-option editor errors."""


class ServerRunningError(WorldOptionsError):
    """Raised when a save/write is attempted while PalServer is running."""


class SaveDecodeError(WorldOptionsError):
    """Raised when a save file cannot be decoded/parsed."""


class SaveEncodeError(WorldOptionsError):
    """Raised when a document cannot be safely re-encoded and verified."""


class BackupError(WorldOptionsError):
    """Raised when the pre-write backup archive could not be created/verified."""


class ValidationError(WorldOptionsError):
    """Raised when one or more edited setting values fail validation."""

    def __init__(self, errors: dict[str, str]) -> None:
        self.errors = errors
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))


@dataclass(frozen=True)
class WorldSaveInfo:
    """A discovered dedicated-server world save directory."""

    world_id: str
    world_option_path: Path
    world_dir: Path


@dataclass(frozen=True)
class BackupArchive:
    """A read-only summary of one archive in the shared backups directory."""

    path: Path
    created_at: datetime
    size_bytes: int
    verified: bool
    error: str | None = None


@dataclass(frozen=True)
class BackupWorldInfo:
    """Read-only summary of one world available for a manual backup."""

    world_id: str
    path: Path
    modified_at: datetime
    size_bytes: int


@dataclass(frozen=True)
class SettingField:
    """Describes one editable ``WorldOption`` setting exposed in the UI."""

    key: str
    label: str
    group: str
    kind: str  # "int" | "float" | "bool" | "enum"
    property_path: tuple[str, ...]
    enum_choices: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None


# Ordered, path-based descriptors for the first-wave editable settings.
# ``property_path`` walks the decoded GVAS ``properties`` dict, following
# the ``{"value": ...}`` / StructProperty nesting used by
# ``palworld-save-tools``. If a path is absent in a given save, the field
# is reported as unavailable rather than guessing a default.
_SETTINGS_ROOT: tuple[str, ...] = ("OptionWorldData", "value", "Settings", "value")

SETTING_FIELDS: tuple[SettingField, ...] = (
    SettingField(
        "difficulty",
        "難度 / Difficulty",
        "難度與死亡懲罰",
        "enum",
        (*_SETTINGS_ROOT, "Difficulty"),
        enum_choices=("None", "Casual", "Normal", "Hard", "Custom"),
    ),
    SettingField(
        "death_penalty",
        "死亡懲罰 / DeathPenalty",
        "難度與死亡懲罰",
        "enum",
        (*_SETTINGS_ROOT, "DeathPenalty"),
        enum_choices=("None", "Item", "ItemAndEquipment", "All"),
    ),
    SettingField(
        "day_time_speed_rate",
        "白天速度倍率 / DayTimeSpeedRate",
        "時間與經驗倍率",
        "float",
        (*_SETTINGS_ROOT, "DayTimeSpeedRate"),
        minimum=0.0,
    ),
    SettingField(
        "night_time_speed_rate",
        "夜晚速度倍率 / NightTimeSpeedRate",
        "時間與經驗倍率",
        "float",
        (*_SETTINGS_ROOT, "NightTimeSpeedRate"),
        minimum=0.0,
    ),
    SettingField(
        "exp_rate",
        "經驗倍率 / ExpRate",
        "時間與經驗倍率",
        "float",
        (*_SETTINGS_ROOT, "ExpRate"),
        minimum=0.0,
    ),
    SettingField(
        "pal_capture_rate",
        "捕獲倍率 / PalCaptureRate",
        "遊戲世界倍率",
        "float",
        (*_SETTINGS_ROOT, "PalCaptureRate"),
        minimum=0.0,
    ),
    SettingField(
        "pal_spawn_num_rate",
        "Pal 出現倍率 / PalSpawnNumRate",
        "遊戲世界倍率",
        "float",
        (*_SETTINGS_ROOT, "PalSpawnNumRate"),
        minimum=0.0,
    ),
    SettingField(
        "drop_item_max_num_rate",
        "掉落物倍率 / DropItemMaxNumRate",
        "遊戲世界倍率",
        "float",
        (*_SETTINGS_ROOT, "DropItemMaxNumRate"),
        minimum=0.0,
    ),
    SettingField(
        "collection_drop_rate",
        "採集掉落倍率 / CollectionDropRate",
        "遊戲世界倍率",
        "float",
        (*_SETTINGS_ROOT, "CollectionDropRate"),
        minimum=0.0,
    ),
    SettingField(
        "player_damage_rate_attack",
        "玩家攻擊倍率 / PlayerDamageRateAttack",
        "玩家與 Pal 倍率",
        "float",
        (*_SETTINGS_ROOT, "PlayerDamageRateAttack"),
        minimum=0.0,
    ),
    SettingField(
        "player_damage_rate_defense",
        "玩家防禦倍率 / PlayerDamageRateDefense",
        "玩家與 Pal 倍率",
        "float",
        (*_SETTINGS_ROOT, "PlayerDamageRateDefense"),
        minimum=0.0,
    ),
    SettingField(
        "pal_damage_rate_attack",
        "Pal 攻擊倍率 / PalDamageRateAttack",
        "玩家與 Pal 倍率",
        "float",
        (*_SETTINGS_ROOT, "PalDamageRateAttack"),
        minimum=0.0,
    ),
    SettingField(
        "pal_damage_rate_defense",
        "Pal 防禦倍率 / PalDamageRateDefense",
        "玩家與 Pal 倍率",
        "float",
        (*_SETTINGS_ROOT, "PalDamageRateDefense"),
        minimum=0.0,
    ),
    SettingField(
        "pal_stomach_decrease_rate",
        "Pal 飢餓速度倍率 / PalStomachDecreaceRate",
        "玩家與 Pal 倍率",
        "float",
        (*_SETTINGS_ROOT, "PalStomachDecreaceRate"),
        minimum=0.0,
    ),
    SettingField(
        "server_player_max_num",
        "最大玩家數 / ServerPlayerMaxNum",
        "伺服器規則",
        "int",
        (*_SETTINGS_ROOT, "ServerPlayerMaxNum"),
        minimum=1,
        maximum=128,
    ),
    SettingField(
        "enable_player_to_player_damage",
        "玩家間傷害 / bEnablePlayerToPlayerDamage",
        "伺服器規則",
        "bool",
        (*_SETTINGS_ROOT, "bEnablePlayerToPlayerDamage"),
    ),
    SettingField(
        "enable_friendly_fire",
        "友軍傷害 / bEnableFriendlyFire",
        "伺服器規則",
        "bool",
        (*_SETTINGS_ROOT, "bEnableFriendlyFire"),
    ),
)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def find_world_saves(save_games_root: Path) -> list[WorldSaveInfo]:
    """Scan a ``SaveGames/0``-style directory for worlds with ``WorldOption.sav``.

    Args:
        save_games_root: Windows-visible path to the dedicated server's
            ``Pal/Saved/SaveGames/0`` directory (e.g. via a ``\\\\wsl$`` UNC
            path).

    Returns:
        Discovered worlds sorted by directory name. Empty if the root does
        not exist or contains no matching worlds.
    """
    results: list[WorldSaveInfo] = []
    if not save_games_root.is_dir():
        return results
    for child in sorted(save_games_root.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        candidate = child / WORLD_OPTION_FILENAME
        if candidate.is_file():
            results.append(
                WorldSaveInfo(world_id=child.name, world_option_path=candidate, world_dir=child)
            )
    return results


def find_world_backup_directories(save_games_root: Path) -> list[Path]:
    """Return world directories supported by the verified backup workflow.

    ``WorldOption.sav`` identifies legacy worlds, while current Palworld
    servers may contain only ``Level.sav``. The settings editor deliberately
    remains limited to worlds that have ``WorldOption.sav``.
    """
    if not save_games_root.is_dir():
        return []
    return [
        child
        for child in sorted(save_games_root.iterdir(), key=lambda path: path.name)
        if child.is_dir()
        and any((child / filename).is_file() for filename in _BACKUP_WORLD_SAVE_FILENAMES)
    ]


def list_backup_worlds(save_games_root: Path) -> list[BackupWorldInfo]:
    """Return selectable worlds with their current size and modification time.

    The game's own rolling ``backup`` directory is deliberately omitted from
    the reported size because it is not included in manual ZIP snapshots.
    """
    worlds: list[BackupWorldInfo] = []
    for world_dir in find_world_backup_directories(save_games_root):
        size_bytes = 0
        modified_at = datetime.fromtimestamp(0)
        try:
            for file_path in world_dir.rglob("*"):
                if not file_path.is_file() or world_dir / "backup" in file_path.parents:
                    continue
                stat = file_path.stat()
                size_bytes += stat.st_size
                modified_at = max(modified_at, datetime.fromtimestamp(stat.st_mtime))
        except OSError as exc:
            raise BackupError(f"Unable to inspect world save {world_dir.name}: {exc}") from exc
        worlds.append(
            BackupWorldInfo(
                world_id=world_dir.name,
                path=world_dir,
                modified_at=modified_at,
                size_bytes=size_bytes,
            )
        )
    return worlds


# ---------------------------------------------------------------------------
# Decode / encode
# ---------------------------------------------------------------------------


def decode_sav_bytes(data: bytes) -> tuple[GvasFile, int]:
    """Decompress and parse raw ``.sav`` bytes into a :class:`GvasFile`.

    Returns:
        A tuple of ``(gvas_file, save_type)`` where ``save_type`` must be
        passed back into :func:`encode_gvas` to reproduce the correct
        compression scheme.

    Raises:
        SaveDecodeError: If the bytes cannot be decompressed or parsed.
    """
    try:
        raw_gvas, save_type = decompress_sav_to_gvas(data)
    except Exception as exc:
        raise SaveDecodeError(f"無法解壓縮存檔 / Failed to decompress save: {exc}") from exc
    try:
        gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, _ACTIVE_CUSTOM_PROPERTIES)
    except Exception as exc:
        raise SaveDecodeError(f"無法解析存檔內容 / Failed to parse save: {exc}") from exc
    return gvas_file, save_type


def encode_gvas(gvas_file: GvasFile, save_type: int) -> bytes:
    """Re-encode a :class:`GvasFile` back into compressed ``.sav`` bytes.

    Raises:
        SaveEncodeError: If encoding or compression fails.
    """
    try:
        raw = gvas_file.write(_ACTIVE_CUSTOM_PROPERTIES)
        return compress_gvas_to_sav(raw, save_type)
    except Exception as exc:
        raise SaveEncodeError(f"無法重新編碼存檔 / Failed to encode save: {exc}") from exc


def dump_gvas_json(gvas_file: GvasFile) -> str:
    """Return a pretty-printed, read-only JSON view of the decoded document."""
    return json.dumps(gvas_file.dump(), indent=2, cls=CustomEncoder, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Field access
# ---------------------------------------------------------------------------


def _walk(node: Any, path: tuple[str, ...]) -> Any | None:
    """Walk a nested dict by *path*, returning ``None`` if any key is missing."""
    current = node
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def get_setting_value(properties: dict[str, Any], field: SettingField) -> Any | None:
    """Return the current value of *field* from decoded *properties*.

    Returns ``None`` if the field is missing or has an unexpected shape,
    signalling to the UI that it is unavailable for this save rather than
    guessing a default.
    """
    node = _walk(properties, field.property_path)
    if not isinstance(node, dict) or "value" not in node:
        return None
    value = node["value"]
    if field.kind == "enum":
        if isinstance(value, dict) and isinstance(value.get("value"), str):
            choice = value["value"].rsplit("::", 1)[-1]
            return choice if choice in field.enum_choices else None
        return None
    if field.kind == "bool":
        return bool(value) if isinstance(value, bool) else None
    if field.kind in ("int", "float"):
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    return None


def set_setting_value(properties: dict[str, Any], field: SettingField, new_value: Any) -> None:
    """Mutate *properties* in place, applying *new_value* to *field*.

    Raises:
        ValidationError: If *field* is unsupported by this save (missing or
            an unexpected shape).
    """
    node = _walk(properties, field.property_path)
    if not isinstance(node, dict) or "value" not in node:
        raise ValidationError({field.key: "此存檔不支援此欄位 / Field not supported by this save"})

    if field.kind == "enum":
        current = node["value"]
        if not (isinstance(current, dict) and isinstance(current.get("value"), str)):
            raise ValidationError(
                {field.key: "此存檔不支援此欄位 / Field not supported by this save"}
            )
        prefix = current["value"].rsplit("::", 1)[0]
        current["value"] = f"{prefix}::{new_value}"
        return

    node["value"] = new_value


def get_available_settings(
    properties: dict[str, Any],
) -> list[tuple[SettingField, Any | None]]:
    """Return every known setting field paired with its current value (or ``None``)."""
    return [(field, get_setting_value(properties, field)) for field in SETTING_FIELDS]


def validate_setting_value(field: SettingField, raw_value: Any) -> Any:
    """Validate and coerce *raw_value* for *field*, raising :class:`ValidationError`."""
    if field.kind == "bool":
        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, str):
            lowered = raw_value.strip().lower()
            if lowered in ("1", "true", "yes", "on"):
                return True
            if lowered in ("0", "false", "no", "off"):
                return False
        raise ValidationError({field.key: "必須為布林值 / Must be a boolean"})

    if field.kind in ("int", "float"):
        try:
            number: float = int(raw_value) if field.kind == "int" else float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValidationError({field.key: "必須為數字 / Must be a number"}) from exc
        if field.minimum is not None and number < field.minimum:
            raise ValidationError({field.key: f"不可小於 {field.minimum} / Must be >= {field.minimum}"})
        if field.maximum is not None and number > field.maximum:
            raise ValidationError({field.key: f"不可大於 {field.maximum} / Must be <= {field.maximum}"})
        return number

    if field.kind == "enum":
        if raw_value not in field.enum_choices:
            choices = ", ".join(field.enum_choices)
            raise ValidationError({field.key: f"必須為以下其中之一 / Must be one of: {choices}"})
        return raw_value

    raise ValidationError({field.key: "不支援的欄位類型 / Unsupported field type"})


def apply_settings(properties: dict[str, Any], changes: dict[str, Any]) -> None:
    """Validate and apply *changes* (by field key) to *properties* in place.

    All changes are validated before any mutation occurs; if any change is
    invalid, :class:`ValidationError` is raised with every failure collected
    and nothing is mutated.
    """
    fields_by_key = {field.key: field for field in SETTING_FIELDS}
    errors: dict[str, str] = {}
    validated: list[tuple[SettingField, Any]] = []

    for key, raw_value in changes.items():
        field = fields_by_key.get(key)
        if field is None:
            errors[key] = "未知欄位 / Unknown field"
            continue
        try:
            validated.append((field, validate_setting_value(field, raw_value)))
        except ValidationError as exc:
            errors.update(exc.errors)

    if errors:
        raise ValidationError(errors)

    for field, value in validated:
        set_setting_value(properties, field, value)


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------


def list_backup_archives(save_games_root: Path) -> list[BackupArchive]:
    """Return verified ZIP archives found directly under ``Backups``.

    This intentionally performs no cleanup or repair.  It is suitable for a
    background UI worker because each archive is fully tested before being
    labelled as verified.
    """
    backups_root = save_games_root / "Backups"
    if not backups_root.exists():
        return []
    if not backups_root.is_dir():
        raise BackupError(f"Backups path is not a directory: {backups_root}")

    try:
        candidates = sorted(
            (
                path
                for path in backups_root.iterdir()
                if path.is_file() and path.suffix.lower() == ".zip"
            ),
            key=lambda path: path.name,
        )
    except OSError as exc:
        raise BackupError(f"Unable to read backups folder: {exc}") from exc

    archives: list[BackupArchive] = []
    for archive_path in candidates:
        try:
            stat = archive_path.stat()
            timestamp_match = _BACKUP_ARCHIVE_TIMESTAMP.fullmatch(archive_path.stem)
            try:
                created_at = (
                    datetime.strptime(timestamp_match.group(1), "%Y%m%d_%H%M%S")
                    if timestamp_match is not None
                    else datetime.fromtimestamp(stat.st_mtime)
                )
            except ValueError:
                created_at = datetime.fromtimestamp(stat.st_mtime)
            error: str | None = None
            verified = False
            with zipfile.ZipFile(archive_path) as archive:
                corrupt_member = archive.testzip()
                if corrupt_member is not None:
                    error = f"Corrupt member: {corrupt_member}"
                elif not any(
                    name.endswith(f"/{filename}") or name == filename
                    for name in archive.namelist()
                    for filename in _BACKUP_WORLD_SAVE_FILENAMES
                ):
                    error = "Missing world save file"
                else:
                    verified = True
        except (OSError, zipfile.BadZipFile) as exc:
            try:
                stat = archive_path.stat()
                created_at = datetime.fromtimestamp(stat.st_mtime)
            except OSError:
                stat = None
                created_at = datetime.fromtimestamp(0)
            error = str(exc)
            verified = False

        archives.append(
            BackupArchive(
                path=archive_path,
                created_at=created_at,
                size_bytes=stat.st_size if stat is not None else 0,
                verified=verified,
                error=error,
            )
        )

    return sorted(archives, key=lambda archive: archive.created_at, reverse=True)


def backup_all_world_saves(
    save_games_root: Path,
    backups_root: Path,
    *,
    is_server_running: Callable[[], bool],
    now: Callable[[], datetime] = datetime.now,
) -> Path:
    """Create a verified ZIP backup of every discovered world save.

    The dedicated server must be stopped so the archive cannot contain a
    partially-written save. World directories containing either legacy
    ``WorldOption.sav`` or current ``Level.sav`` are included; this
    deliberately excludes the ``Backups`` destination when it is located
    below ``save_games_root``.

    Args:
        save_games_root: The dedicated server's ``Pal/Saved/SaveGames/0``
            directory.
        backups_root: Directory in which to create the archive.
        is_server_running: Returns whether PalServer is still running.
        now: Clock injection used for deterministic archive names in tests.

    Raises:
        ServerRunningError: If PalServer is running.
        BackupError: If no worlds are available or the archive cannot be
            created and verified.
    """
    world_directories = find_world_backup_directories(save_games_root)
    if not world_directories:
        raise BackupError(
            f"找不到可備份的世界存檔 / No world saves found: {save_games_root}"
        )
    return backup_selected_world_saves(
        save_games_root,
        backups_root,
        world_directories,
        is_server_running=is_server_running,
        now=now,
    )


def backup_selected_world_saves(
    save_games_root: Path,
    backups_root: Path,
    world_directories: list[Path],
    *,
    is_server_running: Callable[[], bool],
    now: Callable[[], datetime] = datetime.now,
) -> Path:
    """Create a verified ZIP snapshot of the explicitly selected worlds."""
    if is_server_running():
        raise ServerRunningError(
            "PalServer 仍在執行中，請先停止伺服器再備份。"
            " / PalServer is still running; stop it before backing up."
        )

    available_worlds = set(find_world_backup_directories(save_games_root))
    selected_worlds = list(dict.fromkeys(world_directories))
    if not selected_worlds:
        raise BackupError("請至少選擇一個世界存檔 / Select at least one world save")
    if any(world_dir not in available_worlds for world_dir in selected_worlds):
        raise BackupError("選取的世界存檔已不存在或無效 / Selected world save is unavailable")

    world_directories = selected_worlds

    try:
        backups_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BackupError(f"無法建立備份資料夾 / Failed to create backups folder: {exc}") from exc

    archive_path = backups_root / f"savegames_{now().strftime('%Y%m%d_%H%M%S')}.zip"
    try:
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for world_dir in world_directories:
                for file_path in sorted(world_dir.rglob("*")):
                    if file_path.is_file() and world_dir / "backup" not in file_path.parents:
                        zf.write(file_path, arcname=str(file_path.relative_to(save_games_root)))
    except OSError as exc:
        raise BackupError(f"建立備份失敗 / Failed to create backup: {exc}") from exc

    if not archive_path.exists():
        raise BackupError("備份檔案未成功建立 / Backup archive was not created")

    try:
        with zipfile.ZipFile(archive_path) as zf:
            if zf.testzip() is not None:
                raise BackupError("備份檔案損毀 / Backup archive is corrupt")
            names = zf.namelist()
    except zipfile.BadZipFile as exc:
        raise BackupError(f"備份檔案損毀 / Backup archive is corrupt: {exc}") from exc

    expected_world_saves = {
        (world_dir / filename).relative_to(save_games_root).as_posix()
        for world_dir in world_directories
        for filename in _BACKUP_WORLD_SAVE_FILENAMES
        if (world_dir / filename).is_file()
    }
    if not expected_world_saves.issubset(names):
        raise BackupError(
            "備份檔案缺少世界存檔 / Backup archive is missing one or more world save files"
        )

    return archive_path


def create_world_backup(
    world_dir: Path,
    backups_root: Path,
    *,
    now: Callable[[], datetime] = datetime.now,
) -> Path:
    """Create a timestamped ZIP backup of the entire *world_dir*.

    The archive is written to *backups_root*, which must not be nested
    inside *world_dir*, so the backup process cannot recursively include
    itself. The resulting archive is verified to contain
    ``WorldOption.sav`` before this function returns successfully.

    Raises:
        BackupError: If *world_dir* does not exist, the archive cannot be
            created, or verification fails.
    """
    if not world_dir.is_dir():
        raise BackupError(f"找不到世界資料夾 / World directory not found: {world_dir}")

    try:
        backups_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BackupError(f"無法建立備份資料夾 / Failed to create backups folder: {exc}") from exc

    timestamp = now().strftime("%Y%m%d_%H%M%S")
    archive_path = backups_root / f"{world_dir.name}_{timestamp}.zip"

    try:
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(world_dir.rglob("*")):
                if file_path.is_file():
                    zf.write(file_path, arcname=str(file_path.relative_to(world_dir.parent)))
    except OSError as exc:
        raise BackupError(f"建立備份失敗 / Failed to create backup: {exc}") from exc

    if not archive_path.exists():
        raise BackupError("備份檔案未成功建立 / Backup archive was not created")

    try:
        with zipfile.ZipFile(archive_path) as zf:
            names = zf.namelist()
    except zipfile.BadZipFile as exc:
        raise BackupError(f"備份檔案損毀 / Backup archive is corrupt: {exc}") from exc

    if not any(name.endswith(WORLD_OPTION_FILENAME) for name in names):
        raise BackupError("備份檔案缺少 WorldOption.sav，已中止儲存 / Backup missing WorldOption.sav")

    return archive_path


# ---------------------------------------------------------------------------
# Save orchestration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SaveWorldOptionsResult:
    """Result of a successful :func:`save_world_options` call."""

    backup_path: Path
    sav_path: Path


def save_world_options(
    world: WorldSaveInfo,
    gvas_file: GvasFile,
    save_type: int,
    changes: dict[str, Any],
    backups_root: Path,
    *,
    is_server_running: Callable[[], bool],
) -> SaveWorldOptionsResult:
    """Validate, back up, and safely write *changes* to *world*'s save.

    Order of operations, each of which aborts the whole process without
    touching the real file on failure:

    1. Refuse if the dedicated server is currently running.
    2. Validate every change and apply them to a copy of the decoded
       properties (the original is left untouched until re-encoding and
       round-trip verification succeed).
    3. Create and verify a full ZIP backup of the world directory.
    4. Re-encode to bytes and verify the bytes can be decoded again.
    5. Write to a temporary file and atomically replace the original.

    Raises:
        ServerRunningError: If the dedicated server is running.
        ValidationError: If any change is invalid.
        BackupError: If the backup cannot be created/verified.
        SaveEncodeError: If encoding or write-back fails.
    """
    if is_server_running():
        raise ServerRunningError(
            "PalServer 仍在執行中，請先停止伺服器再儲存設定。"
            " / PalServer is still running; stop it before saving."
        )

    original_properties = gvas_file.properties
    working_properties = copy.deepcopy(original_properties)
    apply_settings(working_properties, changes)

    backup_path = create_world_backup(world.world_dir, backups_root)

    # Re-check immediately before mutating the real file, in case the
    # server was started during backup creation.
    if is_server_running():
        raise ServerRunningError(
            "PalServer 仍在執行中，請先停止伺服器再儲存設定。"
            " / PalServer is still running; stop it before saving."
        )

    gvas_file.properties = working_properties
    try:
        encoded = encode_gvas(gvas_file, save_type)
        decode_sav_bytes(encoded)
    except WorldOptionsError:
        gvas_file.properties = original_properties
        raise

    tmp_path = world.world_option_path.with_name(world.world_option_path.name + ".tmp")
    try:
        tmp_path.write_bytes(encoded)
        tmp_path.replace(world.world_option_path)
    except OSError as exc:
        gvas_file.properties = original_properties
        raise SaveEncodeError(f"寫入存檔失敗 / Failed to write save: {exc}") from exc
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

    return SaveWorldOptionsResult(backup_path=backup_path, sav_path=world.world_option_path)
