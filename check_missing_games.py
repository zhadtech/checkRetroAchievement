#!/usr/bin/env python3

import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

def normalize_game_name(name: str) -> str:
    """Normalize game name for comparison by removing common patterns."""
    # Remove region codes like (USA), (J), (U), etc.
    name = re.sub(r'\s*\([^)]*\)\s*', ' ', name)
    # Remove brackets like [!], [b], etc.
    name = re.sub(r'\s*\[[^\]]*\]\s*', ' ', name)
    # Remove file extensions
    name = re.sub(r'\.[a-z]{2,4}$', '', name, flags=re.IGNORECASE)
    # Remove extra whitespace and convert to lowercase
    name = ' '.join(name.split()).lower()
    # Remove common punctuation
    name = re.sub(r'[^\w\s]', '', name)
    return name

def get_platform_mapping() -> Dict[str, str]:
    """Map platform names from must-have.json to sorted folder names."""
    return {
        'Arcade': 'sorted_ARCADE',
        'Atari 2600': 'sorted_ATARI_2600',
        'Nintendo Entertainment System (NES)': 'sorted_NES',
        'Super Nintendo (SNES)': 'sorted_SNES',
        'Nintendo 64': 'sorted_N64',
        'Commodore 64': 'sorted_C64',
        'Game Boy (Original)': 'sorted_GAME_BOY',
        'Game Boy Color': 'sorted_GAME_BOY_COLOR',
        'Game Boy Advance (GBA)': 'sorted_GAME_BOY_ADVANCE',
        'Nintendo 3DS': 'sorted_3DS',
        'Sega Master System': 'sorted_MASTER_SYSTEM',
        'Sega Genesis / Mega Drive': 'sorted_GENESIS',
        'Sega Game Gear': 'sorted_GAME_GEAR',
        'PlayStation 1 (PS1)': 'sorted_PS1',
        'PlayStation 2 (PS2)': 'sorted_PS2',
        'TurboGrafx-16 / PC Engine': 'sorted_PCE',
        'Neo Geo Pocket Color': 'sorted_NEO_GEO_POCKET_COLOR',
        'PC (DOS/Windows)': 'sorted_PC',
    }

def load_must_have_games() -> Dict[str, List[str]]:
    """Load games from must-have.json grouped by platform."""
    with open('must-have.json', 'r') as f:
        data = json.load(f)
    
    games_by_platform = {}
    for platform in data.get('platforms', []):
        platform_name = platform.get('name', '')
        games = [game.get('title', '') for game in platform.get('games', [])]
        games_by_platform[platform_name] = games
    
    return games_by_platform

def get_sorted_folder_games() -> Dict[str, Set[str]]:
    """Get all game filenames from sorted_* folders, grouped by folder."""
    base_path = Path('.')
    sorted_folders = [d for d in base_path.iterdir() if d.is_dir() and d.name.startswith('sorted_')]
    
    games_by_folder = {}
    for folder in sorted_folders:
        folder_name = folder.name
        games = set()
        
        # Get all files in the folder recursively
        for file_path in folder.rglob('*'):
            if file_path.is_file():
                games.add(file_path.name)
        
        games_by_folder[folder_name] = games
    
    return games_by_folder

def find_missing_games():
    """Find games from must-have.json that are not in sorted_* folders."""
    # Load must-have games
    must_have_games = load_must_have_games()
    platform_mapping = get_platform_mapping()
    
    # Get games from sorted folders
    sorted_folder_games = get_sorted_folder_games()
    
    # Create normalized sets for each sorted folder
    normalized_sorted_games: Dict[str, Set[str]] = {}
    for folder_name, games in sorted_folder_games.items():
        normalized_set = set()
        for game_file in games:
            normalized = normalize_game_name(game_file)
            normalized_set.add(normalized)
        normalized_sorted_games[folder_name] = normalized_set
    
    # Find missing games
    missing_games = {}
    
    for platform_name, games in must_have_games.items():
        sorted_folder = platform_mapping.get(platform_name)
        if not sorted_folder:
            # Platform doesn't have a sorted folder, mark all as missing
            missing_games[platform_name] = games
            continue
        
        if sorted_folder not in normalized_sorted_games:
            # Sorted folder doesn't exist, mark all as missing
            missing_games[platform_name] = games
            continue
        
        normalized_sorted = normalized_sorted_games[sorted_folder]
        missing = []
        
        for game_title in games:
            normalized_title = normalize_game_name(game_title)
            
            # Check for exact match or partial match
            found = False
            if normalized_title in normalized_sorted:
                found = True
            else:
                # Try partial matching - check if any sorted game contains the title or vice versa
                # Also try word-by-word matching for better accuracy
                title_words = set(normalized_title.split())
                for sorted_game in normalized_sorted:
                    sorted_words = set(sorted_game.split())
                    # If most words match, consider it found
                    if title_words and sorted_words:
                        common_words = title_words & sorted_words
                        # If at least 70% of words match, or if one contains the other
                        if (len(common_words) / max(len(title_words), len(sorted_words)) >= 0.7 or
                            normalized_title in sorted_game or sorted_game in normalized_title):
                            found = True
                            break
            
            if not found:
                missing.append(game_title)
        
        if missing:
            missing_games[platform_name] = missing
    
    return missing_games, sorted_folder_games

def main():
    print("Scanning must-have.json and sorted_* folders...")
    print("=" * 60)
    
    missing_games, sorted_folder_games = find_missing_games()
    
    if not missing_games:
        print("\n✓ All games from must-have.json are found in sorted_* folders!")
        return
    
    print("\nMissing Games Report")
    print("=" * 60)
    print(f"\nTotal platforms with missing games: {len(missing_games)}\n")
    
    total_missing = 0
    for platform_name, games in sorted(missing_games.items()):
        if games:
            total_missing += len(games)
            print(f"\n{platform_name}:")
            print("-" * 60)
            for game in games:
                print(f"  - {game}")
    
    print("\n" + "=" * 60)
    print(f"Total missing games: {total_missing}")
    print("=" * 60)
    
    # Also show what folders exist for reference
    print("\nAvailable sorted folders:")
    for folder_name in sorted(sorted_folder_games.keys()):
        game_count = len(sorted_folder_games[folder_name])
        print(f"  - {folder_name} ({game_count} files)")

if __name__ == "__main__":
    main()
