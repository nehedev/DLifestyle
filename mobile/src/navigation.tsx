import { MaterialCommunityIcons } from '@expo/vector-icons'
import { createNavigationContainerRef } from '@react-navigation/native'
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { useCart } from './cart'
import { C } from './theme'

import HomeScreen from '../screens/HomeScreen'
import MenuScreen from '../screens/MenuScreen'
import CartScreen from '../screens/CartScreen'
import RequestsScreen from '../screens/RequestsScreen'
import ItemDetailScreen from '../screens/ItemDetailScreen'
import CheckoutScreen from '../screens/CheckoutScreen'
import ConfirmationScreen from '../screens/ConfirmationScreen'
import PaymentCallbackScreen from '../screens/PaymentCallbackScreen'

import AdminHomeScreen from '../screens/admin/AdminHomeScreen'
import AdminMenuScreen from '../screens/admin/AdminMenuScreen'
import AdminServicesScreen from '../screens/admin/AdminServicesScreen'
import AdminOrdersScreen from '../screens/admin/AdminOrdersScreen'
import AdminPaymentsScreen from '../screens/admin/AdminPaymentsScreen'
import AdminServiceRequestsScreen from '../screens/admin/AdminServiceRequestsScreen'
import AdminStoreScreen from '../screens/admin/AdminStoreScreen'
import AdminUsersScreen from '../screens/admin/AdminUsersScreen'

import type { CatalogItem, OrderResponse } from './types'

export type RootStackParamList = {
  Tabs: undefined
  ItemDetail: { item: CatalogItem }
  Checkout: undefined
  Confirmation: { order: OrderResponse }
  PaymentCallback: { orderId?: number } | undefined
  Admin: undefined
  AdminMenu: undefined
  AdminServices: undefined
  AdminOrders: undefined
  AdminPayments: undefined
  AdminServiceRequests: undefined
  AdminStore: undefined
  AdminUsers: undefined
}

export type AdminStackParamList = RootStackParamList

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
        name="Confirmation"
        component={ConfirmationScreen}
        options={{ headerShown: false }}
      />
      <Stack.Screen
        name="PaymentCallback"
        component={PaymentCallbackScreen}
        options={{ headerShown: false, gestureEnabled: false }}
      />
      <Stack.Screen name="Admin" component={AdminHomeScreen} options={{ headerShown: false }} />
      <Stack.Screen name="AdminMenu" component={AdminMenuScreen} options={{ headerShown: false }} />
      <Stack.Screen
        name="AdminServices"
        component={AdminServicesScreen}
        options={{ headerShown: false }}
      />
      <Stack.Screen
        name="AdminOrders"
        component={AdminOrdersScreen}
        options={{ headerShown: false }}
      />
      <Stack.Screen
        name="AdminPayments"
        component={AdminPaymentsScreen}
        options={{ headerShown: false }}
      />
      <Stack.Screen
        name="AdminServiceRequests"
        component={AdminServiceRequestsScreen}
        options={{ headerShown: false }}
      />
      <Stack.Screen
        name="AdminStore"
        component={AdminStoreScreen}
        options={{ headerShown: false }}
      />
      <Stack.Screen
        name="AdminUsers"
        component={AdminUsersScreen}
        options={{ headerShown: false }}
      />
    </Stack.Navigator>
  )
}
