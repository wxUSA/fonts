#!/usr/bin/env python3
"""
Process TrueType font files with fontfreeze to apply OpenType features
and convert to multiple web font formats.

This script:
1. Takes *.ttf font files from input directory
2. (Optional) Selectively freezes specific glyphs with feature variants using fontTools
3. Applies global OpenType features (cv05, cv08, etc.) using pyftfeatfreeze
4. Optionally renames the font family using regex-style replacement
5. (Optional) Updates font metadata (Designer, Vendor)
6. Generates TTF output
7. Converts to WOFF and WOFF2 formats using fonttools

Requirements:
    pip install fonttools brotli pyftfeatfreeze

Usage:
    python process_fonts.py [OPTIONS]

Options:
    -i, --input DIR           Input directory containing *.ttf files (default: current dir)
    -o, --output DIR          Output directory (default: ./processed)
    -r, --rename OLD/NEW      Rename font family (e.g., 'Inter/Winter')
    --designer NAME           Set designer name in font metadata
    --vendor NAME             Set vendor/manufacturer name in font metadata
    --freeze-features LIST    Override global features (e.g., 'cv05,cv08')
    --freeze-glyphs LIST      Override selective glyph freezing (e.g., 'one:tnum,zero:tnum')
    -h, --help                Show help message

Examples:
    python process_fonts.py -i fonts/ -o output/
    python process_fonts.py -i fonts/ -o output/ --rename "Inter/Winter"
    python process_fonts.py -i fonts/ -o output/ --designer "Your Name" --vendor "Your Company"
    python process_fonts.py -i fonts/ -o output/ --freeze-features "cv05,cv08,ss01"
    python process_fonts.py -i fonts/ -o output/ --freeze-glyphs "one:tnum,zero:tnum"

Configuration:
    Edit the SELECTIVE_GLYPH_FREEZING and GLOBAL_FEATURES lists below to customize
    which glyphs and features are frozen.
"""

import os
import sys
import subprocess
import glob
import argparse
from pathlib import Path
from fontTools.ttLib import TTFont

# ============================================================================
# CONFIGURATION
# ============================================================================

# Selective glyph freezing: Replace specific glyphs with their feature variants
# Format: (glyph_name, feature_tag)
# Common glyph names: zero, one, two, three, four, five, six, seven, eight, nine
# Common features: tnum (tabular numbers), onum (oldstyle numbers), etc.
SELECTIVE_GLYPH_FREEZING = [
    ('one', 'tnum'),    # Make "1" always tabular
    # ('zero', 'tnum'),   # Make "0" always tabular
]

# Global feature freezing: Apply these features to all glyphs
# Common features: cv01-cv99 (character variants), ss01-ss20 (stylistic sets), etc.
# Inter example: cv05: tailed L (for fonts that support it)
#                cv08: block I (for fonts that support it)
GLOBAL_FEATURES = ['cv05', 'cv08']

# ============================================================================
# GLYPH MANIPULATION FUNCTIONS
# ============================================================================

def find_substitution_glyph(font, base_glyph, feature_tag):
    """
    Find what glyph a base glyph substitutes to for a given feature.

    Args:
        font: TTFont object
        base_glyph: Base glyph name (e.g., 'one')
        feature_tag: OpenType feature tag (e.g., 'tnum')

    Returns:
        The substitute glyph name or None if not found.
    """
    if 'GSUB' not in font:
        return None

    gsub = font['GSUB']

    if not hasattr(gsub.table, 'FeatureList'):
        return None

    for feature_record in gsub.table.FeatureList.FeatureRecord:
        if feature_record.FeatureTag == feature_tag:
            feature = feature_record.Feature

            for lookup_index in feature.LookupListIndex:
                lookup = gsub.table.LookupList.Lookup[lookup_index]

                # Type 1 = Single substitution
                if lookup.LookupType == 1:
                    for subtable in lookup.SubTable:
                        if hasattr(subtable, 'mapping') and base_glyph in subtable.mapping:
                            return subtable.mapping[base_glyph]

    return None

def copy_glyph_data(font, source_glyph, target_glyph):
    """
    Copy glyph outline and metrics from source to target.

    Args:
        font: TTFont object
        source_glyph: Source glyph name
        target_glyph: Target glyph name
    """
    glyf = font.get('glyf')
    hmtx = font['hmtx']

    if glyf and source_glyph in glyf.glyphs and target_glyph in glyf.glyphs:
        # Copy outline
        glyf.glyphs[target_glyph] = glyf.glyphs[source_glyph]

    # Copy metrics (width and left side bearing)
    if source_glyph in hmtx.metrics and target_glyph in hmtx.metrics:
        hmtx.metrics[target_glyph] = hmtx.metrics[source_glyph]

