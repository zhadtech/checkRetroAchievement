#!/usr/bin/env python3

import json
from pathlib import Path

def convert_hash_library():
    # Read the new format
    with open('all-gba.json', 'r') as f:
        new_data = json.load(f)
    
    # Create the old format structure
    old_format = {
        "Success": True,
        "MD5List": {}
    }
    
    # Convert data
    for game in new_data:
        game_id = game['ID']
        for hash_value in game['Hashes']:
            old_format['MD5List'][hash_value.lower()] = game_id
    
    # Write to the old format file
    with open('data/0_hashlibrary.json', 'w') as f:
        json.dump(old_format, f, indent=2)
    
    # Print statistics
    print(f"Conversion complete!")
    print(f"Total games processed: {len(new_data)}")
    print(f"Total hashes: {len(old_format['MD5List'])}")

if __name__ == "__main__":
    convert_hash_library() 