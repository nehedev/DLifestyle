# Dami's Lifestyle Services — Expo (React Native)

Mobile port of the web app. Same backend, same auth model.

## 1. Install

```bash
npm install
```

## 2. Configure env (`.env`)

```env
EXPO_PUBLIC_API_BASE_URL=http://localhost:8000
EXPO_PUBLIC_GOOGLE_CLIENT_ID=xxxxxx.apps.googleusercontent.com
```

- **Android emulator**: use `http://10.0.2.2:8000`
- **iOS simulator**: `http://localhost:8000`
- **Physical device**: `http://<your-lan-ip>:8000`

## 3. Google OAuth

1. Google Cloud Console → APIs & Services → Credentials → **OAuth 2.0 Client ID (Web)**.
2. Add **Authorized redirect URIs**:
   - For Expo Go dev: the URL printed by `AuthSession.makeRedirectUri({ scheme: 'damis', path: 'oauth' })` — usually `https://auth.expo.io/@you/damis-lifestyle`.
   - For built apps: `damis://oauth`.
3. Paste the Client ID into `.env`.
4. **Backend change required**: `/api/v1/auth/google` must now also accept `redirect_uri` and pass it to Google's token endpoint when exchanging the auth code. This is a small addition — the request body already contains `redirect_uri`.

## 4. Run

```bash
npx expo start
```

Press `a` for Android, `i` for iOS, or scan the QR with Expo Go.

## What's included

- Full customer flow: Home, Menu, Item detail, Cart, Checkout, Confirmation, Account/Orders.
- Server-authoritative pricing — never computes money on the client.
- Google sign-in via `expo-auth-session` + ID token stored in `AsyncStorage`.
- Cart persisted locally and synced to `/api/v1/cart` when signed in.

## What's *not* included (yet)

- Admin dashboard (`/sudo/*` endpoints). The API client deliberately omits them; add them if you want a mobile admin.
- Payment deep-link callback screen (currently opens Paystack in an in-app browser and returns to Orders; the backend webhook is authoritative).

## Layout cheat sheet

| Web                 | Native                                 |
| ------------------- | -------------------------------------- |
| `localStorage`      | `AsyncStorage`                         |
| `@react-oauth/google` | `expo-auth-session`                  |
| `iconify-icon`      | `@expo/vector-icons` (MaterialCommunity) |
| hash router         | `@react-navigation/native-stack` + bottom tabs |
| CSS files           | `StyleSheet.create` + `src/theme.ts`   |
| `<img>`             | `<Image>`                              |