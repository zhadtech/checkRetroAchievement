#!/usr/bin/env python3

import hashlib
import shutil
import json
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
from datetime import datetime

class Statistics:
    def __init__(self):
        self.total_roms = 0
        self.with_achievements = 0
        self.without_achievements = 0
        self.not_found_in_library = 0
        self.achievement_counts: Dict[str, int] = {}  # Game name -> achievement count
        self.errors: List[Tuple[str, str, str]] = []  # List of (rom_name, error_type, error_message)
        self.library_errors: Dict[str, int] = {}  # Error type -> count
        self.start_time = datetime.now()

    def add_game_with_achievements(self, game_name: str, achievement_count: int):
        self.with_achievements += 1
        self.achievement_counts[game_name] = achievement_count

    def add_game_without_achievements(self):
        self.without_achievements += 1

    def add_game_not_found(self):
        self.not_found_in_library += 1

    def add_error(self, rom_name: str, error_type: str, error_msg: str):
        self.errors.append((rom_name, error_type, error_msg))
        self.library_errors[error_type] = self.library_errors.get(error_type, 0) + 1

    def print_report(self):
        duration = datetime.now() - self.start_time
        
        print("\n" + "="*50)
        print("SORTING COMPLETE - SUMMARY REPORT")
        print("="*50)
        print(f"\nProcessing Duration: {duration}")
        print(f"\nTotal ROMs processed: {self.total_roms}")
        print(f"ROMs with achievements: {self.with_achievements}")
        print(f"ROMs without achievements: {self.without_achievements}")
        print(f"ROMs not found in hash library: {self.not_found_in_library}")
        
        if self.achievement_counts:
            print("\nGames with achievements:")
            print("-"*30)
            # Sort games by achievement count in descending order
            sorted_games = sorted(self.achievement_counts.items(), key=lambda x: x[1], reverse=True)
            for game_name, count in sorted_games:
                print(f"{game_name}: {count} achievements")

        if self.library_errors:
            print("\nError Summary:")
            print("-"*30)
            for error_type, count in sorted(self.library_errors.items()):
                print(f"{error_type}: {count} occurrences")

        if self.errors:
            print("\nDetailed Errors:")
            print("-"*30)
            # Group errors by type
            error_groups: Dict[str, List[Tuple[str, str]]] = {}
            for rom_name, error_type, error_msg in self.errors:
                if error_type not in error_groups:
                    error_groups[error_type] = []
                error_groups[error_type].append((rom_name, error_msg))
            
            # Print errors grouped by type
            for error_type, errors in error_groups.items():
                print(f"\n{error_type}:")
                for rom_name, error_msg in errors:
                    print(f"  - {rom_name}: {error_msg}")

        # Calculate and display percentages
        if self.total_roms > 0:
            with_achievements_percent = (self.with_achievements / self.total_roms) * 100
            error_percent = (len(self.errors) / self.total_roms) * 100
            not_found_percent = (self.not_found_in_library / self.total_roms) * 100
            print(f"\nStatistics:")
            print("-"*30)
            print(f"ROMs with achievements: {with_achievements_percent:.2f}%")
            print(f"ROMs with errors: {error_percent:.2f}%")
            print(f"ROMs not found: {not_found_percent:.2f}%")

def get_rom_data_from_file(file_path: Path) -> Optional[bytes]:
    """Get ROM data from a file, handling archives if needed."""
    # Check if it's an archive
    if file_path.suffix.lower() == '.zip':
        try:
            with zipfile.ZipFile(file_path, 'r') as z:
                # Find ROM files in archive (prioritize .nes, .fc, .fds)
                rom_extensions = ['.nes', '.NES', '.fc', '.FC', '.fds', '.FDS']
                for ext in rom_extensions:
                    for name in z.namelist():
                        if name.endswith(ext):
                            return z.read(name)
                # If no standard ROM extension found, try any file
                if z.namelist():
                    return z.read(z.namelist()[0])
        except Exception as e:
            return None
    # TODO: Add 7z and RAR support if needed
    # For now, treat as regular file
    try:
        with open(file_path, 'rb') as f:
            return f.read()
    except Exception:
        return None

def calculate_md5_from_data(data: bytes) -> str:
    """Calculate MD5 hash from data."""
    return hashlib.md5(data).hexdigest().lower()