def apply_selective_glyph_freezing(font_path, glyph_substitutions):
    """
    Replace specific glyphs with their feature variants.

    Args:
        font_path: Path to TTF file (will be modified in place)
        glyph_substitutions: List of (glyph_name, feature_tag) tuples

    Returns:
        Number of successful substitutions
    """
    if not glyph_substitutions:
        return 0

    font = TTFont(font_path)
    successful = 0

    for glyph_name, feature_tag in glyph_substitutions:
        substitute_glyph = find_substitution_glyph(font, glyph_name, feature_tag)

        if substitute_glyph:
            copy_glyph_data(font, substitute_glyph, glyph_name)
            print(f"    ✓ Froze '{glyph_name}' with {feature_tag} variant ('{substitute_glyph}')")
            successful += 1
        else:
            print(f"    ⚠ Could not find {feature_tag} variant for '{glyph_name}'")

    if successful > 0:
        font.save(font_path)

    return successful

def update_font_metadata(font_path, designer=None, vendor=None):
    """
    Update font metadata fields (Designer, Vendor).

    Args:
        font_path: Path to TTF file (will be modified in place)
        designer: Designer name to set
        vendor: Vendor name to set

    Returns:
        True if any metadata was updated
    """
    if not designer and not vendor:
        return False

    font = TTFont(font_path)
    updated = False

    # The 'name' table contains various metadata
    if 'name' not in font:
        print(f"    ⚠ Font has no 'name' table")
        return False

    name_table = font['name']

    # Name IDs (per OpenType spec):
    # 8 = Manufacturer (Vendor)
    # 9 = Designer
    # We need to update across all platform/encoding combinations

    if vendor:
        # Update nameID 8 (Manufacturer/Vendor)
        for record in name_table.names:
            if record.nameID == 8:
                record.string = vendor if isinstance(vendor, bytes) else vendor.encode(record.getEncoding())
                updated = True

        # If no existing records, add new ones for common platforms
        if not any(record.nameID == 8 for record in name_table.names):
            name_table.setName(vendor, 8, 3, 1, 0x409)  # Windows, Unicode BMP, English US
            name_table.setName(vendor, 8, 1, 0, 0)      # Mac, Roman, English
            updated = True

        print(f"    ✓ Updated Vendor: {vendor}")

    if designer:
        # Update nameID 9 (Designer)
        for record in name_table.names:
            if record.nameID == 9:
                record.string = designer if isinstance(designer, bytes) else designer.encode(record.getEncoding())
                updated = True

        # If no existing records, add new ones
        if not any(record.nameID == 9 for record in name_table.names):
            name_table.setName(designer, 9, 3, 1, 0x409)  # Windows, Unicode BMP, English US
            name_table.setName(designer, 9, 1, 0, 0)      # Mac, Roman, English
            updated = True

        print(f"    ✓ Updated Designer: {designer}")

    if updated:
        font.save(font_path)

    return updated

# ============================================================================
# DEPENDENCY CHECKS
# ============================================================================

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

