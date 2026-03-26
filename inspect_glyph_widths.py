#!/usr/bin/env python3
"""
Inspect glyph widths in a font file.
This helps you determine appropriate custom widths for process_fonts.py
"""

import sys
from pathlib import Path
from fontTools.ttLib import TTFont

def inspect_glyph_widths(font_path, glyph_names):
    """
    Display width information for specified glyphs.

    Args:
        font_path: Path to TTF file
        glyph_names: List of glyph names to inspect
    """
    try:
        font = TTFont(font_path)
    except Exception as e:
        print(f"Error loading font: {e}")
        return

    if 'hmtx' not in font:
        print("Error: Font has no 'hmtx' table (horizontal metrics)")
        return

    hmtx = font['hmtx']

    print(f"\nFont: {Path(font_path).name}")
    print("=" * 70)

    for glyph_name in glyph_names:
        if glyph_name not in hmtx.metrics:
            print(f"\n'{glyph_name}': NOT FOUND")
            continue

        width, lsb = hmtx.metrics[glyph_name]
        print(f"\n'{glyph_name}':")
        print(f"  Advance Width: {width}")
        print(f"  Left Side Bearing: {lsb}")

        # Try to find tnum variant (check common naming conventions)
        tnum_glyph = None
        for variant in ['.tnum', '.tf']:
            if glyph_name + variant in hmtx.metrics:
                tnum_glyph = glyph_name + variant
                break

        if tnum_glyph:
            tnum_width, tnum_lsb = hmtx.metrics[tnum_glyph]
            print(f"\n'{tnum_glyph}' (tabular variant):")
            print(f"  Advance Width: {tnum_width}")
            print(f"  Left Side Bearing: {tnum_lsb}")
            print(f"  Difference: {tnum_width - width:+d}")

            # Suggest some intermediate values
            mid = (width + tnum_width) // 2
            quarter = width + (tnum_width - width) // 4
            three_quarter = width + 3 * (tnum_width - width) // 4
            print(f"\nSuggested custom widths to try:")
            print(f"  Original:       {width} (LSB: {lsb})")
            print(f"  1/4 wider:      {quarter} (LSB: {lsb})")
            print(f"  Mid-point:      {mid} (LSB: {lsb})")
            print(f"  3/4 wider:      {three_quarter} (LSB: {lsb})")
            print(f"  Tabular (full): {tnum_width} (LSB: {tnum_lsb})")
            print(f"\nExample command-line usage:")
            print(f"  --freeze-glyphs \"{glyph_name}:tnum:{mid}:{lsb}\"")

    print("\n" + "=" * 70)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python inspect_glyph_widths.py <font.ttf> [glyph1 glyph2 ...]")
        print("\nExample:")
        print("  python inspect_glyph_widths.py Inter-Regular.ttf one zero")
        print("\nIf no glyphs specified, defaults to: zero one two three four five six seven eight nine")
        sys.exit(1)

    font_path = sys.argv[1]

    # Default to inspecting all digits
    if len(sys.argv) > 2:
        glyph_names = sys.argv[2:]
    else:
        glyph_names = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']

    inspect_glyph_widths(font_path, glyph_names)