def calculate_rom_hashes(rom_data: bytes) -> List[str]:
    """Calculate multiple hash variations for a ROM.
    Returns list of hashes: [full_hash, no_header_hash, with_header_hash]
    """
    hashes = []
    
    # Hash the ROM as-is
    full_hash = calculate_md5_from_data(rom_data)
    hashes.append(full_hash)
    
    # Try stripping iNES header (first 16 bytes) if present
    # iNES header starts with "NES" followed by 0x1A
    if len(rom_data) >= 16 and rom_data[0:4] == b'NES\x1a':
        no_header_hash = calculate_md5_from_data(rom_data[16:])
        hashes.append(no_header_hash)
    
    # Try hashing without first 16 bytes (common header size)
    if len(rom_data) > 16:
        no_header_hash2 = calculate_md5_from_data(rom_data[16:])
        if no_header_hash2 not in hashes:
            hashes.append(no_header_hash2)
    
    return hashes

def load_hash_library():
    """Load all hash data from all_hash JSON files and create a hash -> game_info mapping."""
    all_hash_dir = Path("all_hash")
    
    if not all_hash_dir.exists():
        raise Exception(f"all_hash directory not found at {all_hash_dir.absolute()}")
    
    hash_to_game: Dict[str, Dict] = {}
    
    # Get all JSON files from all_hash folder
    json_files = sorted(all_hash_dir.glob("*.json"))
    
    if not json_files:
        raise Exception("No hash JSON files found in all_hash directory")
    
    print(f"Loading hash library from {len(json_files)} file(s)...")
    
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                games = json.load(f)
            
            # Each file contains a list of games
            for game in games:
                game_info = {
                    'ID': game.get('ID'),
                    'Title': game.get('Title', ''),
                    'ConsoleName': game.get('ConsoleName', ''),
                    'NumAchievements': game.get('NumAchievements', 0),
                    'ConsoleID': game.get('ConsoleID')
                }
                
                # Map each hash to the game info
                for hash_value in game.get('Hashes', []):
                    hash_to_game[hash_value.lower()] = game_info
            
        except json.JSONDecodeError as e:
            print(f"Warning: Error parsing {json_file.name}: {str(e)}")
            continue
        except Exception as e:
            print(f"Warning: Error loading {json_file.name}: {str(e)}")
            continue
    
    print(f"Loaded {len(hash_to_game)} hash entries")
    return hash_to_game

def get_game_info_by_hash(rom_hashes: List[str], hash_library: Dict[str, Dict]) -> Optional[Dict]:
    """Get game information from hash using the loaded hash library.
    Tries multiple hash variations to find a match.
    """
    for rom_hash in rom_hashes:
        game_info = hash_library.get(rom_hash.lower())
        if game_info:
            return game_info
    return None

def get_platform_folder_name(console_name):
    """Convert console name to folder name format (e.g., 'Arcade' -> 'sorted_ARCADE')."""
    if not console_name:
        return None
    
    # Special mappings for console names that need specific folder names
    console_mappings = {
        'PC Engine/TurboGrafx-16': 'PCE',
        'PC Engine CD/TurboGrafx-CD': 'PCCD',
        'Genesis/Mega Drive': 'GENESIS',
        'SNES/Super Famicom': 'SNES',
        'NES/Famicom': 'NES',
    }
    
    # Check if there's a specific mapping
    if console_name in console_mappings:
        return f"sorted_{console_mappings[console_name]}"
    
    # Otherwise, convert to uppercase and replace special characters with underscores
    # Replace spaces, slashes, hyphens, and other special chars
    folder_name = console_name.upper()
    # Replace common special characters
    folder_name = folder_name.replace(' ', '_')
    folder_name = folder_name.replace('/', '_')
    folder_name = folder_name.replace('-', '_')
    folder_name = folder_name.replace('&', 'AND')
    
    return f"sorted_{folder_name}"