def process_fonts(input_dir, output_dir, features, glyph_substitutions=None, rename_from=None, rename_to=None, designer=None, vendor=None):
    """
    Process all *.ttf fonts in input directory.

    Args:
        input_dir: Directory containing *.ttf files
        output_dir: Directory to save processed fonts
        features: List of OpenType features to apply globally
        glyph_substitutions: List of (glyph_name, feature_tag) tuples for selective freezing
        rename_from: Optional old font family name to replace
        rename_to: Optional new font family name
        designer: Optional designer name to set in font metadata
        vendor: Optional vendor name to set in font metadata
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

        # Step 0: Apply selective glyph freezing (before global features)
        if glyph_substitutions:
            # First copy the file to output location
            import shutil
            shutil.copy2(str(ttf_file), str(ttf_output))

            print(f"  Applying selective glyph freezing...")
            count = apply_selective_glyph_freezing(str(ttf_output), glyph_substitutions)
            if count > 0:
                print(f"  ✓ Successfully froze {count} glyph(s)")

            # Use the modified file as input for next step
            input_for_features = str(ttf_output)
        else:
            input_for_features = str(ttf_file)

        # Step 0.5: Update font metadata (if requested)
        if designer or vendor:
            # If we haven't copied yet, copy now
            if input_for_features == str(ttf_file):
                import shutil
                shutil.copy2(str(ttf_file), str(ttf_output))
                input_for_features = str(ttf_output)

            print(f"  Updating font metadata...")
            update_font_metadata(input_for_features, designer=designer, vendor=vendor)

        # Step 1: Freeze global OpenType features (and optionally rename)
        if features:
            if not freeze_features(input_for_features, str(ttf_output), features, rename_from, rename_to):
                print(f"  ✗ Feature freezing failed, Skipping web font generation for {ttf_file.name}")
                continue
        elif not glyph_substitutions:
            # No features and no glyph substitutions, just copy with optional rename
            import shutil
            shutil.copy2(str(ttf_file), str(ttf_output))
            if rename_from and rename_to:
                print(f"  Note: Renaming requires feature freezing step")

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
    parser = argparse.ArgumentParser(
        description='Process TrueType font files with OpenType feature freezing and format conversion',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -i fonts/ -o output/
  %(prog)s -i fonts/ -o output/ --rename "Inter/Winter"
  %(prog)s -i fonts/ -o output/ --designer "Your Name" --vendor "Your Company"
  %(prog)s -i fonts/ -o output/ --freeze-features "cv05,cv08,ss01"
  %(prog)s -i fonts/ -o output/ --freeze-glyphs "one:tnum,zero:tnum"
  %(prog)s --input ./fonts --output ./processed --rename "OldFont/NewFont" --designer "Jane Doe"

Configuration:
  Edit SELECTIVE_GLYPH_FREEZING and GLOBAL_FEATURES in the script to set defaults.
  Use --freeze-features and --freeze-glyphs to override these defaults.

Common Features:
  • cv01-cv99: Character variants
  • ss01-ss20: Stylistic sets
  • tnum: Tabular numbers
  • onum: Oldstyle numbers
        """
    )

    parser.add_argument(
        '-i', '--input',
        default='.',
        help='Input directory containing *.ttf files (default: current directory)'
    )

    parser.add_argument(
        '-o', '--output',
        default='./processed',
        help='Output directory for processed fonts (default: ./processed)'
    )

    parser.add_argument(
        '-r', '--rename',
        metavar='OLD/NEW',
        help='Rename font family (format: OldName/NewName, e.g., "Inter/Winter")'
    )

    parser.add_argument(
        '--designer',
        metavar='NAME',
        help='Set designer name in font metadata'
    )

    parser.add_argument(
        '--vendor',
        metavar='NAME',
        help='Set vendor/manufacturer name in font metadata'
    )

    parser.add_argument(
        '-f', '--freeze-features',
        metavar='FEATURES',
        help='Comma-separated list of OpenType features to freeze globally (e.g., "cv05,cv08,ss01"). Overrides GLOBAL_FEATURES.'
    )

    parser.add_argument(
        '-g', '--freeze-glyphs',
        metavar='GLYPHS',
        help='Comma-separated list of glyph:feature pairs for selective freezing (e.g., "one:tnum,zero:tnum"). Overrides SELECTIVE_GLYPH_FREEZING.'
    )

    args = parser.parse_args()

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

    # Parse rename option (format: OldName/NewName)
    rename_from = None
    rename_to = None
    if args.rename:
        if '/' in args.rename:
            parts = args.rename.split('/', 1)
            rename_from = parts[0]
            rename_to = parts[1]
        else:
            print(f"Error: Invalid rename format '{args.rename}'. Expected 'OldName/NewName'")
            sys.exit(1)

    # Parse freeze-features option (comma-separated list)
    features = GLOBAL_FEATURES
    if args.freeze_features:
        features = [f.strip() for f in args.freeze_features.split(',') if f.strip()]
        if not features:
            print("Error: --freeze-features provided but no valid features found")
            sys.exit(1)

    # Parse freeze-glyphs option (comma-separated glyph:feature pairs)
    glyph_substitutions = SELECTIVE_GLYPH_FREEZING
    if args.freeze_glyphs:
        glyph_substitutions = []
        for pair in args.freeze_glyphs.split(','):
            pair = pair.strip()
            if ':' not in pair:
                print(f"Error: Invalid glyph:feature format '{pair}'. Expected format like 'one:tnum'")
                sys.exit(1)
            glyph, feature = pair.split(':', 1)
            glyph = glyph.strip()
            feature = feature.strip()
            if glyph and feature:
                glyph_substitutions.append((glyph, feature))
            else:
                print(f"Error: Invalid glyph:feature format '{pair}'. Both glyph and feature must be non-empty")
                sys.exit(1)

    print(f"Input directory:  {args.input}")
    print(f"Output directory: {args.output}")
    print()

    # Display configuration
    if glyph_substitutions:
        source = "(from --freeze-glyphs)" if args.freeze_glyphs else "(from config)"
        print(f"Selective glyph freezing {source}:")
        for glyph, feature in glyph_substitutions:
            print(f"  • '{glyph}' with {feature}")
    else:
        print("Selective glyph freezing: (none)")
    print()

    if features:
        source = "(from --freeze-features)" if args.freeze_features else "(from config)"
        print(f"Global features to freeze {source}: {', '.join(features)}")
    else:
        print("Global features to freeze: (none)")
    print()

    if rename_from and rename_to:
        print(f"Font rename: {rename_from} -> {rename_to}")
    else:
        print(f"Font rename: (no rename)")
    print()

    if args.designer:
        print(f"Designer: {args.designer}")
    if args.vendor:
        print(f"Vendor: {args.vendor}")
    if args.designer or args.vendor:
        print()

    # Process fonts
    process_fonts(
        args.input,
        args.output,
        features,
        glyph_substitutions,
        rename_from,
        rename_to,
        designer=args.designer,
        vendor=args.vendor
    )

    print("=" * 70)
    print("Processing complete!")
    print("=" * 70)
    print()
    print("Tips:")
    print("  • Edit SELECTIVE_GLYPH_FREEZING to freeze specific characters with features")
    print("  • Edit GLOBAL_FEATURES to change which features are applied to all glyphs")
    print("  • Common glyph names: zero, one, two, three, four, five, six, seven, eight, nine")
    print("  • Common features: tnum, onum, cv01-cv99, ss01-ss20")
    print()

if __name__ == '__main__':
    main()
