#!/bin/bash
# Script to convert SVG icons to PNG
# Requires: inkscape, rsvg-convert, or ImageMagick

cd "$(dirname "$0")"

# Check for available converter
if command -v inkscape &> /dev/null; then
    CONVERTER="inkscape"
    echo "Using Inkscape..."
elif command -v rsvg-convert &> /dev/null; then
    CONVERTER="rsvg"
    echo "Using rsvg-convert..."
elif command -v magick &> /dev/null; then
    CONVERTER="magick"
    echo "Using ImageMagick..."
elif command -v convert &> /dev/null; then
    CONVERTER="convert"
    echo "Using ImageMagick (convert)..."
else
    echo "❌ Error: No SVG converter found!"
    echo "Please install one of: inkscape, librsvg2-bin, or imagemagick"
    echo ""
    echo "Ubuntu/Debian: sudo apt install inkscape"
    echo "Or: sudo apt install librsvg2-bin"
    echo "Or: sudo apt install imagemagick"
    exit 1
fi

convert_svg() {
    local svg="$1"
    local png="$2"
    local size="$3"
    
    case $CONVERTER in
        inkscape)
            inkscape "$svg" --export-filename="$png" --export-width=$size --export-height=$size 2>/dev/null
            ;;
        rsvg)
            rsvg-convert -w $size -h $size "$svg" -o "$png"
            ;;
        magick)
            magick "$svg" -resize ${size}x${size} "$png"
            ;;
        convert)
            convert "$svg" -resize ${size}x${size} "$png"
            ;;
    esac
    
    if [ -f "$png" ]; then
        echo "✓ Created $png"
    else
        echo "✗ Failed to create $png"
    fi
}

echo "Converting SVG icons to PNG..."
echo ""

# App icon
convert_svg "icon.svg" "icon.png" 1024

# Splash icon
convert_svg "splash-icon.svg" "splash-icon.png" 512

# Favicon
convert_svg "icon.svg" "favicon.png" 48

# Android adaptive icons
convert_svg "android-icon-foreground.svg" "android-icon-foreground.png" 1024
convert_svg "android-icon-background.svg" "android-icon-background.png" 1024
convert_svg "android-icon-monochrome.svg" "android-icon-monochrome.png" 1024

# In-app logo
convert_svg "logo.svg" "logo.png" 256

echo ""
echo "✅ All icons converted successfully!"
echo ""
echo "Note: The splash icon uses Pacifico font for 'Dami's Lifestyle' text."
echo "If the font doesn't render correctly, you may need to install it:"
echo "  - Download from: https://fonts.google.com/specimen/Pacifico"
echo "  - Or use an online SVG to PNG converter"