def sort_rom(rom_path, hash_library, stats):
    """Sort a single ROM file based on whether it has achievements.
    ROMs with achievements are moved to platform-specific sorted folders.
    ROMs without achievements remain in their original location."""
    print(f"\nProcessing: {rom_path.name}")
    stats.total_roms += 1
    
    try:
        # Get ROM data (handles archives)
        rom_data = get_rom_data_from_file(rom_path)
        if not rom_data:
            print("Could not read ROM data - leaving in original location")
            stats.add_error(rom_path.name, "File Read Error", "Could not read ROM data")
            return
        
        # Calculate multiple hash variations
        rom_hashes = calculate_rom_hashes(rom_data)
        print(f"ROM Hash(es): {rom_hashes[0]}" + (f" (also tried: {', '.join(rom_hashes[1:])})" if len(rom_hashes) > 1 else ""))
        
        # Get game info from hash library (tries all hash variations)
        game_info = get_game_info_by_hash(rom_hashes, hash_library)
        
        if not game_info:
            print("Game not found in hash library - leaving in original location")
            stats.add_game_not_found()
            return  # Leave ROM in original location
        
        # Check if game has achievements
        achievement_count = game_info.get('NumAchievements', 0)
        
        if achievement_count > 0:
            console_name = game_info.get('ConsoleName', '')
            game_title = game_info.get('Title', rom_path.name)
            print(f"Found {achievement_count} achievements! Platform: {console_name}")
            stats.add_game_with_achievements(game_title, achievement_count)
            
            # Get platform folder name
            platform_folder = get_platform_folder_name(console_name)
            if platform_folder:
                # Create platform-specific sorted folder
                sorted_platform_dir = Path(platform_folder)
                sorted_platform_dir.mkdir(parents=True, exist_ok=True)
                
                # Move ROM to platform-specific sorted folder
                target_path = sorted_platform_dir / rom_path.name
                shutil.move(str(rom_path), str(target_path))
                print(f"Moved to: {target_path}")
            else:
                print("Warning: Could not determine platform - leaving in original location")
        else:
            print("No achievements found - leaving in original location")
            stats.add_game_without_achievements()
            # ROM stays in original location

    except Exception as e:
        error_msg = str(e)
        print(f"File Processing Error: {error_msg} - leaving in original location")
        stats.add_error(rom_path.name, "File Processing Error", error_msg)
        # ROM stays in original location

def get_rom_extensions():
    """Get common ROM file extensions."""
    return {
        '.gba', '.gb', '.gbc', '.nes', '.sfc', '.smc',
        '.md', '.gen', '.gg', '.lynx', '.a26',
        '.bin', '.rom', '.pce',  # include PC Engine HuCard ROMs
        '.zip', '.7z', '.rar',
    }

def find_rom_files(roms_dir):
    """Recursively find all ROM files in the ROMS directory."""
    rom_extensions = get_rom_extensions()
    rom_files = []
    
    # Explicitly include these directories
    additional_dirs = [
        roms_dir / "ROMS_Square" / "ARCADE",
        roms_dir / "ROMS_Square" / "FBNEO",
        roms_dir / "ROMS_Square" / "MD",
        roms_dir / "ROMS_Square" / "LYNX",
    ]
    
    for ext in rom_extensions:
        # Find files with this extension recursively (case-insensitive search)
        rom_files.extend(roms_dir.rglob(f"*{ext}"))
        rom_files.extend(roms_dir.rglob(f"*{ext.upper()}"))
        
        # Explicitly search in additional directories
        for additional_dir in additional_dirs:
            if additional_dir.exists():
                rom_files.extend(additional_dir.rglob(f"*{ext}"))
                rom_files.extend(additional_dir.rglob(f"*{ext.upper()}"))
    
    # Remove duplicates and sort
    return sorted(set(rom_files))

def main():
    # Setup directories
    roms_dir = Path("ROMS")
    
    if not roms_dir.exists():
        raise Exception(f"ROMS directory not found at {roms_dir.absolute()}")
    
    # Load hash library
    try:
        hash_library = load_hash_library()
    except Exception as e:
        raise Exception(f"Failed to load hash library: {str(e)}")
    
    # Initialize statistics
    stats = Statistics()
    
    # Find all ROM files recursively
    print(f"\nScanning for ROM files in {roms_dir}...")
    rom_files = find_rom_files(roms_dir)
    total_roms = len(rom_files)
    
    if total_roms == 0:
        print(f"No ROM files found in {roms_dir}")
        return
    
    print(f"Found {total_roms} ROM file(s) to process\n")
    
    # Process all ROMs
    for i, rom_path in enumerate(rom_files, 1):
        print(f"\nProgress: {i}/{total_roms} ({(i/total_roms)*100:.1f}%)")
        sort_rom(rom_path, hash_library, stats)
    
    # Print final statistics
    stats.print_report()

    # Save report to file
    report_dir = Path(".")
    report_path = report_dir / "sorting_report.txt"
    with open(report_path, 'w') as f:
        # Redirect print output to file
        import sys
        original_stdout = sys.stdout
        sys.stdout = f
        stats.print_report()
        sys.stdout = original_stdout
    
    print(f"\nDetailed report saved to: {report_path}")

if __name__ == "__main__":
    main() 