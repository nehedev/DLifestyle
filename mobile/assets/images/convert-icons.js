#!/usr/bin/env node

/**
 * Convert SVG icons to PNG using sharp
 * Run: node convert-icons.js
 */

const fs = require('fs');
const path = require('path');

// Check if sharp is available
let sharp;
try {
  sharp = require('sharp');
} catch (err) {
  console.log('❌ sharp not found. Installing...');
  console.log('Run: npm install --no-save sharp');
  process.exit(1);
}

const icons = [
  { svg: 'icon.svg', png: 'icon.png', size: 1024 },
  { svg: 'splash-icon.svg', png: 'splash-icon.png', size: 512 },
  { svg: 'icon.svg', png: 'favicon.png', size: 48 },
  { svg: 'android-icon-foreground.svg', png: 'android-icon-foreground.png', size: 1024 },
  { svg: 'android-icon-background.svg', png: 'android-icon-background.png', size: 1024 },
  { svg: 'android-icon-monochrome.svg', png: 'android-icon-monochrome.png', size: 1024 },
  { svg: 'logo.svg', png: 'logo.png', size: 256 },
];

async function convertIcon(svg, png, size) {
  const svgPath = path.join(__dirname, svg);
  const pngPath = path.join(__dirname, png);
  
  if (!fs.existsSync(svgPath)) {
    console.log(`⚠️  ${svg} not found, skipping...`);
    return;
  }
  
  try {
    await sharp(svgPath)
      .resize(size, size)
      .png()
      .toFile(pngPath);
    console.log(`✓ Created ${png} (${size}×${size})`);
  } catch (err) {
    console.log(`✗ Failed to create ${png}:`, err.message);
  }
}

async function convertAll() {
  console.log('Converting SVG icons to PNG...\n');
  
  for (const icon of icons) {
    await convertIcon(icon.svg, icon.png, icon.size);
  }
  
  console.log('\n✅ Icon conversion complete!');
  console.log('\nGenerated files:');
  console.log('  - icon.png (1024×1024) - Main app icon');
  console.log('  - splash-icon.png (512×512) - Splash screen with text');
  console.log('  - favicon.png (48×48) - Web favicon');
  console.log('  - logo.png (256×256) - In-app header logo');
  console.log('  - android-icon-*.png (1024×1024) - Android adaptive icons');
}

convertAll().catch(console.error);
