# Welcome to your Expo app 👋

This is an [Expo](https://expo.dev) project created with [`create-expo-app`](https://www.npmjs.com/package/create-expo-app).

## Get started

1. Install dependencies

   ```bash
   npm install
   ```

2. Start the app

   ```bash
   npx expo start
   ```

In the output, you'll find options to open the app in a

- [development build](https://docs.expo.dev/develop/development-builds/introduction/)
- [Android emulator](https://docs.expo.dev/workflow/android-studio-emulator/)
- [iOS simulator](https://docs.expo.dev/workflow/ios-simulator/)
- [Expo Go](https://expo.dev/go), a limited sandbox for trying out app development with Expo

You can start developing by editing the files inside the **app** directory. This project uses [file-based routing](https://docs.expo.dev/router/introduction).

## Google sign-in (native)

Sign-in uses native Google Sign-In
([`@react-native-google-signin/google-signin`](https://react-native-google-signin.github.io)),
which requires a **development build** — it does not work in Expo Go.

1. In Google Cloud Console, create OAuth 2.0 client IDs for the same project:
   - **Web** — used as `webClientId` and by the web build.
   - **Android** — with the app's package name and SHA-1 fingerprint.
   - **iOS** — with the app's bundle identifier.
2. Set the environment values (see `.env.example`):
   - `EXPO_PUBLIC_GOOGLE_CLIENT_ID` — the Web client ID.
   - `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID` — the iOS client ID (required for iOS).
3. Build and run a development build:
   ```bash
   npx expo prebuild --clean
   npx expo run:android   # or: npx expo run:ios
   ```

`app.config.ts` adds the Google Sign-In config plugin (with the iOS URL scheme)
only when `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID` is set. Android needs no plugin
change because the project does not use Firebase.

**How it talks to the backend:** the native SDK returns a Google **ID token**,
which the app sends as `Authorization: Bearer …`. The backend verifies it
against Google's JWKS and provisions the user (see `/api/v1/me`). The web build
keeps the authorization-code flow through `POST /api/v1/auth/google`.


## Get a fresh project

When you're ready, run:

```bash
npm run reset-project
```

This command will move the starter code to the **app-example** directory and create a blank **app** directory where you can start developing.

### Other setup steps

- To set up ESLint for linting, run `npx expo lint`, or follow our guide on ["Using ESLint and Prettier"](https://docs.expo.dev/guides/using-eslint/)
- If you'd like to set up unit testing, follow our guide on ["Unit Testing with Jest"](https://docs.expo.dev/develop/unit-testing/)
- Learn more about the TypeScript setup in this template in our guide on ["Using TypeScript"](https://docs.expo.dev/guides/typescript/)

## Learn more

To learn more about developing your project with Expo, look at the following resources:

- [Expo documentation](https://docs.expo.dev/): Learn fundamentals, or go into advanced topics with our [guides](https://docs.expo.dev/guides).
- [Learn Expo tutorial](https://docs.expo.dev/tutorial/introduction/): Follow a step-by-step tutorial where you'll create a project that runs on Android, iOS, and the web.

## Join the community

Join our community of developers creating universal apps.

- [Expo on GitHub](https://github.com/expo/expo): View our open source platform and contribute.
- [Discord community](https://chat.expo.dev): Chat with Expo users and ask questions.
