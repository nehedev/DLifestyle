import { Stack } from 'expo-router'
import * as SplashScreen from 'expo-splash-screen'
import { useEffect } from 'react'
import { SafeAreaProvider } from 'react-native-safe-area-context'
import { AppAuth } from '@/auth'
import { CatalogProvider, CartProvider } from '@/store'

SplashScreen.preventAutoHideAsync()

export default function RootLayout() {
  useEffect(() => {
    void SplashScreen.hideAsync()
  }, [])

  return (
    <SafeAreaProvider>
      <AppAuth>
        <CatalogProvider>
          <CartProvider>
            <Stack
              screenOptions={{
                headerStyle: { backgroundColor: '#FFFCE0' },
                headerTintColor: '#0A6A1B',
                headerTitleStyle: { fontWeight: '800' },
                contentStyle: { backgroundColor: '#FFFCE0' },
              }}
            >
              {/* Bottom-tab group — header hidden, each tab screen owns its own Header component */}
              <Stack.Screen name="(tabs)" options={{ headerShown: false }} />

              {/* Stack screens pushed on top of the tabs */}
              <Stack.Screen name="item-detail" options={{ title: '' }} />
              <Stack.Screen name="checkout" options={{ title: 'Checkout' }} />
              <Stack.Screen
                name="payment-callback"
                options={{ headerShown: false, gestureEnabled: false }}
              />
            </Stack>
          </CartProvider>
        </CatalogProvider>
      </AppAuth>
    </SafeAreaProvider>
  )
}
