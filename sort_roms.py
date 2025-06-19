#!/usr/bin/env python3

import os
import hashlib
import requests
import shutil
import time
import json
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

# Read RetroAchievements API configuration from app_constants
def read_constants():
    try:
        with open('APP_CONSTANTS', 'r') as f:
            constants = {}
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    constants[key] = value
            return constants
    except FileNotFoundError:
        raise Exception("APP_CONSTANTS file not found. Please create it with RA_USERNAME and RA_API_KEY.")

constants = read_constants()
RA_USERNAME = constants.get('RA_USERNAME')  # Get username from constants file
RA_API_KEY = constants.get('RA_API_KEY')    # Get API key from constants file

if not RA_USERNAME or not RA_API_KEY:
    raise Exception("RA_USERNAME and RA_API_KEY must be set in APP_CONSTANTS file")

BASE_URL = "https://retroachievements.org/API"

class Statistics:
    def __init__(self):
        self.total_roms = 0
        self.with_achievements = 0
        self.without_achievements = 0
        self.not_found_in_library = 0
        self.achievement_counts: Dict[str, int] = {}  # Game name -> achievement count
        self.errors: List[Tuple[str, str, str]] = []  # List of (rom_name, error_type, error_message)
        self.api_errors: Dict[str, int] = {}  # Error type -> count
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
        self.api_errors[error_type] = self.api_errors.get(error_type, 0) + 1

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

        if self.api_errors:
            print("\nError Summary:")
            print("-"*30)
            for error_type, count in sorted(self.api_errors.items()):
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

def calculate_md5(file_path):
    """Calculate MD5 hash of a file."""
    md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            md5.update(chunk)
    return md5.hexdigest().lower()

def get_game_info(game_id):
    """Get game information from RetroAchievements API."""
    url = f"{BASE_URL}/API_GetGameInfoAndUserProgress.php"
    params = {
        'y': RA_API_KEY,
        'u': RA_USERNAME,
        'g': game_id
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Check for API-specific error responses
        if isinstance(data, dict):
            if data.get('Error'):
                raise Exception(f"API Error: {data['Error']}")
            if not data.get('Title'):
                raise Exception("API returned empty game data")
                
        return data
    except requests.exceptions.RequestException as e:
        raise Exception(f"Network Error: {str(e)}")
    except json.JSONDecodeError as e:
        raise Exception(f"Invalid JSON Response: {str(e)}")
    except Exception as e:
        raise Exception(f"API Error: {str(e)}")

def get_game_id_by_hash(rom_hash):
    """Get game ID from hash using a local hash library."""
    hash_library_path = Path("data/0_hashlibrary.json")
    
    if not hash_library_path.exists():
        raise Exception("Hash library file not found")
        
    try:
        with open(hash_library_path, 'r') as f:
            hash_library = json.loads(f.read())
            
        # The hash library contains MD5 hashes mapped to game IDs
        if not hash_library.get('Success'):
            raise Exception("Hash library indicates failure status")
            
        if 'MD5List' not in hash_library:
            raise Exception("Hash library missing MD5List")
            
        return hash_library['MD5List'].get(rom_hash)
            
    except json.JSONDecodeError as e:
        raise Exception(f"Invalid hash library JSON: {str(e)}")
    except Exception as e:
        raise Exception(f"Hash library error: {str(e)}")

def sort_rom(rom_path, with_achievements_dir, without_achievements_dir, stats):
    """Sort a single ROM file based on whether it has achievements."""
    print(f"\nProcessing: {rom_path.name}")
    stats.total_roms += 1
    
    try:
        # Calculate MD5 hash
        rom_hash = calculate_md5(str(rom_path))
        print(f"ROM Hash (MD5): {rom_hash}")
        
        try:
            # Get game ID from hash
            game_id = get_game_id_by_hash(rom_hash)
            
            if not game_id:
                print("Game not found in hash library")
                stats.add_game_not_found()
                target_dir = without_achievements_dir
            else:
                try:
                    # Get game info from API
                    game_info = get_game_info(game_id)
                    
                    if game_info and game_info.get('NumAchievements', 0) > 0:
                        achievement_count = game_info['NumAchievements']
                        print(f"Found {achievement_count} achievements!")
                        stats.add_game_with_achievements(game_info.get('Title', rom_path.name), achievement_count)
                        target_dir = with_achievements_dir
                    else:
                        print("No achievements found")
                        stats.add_game_without_achievements()
                        target_dir = without_achievements_dir
                except Exception as e:
                    print(f"API Error: {str(e)}")
                    stats.add_error(rom_path.name, "API Error", str(e))
                    target_dir = without_achievements_dir
        except Exception as e:
            print(f"Hash Library Error: {str(e)}")
            stats.add_error(rom_path.name, "Hash Library Error", str(e))
            target_dir = without_achievements_dir
        
        # Move the ROM file
        target_path = target_dir / rom_path.name
        shutil.move(str(rom_path), str(target_path))
        print(f"Moved to: {target_path}")

    except Exception as e:
        error_msg = str(e)
        print(f"File Processing Error: {error_msg}")
        stats.add_error(rom_path.name, "File Processing Error", error_msg)

def main():
    # Setup directories
    gba_dir = Path("GBA")
    sorted_dir = Path("sorted_GBA")
    with_achievements_dir = sorted_dir / "with_achievements"
    without_achievements_dir = sorted_dir / "without_achievements"
    
    # Create output directories if they don't exist
    with_achievements_dir.mkdir(parents=True, exist_ok=True)
    without_achievements_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize statistics
    stats = Statistics()
    
    # Process all GBA ROMs
    total_roms = len(list(gba_dir.glob("*.gba")))
    for i, rom_path in enumerate(gba_dir.glob("*.gba"), 1):
        print(f"\nProgress: {i}/{total_roms} ({(i/total_roms)*100:.1f}%)")
        sort_rom(rom_path, with_achievements_dir, without_achievements_dir, stats)
        # Add a small delay to avoid hitting API rate limits
        time.sleep(1)
    
    # Print final statistics
    stats.print_report()

    # Save report to file
    report_path = sorted_dir / "sorting_report.txt"
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