# Dami's Lifestyle Services — Expo (React Native)

Mobile port of the web app. Same backend, same API contract, same auth model.

## 1. Install

```bash
npm install
```

## 2. Configure env (`.env`)

```env
EXPO_PUBLIC_API_BASE_URL=http://localhost:8000
EXPO_PUBLIC_GOOGLE_CLIENT_ID=xxxxxx.apps.googleusercontent.com
EXPO_PUBLIC_WEB_CALLBACK_URL=https://your-web-app.com/payment/callback
```

- **Android emulator**: use `http://10.0.2.2:8000`
- **iOS simulator**: `http://localhost:8000`
- **Physical device**: `http://<your-lan-ip>:8000`

`EXPO_PUBLIC_WEB_CALLBACK_URL` is the URL the Paystack hosted page redirects to
after payment. The in-app browser watches for it and hands back to the app so the
payment status screen can poll the backend.

## 3. Google OAuth

1. Google Cloud Console → APIs & Services → Credentials → **OAuth 2.0 Client ID (Web)**.
2. Add **Authorized redirect URIs**:
   - For Expo Go dev: the URL printed by `AuthSession.makeRedirectUri({ scheme: 'damis', path: 'oauth' })` — usually `https://auth.expo.io/@you/damis-lifestyle`.
   - For built apps: `damis://oauth`.
3. Paste the Client ID into `.env`.
4. The app sends the redirect URI it used to `POST /api/v1/auth/google`. The
   backend forwards it to Google's token endpoint, so native codes verify
   correctly. The web popup flow omits it and falls back to `postmessage`.

## 4. Run

```bash
npx expo start
```

Press `a` for Android, `i` for iOS, or scan the QR with Expo Go.

## What's included

- Full customer flow: Home, Menu, Item detail, Cart, Checkout, Payment status, Account/Orders.
- Server-authoritative pricing — never computes money on the client beyond display.
- Store settings (delivery fee, order cutoff, advance window) drive the cart and checkout.
- Google sign-in via `expo-auth-session`; the session ID token is stored in `AsyncStorage`.
- Cart is persisted locally and synced to `GET`/`PUT /api/v1/cart` when signed in.
- Checkout sends service requests and the food order, then starts Paystack in an in-app browser.
- Orders and service requests can be cancelled from the Account tab while the backend allows it.

## What's *not* included

- Admin dashboard (`/sudo/*` endpoints). The API client deliberately omits them; add them if you want a mobile admin.

## Layout cheat sheet

| Web                   | Native                                 |
| --------------------- | -------------------------------------- |
| `localStorage`        | `AsyncStorage`                         |
| `@react-oauth/google` | `expo-auth-session`                    |
| `iconify-icon`        | `@expo/vector-icons` (MaterialCommunity) |
| hash router           | `@react-navigation/native-stack` + bottom tabs |
| CSS files             | `StyleSheet.create` + `src/theme.ts`   |
| `<img>`               | `<Image>`                              |
| `src/pages/`          | `src/screens/`                         |
| `src/store.tsx`       | `src/store.tsx`                        |
