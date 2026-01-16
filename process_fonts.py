#!/usr/bin/env python3
"""
Process TrueType font files with fontfreeze to apply OpenType features
and convert to multiple web font formats.

This script:
1. Takes *.ttf font files from input directory
2. Applies OpenType features (cv05, cv08) using pyftfeatfreeze
3. Optionally renames the font family using regex-style replacement
4. Generates TTF output
5. Converts to WOFF and WOFF2 formats using fonttools

Requirements:
    pip install fonttools brotli pyftfeatfreeze

Usage:
    python process_inter_fonts.py [input_dir] [output_dir] [old_name/new_name]
    
    input_dir:  Directory containing *.ttf files (default: current dir)
    output_dir: Output directory (default: ./processed)
    rename:     Font rename in format 'OldName/NewName' (e.g., 'Inter/Winter')
                This replaces all instances of OldName with NewName
                (default: no rename)
"""

import os
import sys
import subprocess
import glob
from pathlib import Path

def check_dependencies():
    """Check if required tools are installed."""
    try:
        import fontTools
        print("✓ fonttools installed")
    except ImportError:
        print("✗ fonttools not found. Install with: pip install fonttools")
        return False
    
    try:
        import brotli
        print("✓ brotli installed")
    except ImportError:
        print("✗ brotli not found. Install with: pip install brotli")
        return False
    
    try:
        result = subprocess.run(['pyftfeatfreeze', '--help'], 
                              capture_output=True, text=True)
        print("✓ pyftfeatfreeze installed")
    except FileNotFoundError:
        print("✗ pyftfeatfreeze not found. Install with: pip install pyftfeatfreeze")
        return False
    
    return True

def freeze_features(input_font, output_font, features, rename_from=None, rename_to=None):
    """
    Apply OpenType features to font using pyftfeatfreeze.
    
    Args:
        input_font: Path to input TTF file
        output_font: Path to output TTF file
        features: List of OpenType feature tags to freeze (e.g., ['cv05', 'cv08'])
        rename_from: Optional old font family name to replace
        rename_to: Optional new font family name
    """
    feature_string = ','.join(features)
    
    cmd = [
        'pyftfeatfreeze',
        '-f', feature_string,
    ]
    
    # Add rename option if specified
    if rename_from and rename_to:
        cmd.extend(['-R', f'{rename_from}/{rename_to}'])
        print(f"  Freezing features: {feature_string}, renaming {rename_from} -> {rename_to}")
    else:
        print(f"  Freezing features: {feature_string}")
    
    cmd.extend([input_font, output_font])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"  ✗ Error: {result.stderr}")
        return False
    
    print(f"  ✓ Created: {output_font}")
    return True

def convert_to_woff(ttf_path, woff_path):
    """Convert TTF to WOFF using fonttools."""
    from fontTools.ttLib import TTFont
    
    font = TTFont(ttf_path)
    font.flavor = 'woff'
    font.save(woff_path)
    print(f"  ✓ Created: {woff_path}")

def convert_to_woff2(ttf_path, woff2_path):
    """Convert TTF to WOFF2 using fonttools."""
    from fontTools.ttLib import TTFont
    
    font = TTFont(ttf_path)
    font.flavor = 'woff2'
    font.save(woff2_path)
    print(f"  ✓ Created: {woff2_path}")

def process_fonts(input_dir, output_dir, features, rename_from=None, rename_to=None):
    """
    Process all *.ttf fonts in input directory.
    
    Args:
        input_dir: Directory containing *.ttf files
        output_dir: Directory to save processed fonts
        features: List of OpenType features to apply
        rename_from: Optional old font family name to replace
        rename_to: Optional new font family name
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    # Create output directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Find all TTF files
    ttf_files = sorted(input_path.glob('*.ttf'))
    
    if not ttf_files:
        print(f"No *.ttf files found in {input_dir}")
        return
    
    print(f"\nFound {len(ttf_files)} font file(s) to process\n")
    
    for ttf_file in ttf_files:
        print(f"Processing: {ttf_file.name}")
        
        # Generate output filename - replace old name with new name if provided
        if rename_from and rename_to:
            base_name = ttf_file.stem.replace(rename_from, rename_to)
        else:
            base_name = ttf_file.stem
        
        # Output paths
        ttf_output = output_path / f"{base_name}.ttf"
        woff_output = output_path / f"{base_name}.woff"
        woff2_output = output_path / f"{base_name}.woff2"
        
        # Step 1: Freeze OpenType features (and optionally rename)
        if not freeze_features(str(ttf_file), str(ttf_output), features, rename_from, rename_to):
            print(f"  ✗ Output failed, Skipping web font generation for {ttf_file.name}")
            continue
        
        # Step 2: Convert to WOFF
        try:
            convert_to_woff(str(ttf_output), str(woff_output))
        except Exception as e:
            print(f"  ✗ WOFF conversion failed: {e}")
        
        # Step 3: Convert to WOFF2
        try:
            convert_to_woff2(str(ttf_output), str(woff2_output))
        except Exception as e:
            print(f"  ✗ WOFF2 conversion failed: {e}")
        
        print()

def main():
    """Main entry point."""
    print("=" * 70)
    print("Font Processor with OpenType Feature Freezing")
    print("=" * 70)
    print()
    
    # Check dependencies
    print("Checking dependencies...")
    if not check_dependencies():
        print("\nPlease install missing dependencies and try again.")
        sys.exit(1)
    
    print()
    
    # Parse arguments
    if len(sys.argv) > 1:
        input_dir = sys.argv[1]
    else:
        input_dir = '.'
    
    if len(sys.argv) > 2:
        output_dir = sys.argv[2]
    else:
        output_dir = './processed'
    
    # Parse rename option (format: OldName/NewName)
    rename_from = None
    rename_to = None
    if len(sys.argv) > 3:
        rename_arg = sys.argv[3]
        if '/' in rename_arg:
            parts = rename_arg.split('/', 1)
            rename_from = parts[0]
            rename_to = parts[1]
        else:
            print(f"Warning: Invalid rename format '{rename_arg}'. Expected 'OldName/NewName'")
    
    # Features to freeze
    # cv05: tailed L (for fonts that support it)
    # cv08: block I (for fonts that support it)
    features = ['cv05', 'cv08']
    
    print(f"Input directory:  {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Features to freeze: {', '.join(features)}")
    if rename_from and rename_to:
        print(f"Font rename: {rename_from} -> {rename_to}")
    else:
        print(f"Font rename: (no rename)")
    print()
    
    # Process fonts
    process_fonts(input_dir, output_dir, features, rename_from, rename_to)
    
    print("=" * 70)
    print("Processing complete!")
    print("=" * 70)
    print()
    print("Note: To also apply 'tnum' (tabular numbers), you can either:")
    print("  1. Add 'tnum' to the features list in this script")
    print("  2. Apply it selectively in CSS with: font-feature-settings: 'tnum';")
    print()

if __name__ == '__main__':
    main()
