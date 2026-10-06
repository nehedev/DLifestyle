import { NavigationContainer, type LinkingOptions } from '@react-navigation/native'
import * as Linking from 'expo-linking'
import { StatusBar } from 'expo-status-bar'
import { SafeAreaProvider } from 'react-native-safe-area-context'
import { AppAuth } from './src/auth'
import { CatalogProvider, CartProvider } from './src/store'
import { navigationRef, RootNavigator, type RootStackParamList } from './src/navigation'

const linking: LinkingOptions<RootStackParamList> = {
  prefixes: [Linking.createURL('/'), 'damis://'],
  config: {
    screens: {
      PaymentCallback: 'payment/callback',
      Tabs: {
        screens: {
          Home: '',
          Menu: 'menu',
          Cart: 'cart',
          Orders: 'orders',
        },
      },
    },
  },
}

export default function App() {
  return (
    <SafeAreaProvider>
      <AppAuth>
        <CatalogProvider>
          <CartProvider>
            <NavigationContainer ref={navigationRef} linking={linking}>
              <StatusBar style="dark" />
              <RootNavigator />
            </NavigationContainer>
          </CartProvider>
        </CatalogProvider>
      </AppAuth>
    </SafeAreaProvider>
  )
}