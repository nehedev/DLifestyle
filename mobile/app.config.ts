import type { ConfigContext, ExpoConfig } from 'expo/config'

// Native Google Sign-In uses a config plugin. Without Firebase the plugin only
// registers the iOS URL scheme, so it needs the iOS client ID. We add it only
// when that client ID is configured; Android needs no plugin changes when it is
// not using Firebase (the native module is autolinked).
const GOOGLE_SIGNIN_PLUGIN = '@react-native-google-signin/google-signin'

/** `594...apps.googleusercontent.com` -> `com.googleusercontent.apps.594...`. */
function reversedClientId(clientId: string | undefined): string | null {
  if (!clientId) return null
  const suffix = clientId.split('.apps.googleusercontent.com')[0]
  if (!suffix || suffix === clientId) return null
  return `com.googleusercontent.apps.${suffix}`
}

export default ({ config }: ConfigContext): ExpoConfig => {
  const iosUrlScheme = reversedClientId(
    process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID,
  )

  const plugins = (config.plugins ?? []).filter((plugin) => {
    const name = typeof plugin === 'string' ? plugin : plugin[0]
    return name !== GOOGLE_SIGNIN_PLUGIN
  })

  if (iosUrlScheme) {
    plugins.push([GOOGLE_SIGNIN_PLUGIN, { iosUrlScheme }])
  }

  return { ...config, plugins } as ExpoConfig
}
