#!/usr/bin/env python3

import json
from pathlib import Path

def convert_hash_library():
    output_path = Path("data/hashlibrary.json")

    # Start from existing output if it exists (append-only behavior)
    if output_path.exists():
        with output_path.open("r") as f:
            old_format = json.load(f)
        old_format.setdefault("Success", True)
        old_format.setdefault("MD5List", {})
        if not isinstance(old_format["MD5List"], dict):
            raise ValueError("Expected output data['MD5List'] to be a JSON object (dict).")
    else:
        # Create the old format structure
        old_format = {
            "Success": True,
            "MD5List": {}
        }
    
    # Get all JSON files from all_hash folder
    all_hash_dir = Path('all_hash')
    json_files = sorted(all_hash_dir.glob('*.json'))
    
    total_games = 0
    skipped_existing_hashes = 0
    processed_files = []
    
    # Process each JSON file
    for json_file in json_files:
        print(f"Processing {json_file.name}...")
        with open(json_file, 'r') as f:
            new_data = json.load(f)
        
        # Convert data
        file_games = 0
        for game in new_data:
            game_id = game['ID']
            for hash_value in game['Hashes']:
                key = hash_value.lower()
                if key in old_format["MD5List"]:
                    skipped_existing_hashes += 1
                    continue
                old_format['MD5List'][key] = game_id
            file_games += 1
        
        total_games += file_games
        processed_files.append((json_file.name, file_games))
        print(f"  - Processed {file_games} games from {json_file.name}")
    
    # Write to the hashlibrary.json file
    with open('data/hashlibrary.json', 'w') as f:
        json.dump(old_format, f, indent=2)
    
    # Print statistics
    print(f"\nConversion complete!")
    print(f"Total files processed: {len(processed_files)}")
    print(f"Total games processed: {total_games}")
    print(f"Total hashes: {len(old_format['MD5List'])}")
    print(f"Skipped existing hashes: {skipped_existing_hashes}")
    print(f"\nOutput written to: data/hashlibrary.json")

if __name__ == "__main__":
    convert_hash_library() 