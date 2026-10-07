import { Redirect } from 'expo-router'

// The root index redirects to the home tab.
export default function Index() {
  return <Redirect href="/(tabs)" />
}
