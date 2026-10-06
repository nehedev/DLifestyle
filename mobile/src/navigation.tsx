import { MaterialCommunityIcons } from '@expo/vector-icons'
import { createNavigationContainerRef } from '@react-navigation/native'
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { useCart } from './store'
import { C } from './theme'

import HomeScreen from './screens/HomeScreen'
import MenuScreen from './screens/MenuScreen'
import CartScreen from './screens/CartScreen'
import RequestsScreen from './screens/RequestsScreen'
import ItemDetailScreen from './screens/ItemDetailScreen'
import CheckoutScreen from './screens/CheckoutScreen'
import PaymentCallbackScreen from './screens/PaymentCallbackScreen'

import type { CatalogItem } from './types'

export type RootStackParamList = {
  Tabs: undefined
  ItemDetail: { item: CatalogItem }
  Checkout: undefined
  PaymentCallback: { orderId?: number } | undefined
}

export type TabParamList = {
  Home: undefined
  Menu: { svc?: boolean } | undefined
  Cart: undefined
  Orders: undefined
}

export const navigationRef = createNavigationContainerRef<RootStackParamList>()

const Stack = createNativeStackNavigator<RootStackParamList>()
const Tab = createBottomTabNavigator<TabParamList>()

function Tabs() {
  const { count } = useCart()
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: C.green,
        tabBarInactiveTintColor: C.mut,
        tabBarStyle: { backgroundColor: C.white, borderTopColor: C.line },
      }}
    >
      <Tab.Screen
        name="Home"
        component={HomeScreen}
        options={{
          tabBarIcon: ({ color, size }) => (
            <MaterialCommunityIcons name="home-outline" size={size} color={color} />
          ),
        }}
      />
      <Tab.Screen
        name="Menu"
        component={MenuScreen}
        options={{
          tabBarIcon: ({ color, size }) => (
            <MaterialCommunityIcons name="silverware-fork-knife" size={size} color={color} />
          ),
        }}
      />
      <Tab.Screen
        name="Cart"
        component={CartScreen}
        options={{
          tabBarBadge: count > 0 ? count : undefined,
          tabBarBadgeStyle: { backgroundColor: C.burg, color: '#fff' },
          tabBarIcon: ({ color, size }) => (
            <MaterialCommunityIcons name="cart-outline" size={size} color={color} />
          ),
        }}
      />
      <Tab.Screen
        name="Orders"
        component={RequestsScreen}
        options={{
          tabBarLabel: 'Account',
          tabBarIcon: ({ color, size }) => (
            <MaterialCommunityIcons name="account-outline" size={size} color={color} />
          ),
        }}
      />
    </Tab.Navigator>
  )
}

export function RootNavigator() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: C.cream },
        headerTintColor: C.green,
        headerTitleStyle: { fontWeight: '800' },
        contentStyle: { backgroundColor: C.cream },
      }}
    >
      <Stack.Screen name="Tabs" component={Tabs} options={{ headerShown: false }} />
      <Stack.Screen name="ItemDetail" component={ItemDetailScreen} options={{ title: '' }} />
      <Stack.Screen name="Checkout" component={CheckoutScreen} options={{ title: 'Checkout' }} />
      <Stack.Screen
        name="PaymentCallback"
        component={PaymentCallbackScreen}
        options={{ headerShown: false, gestureEnabled: false }}
      />
    </Stack.Navigator>
  )
}
