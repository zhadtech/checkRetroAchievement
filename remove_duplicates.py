#!/usr/bin/env python3

from pathlib import Path
import shutil
from typing import Dict, List

from sort_roms import get_rom_data_from_file, calculate_md5_from_data


def find_sorted_folders(base_dir: Path) -> List[Path]:
    """Return all platform folders that start with 'sorted_'."""
    return [p for p in base_dir.iterdir() if p.is_dir() and p.name.startswith("sorted_")]


def dedupe_folder(folder: Path, duplicates_root: Path) -> Dict[str, int]:
    """
    Remove duplicate ROMs inside a single sorted_* folder.

    Duplicates are detected by ROM content hash (using the same
    archive/ROM reading logic as in sort_roms.py).

    Instead of deleting files outright, duplicates are moved into a
    parallel folder under `duplicates/` so they can be inspected or
    restored if needed.
    """
    stats = {
        "total_files": 0,
        "unique_files": 0,
        "duplicates_moved": 0,
        "read_errors": 0,
    }

    seen_hashes: Dict[str, Path] = {}

    for rom_path in sorted(folder.iterdir()):
        if not rom_path.is_file():
            continue

        stats["total_files"] += 1

        rom_data = get_rom_data_from_file(rom_path)
        if not rom_data:
            # Could not read / unsupported archive – skip but count as an error
            stats["read_errors"] += 1
            print(f"[{folder.name}] Skipping (cannot read): {rom_path.name}")
            continue

        content_hash = calculate_md5_from_data(rom_data)

        if content_hash not in seen_hashes:
            seen_hashes[content_hash] = rom_path
            stats["unique_files"] += 1
            continue

        # Duplicate found – move it to duplicates folder
        target_dir = duplicates_root / folder.name
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / rom_path.name
        # Avoid overwriting in the duplicates folder
        if target_path.exists():
            stem = target_path.stem
            suffix = target_path.suffix
            i = 1
            while True:
                candidate = target_dir / f"{stem}_dup{i}{suffix}"
                if not candidate.exists():
                    target_path = candidate
                    break
                i += 1

        shutil.move(str(rom_path), str(target_path))
        stats["duplicates_moved"] += 1
        original = seen_hashes[content_hash]
        print(
            f"[{folder.name}] Duplicate: {rom_path.name} "
            f"(same content as {original.name}) -> moved to {target_path}"
        )

    return stats


def main() -> None:
    base_dir = Path(".").resolve()
    duplicates_root = base_dir / "duplicates"

    sorted_folders = find_sorted_folders(base_dir)
    if not sorted_folders:
        print("No 'sorted_*' folders found.")
        return

    print(f"Found {len(sorted_folders)} sorted_* folder(s).")
    print("Scanning for duplicate ROMs within each folder (by content hash)...\n")

    overall = {
        "folders_processed": 0,
        "total_files": 0,
        "unique_files": 0,
        "duplicates_moved": 0,
        "read_errors": 0,
    }

    for folder in sorted(sorted_folders):
        print(f"=== {folder.name} ===")
        stats = dedupe_folder(folder, duplicates_root)

        print(
            f"Summary for {folder.name}: "
            f"{stats['total_files']} files, "
            f"{stats['unique_files']} unique, "
            f"{stats['duplicates_moved']} duplicates moved, "
            f"{stats['read_errors']} read errors\n"
        )

        overall["folders_processed"] += 1
        overall["total_files"] += stats["total_files"]
        overall["unique_files"] += stats["unique_files"]
        overall["duplicates_moved"] += stats["duplicates_moved"]
        overall["read_errors"] += stats["read_errors"]

    print("=== Overall summary ===")
    print(f"Folders processed       : {overall['folders_processed']}")
    print(f"Total files scanned     : {overall['total_files']}")
    print(f"Unique files kept       : {overall['unique_files']}")
    print(f"Duplicates moved        : {overall['duplicates_moved']}")
    print(f"Files with read errors  : {overall['read_errors']}")
    print(f"\nDuplicates are stored under: {duplicates_root}")


if __name__ == "__main__":
    main()

