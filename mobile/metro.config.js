// Learn more https://docs.expo.io/guides/customizing-metro
const { getDefaultConfig } = require('expo/metro-config');

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

// Enable tree shaking and minification
config.transformer = {
  ...config.transformer,
  minifierConfig: {
    compress: {
      drop_console: true, // Remove console.log in production
    },
  },
};

module.exports = config;
