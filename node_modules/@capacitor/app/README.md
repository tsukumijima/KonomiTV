# @capacitor/app

The App API handles high level App state and events. For example, this API emits events when the app enters and leaves the foreground, handles deeplinks, opens other apps, and manages persisted plugin state.

## Install

```bash
npm install @capacitor/app
npx cap sync
```

## iOS

For being able to open the app from a custom scheme you need to register the scheme first. You can do it by editing the [`Info.plist`](https://capacitorjs.com/docs/ios/configuration#configuring-infoplist) file and adding this lines.


```xml
<key>CFBundleURLTypes</key>
<array>
  <dict>
    <key>CFBundleURLName</key>
    <string>com.getcapacitor.capacitor</string>
    <key>CFBundleURLSchemes</key>
    <array>
      <string>mycustomscheme</string>
    </array>
  </dict>
</array>
```

## Android

For being able to open the app from a custom scheme you need to register the scheme first. You can do it by adding this lines inside the `activity` section of the `AndroidManifest.xml`.

```xml
<intent-filter>
    <action android:name="android.intent.action.VIEW" />
    <category android:name="android.intent.category.DEFAULT" />
    <category android:name="android.intent.category.BROWSABLE" />
    <data android:scheme="@string/custom_url_scheme" />
</intent-filter>
```

`custom_url_scheme` value is stored in `strings.xml`. When the Android platform is added, `@capacitor/cli` adds the app's package name as default value, but can be replaced by editing the `strings.xml` file.

## Example

```typescript
import { App } from '@capacitor/app';

App.addListener('appStateChange', ({ isActive }) => {
  console.log('App state changed. Is active?', isActive);
});

App.addListener('appUrlOpen', data => {
  console.log('App opened with URL:', data);
});

App.addListener('appRestoredResult', data => {
  console.log('Restored state:', data);
});

const checkAppLaunchUrl = async () => {
  const { url } = await App.getLaunchUrl();

  console.log('App opened with URL: ' + url);
};
```

## Configuration

<docgen-config>
<!--Update the source file JSDoc comments and rerun docgen to update the docs below-->

| Prop                           | Type                 | Description                                                                    | Default            | Since |
| ------------------------------ | -------------------- | ------------------------------------------------------------------------------ | ------------------ | ----- |
| **`disableBackButtonHandler`** | <code>boolean</code> | Disable the plugin's default back button handling. Only available for Android. | <code>false</code> | 7.1.0 |

### Examples

In `capacitor.config.json`:

```json
{
  "plugins": {
    "App": {
      "disableBackButtonHandler": true
    }
  }
}
```

In `capacitor.config.ts`:

```ts
/// <reference types="@capacitor/app" />

import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  plugins: {
    App: {
      disableBackButtonHandler: true,
    },
  },
};

export default config;
```

</docgen-config>

## API

<docgen-index>

* [`exitApp()`](#exitapp)
* [`getInfo()`](#getinfo)
* [`getState()`](#getstate)
* [`getLaunchUrl()`](#getlaunchurl)
* [`minimizeApp()`](#minimizeapp)
* [`toggleBackButtonHandler(...)`](#togglebackbuttonhandler)
* [`addListener('appStateChange', ...)`](#addlistenerappstatechange-)
* [`addListener('pause', ...)`](#addlistenerpause-)
* [`addListener('resume', ...)`](#addlistenerresume-)
* [`addListener('appUrlOpen', ...)`](#addlistenerappurlopen-)
* [`addListener('appRestoredResult', ...)`](#addlistenerapprestoredresult-)
* [`addListener('backButton', ...)`](#addlistenerbackbutton-)
* [`removeAllListeners()`](#removealllisteners)
* [Interfaces](#interfaces)
* [Type Aliases](#type-aliases)

</docgen-index>

<docgen-api>
<!--Update the source file JSDoc comments and rerun docgen to update the docs below-->

### exitApp()

```typescript
exitApp() => Promise<void>
```

Force exit the app. This should only be used in conjunction with the `backButton` handler for Android to
exit the app when navigation is complete.

Ionic handles this itself so you shouldn't need to call this if using Ionic.

**Since:** 1.0.0

--------------------


### getInfo()

```typescript
getInfo() => Promise<AppInfo>
```

Return information about the app.

**Returns:** <code>Promise&lt;<a href="#appinfo">AppInfo</a>&gt;</code>

**Since:** 1.0.0

--------------------


### getState()

```typescript
getState() => Promise<AppState>
```

Gets the current app state.

**Returns:** <code>Promise&lt;<a href="#appstate">AppState</a>&gt;</code>

**Since:** 1.0.0

--------------------


### getLaunchUrl()

```typescript
getLaunchUrl() => Promise<AppLaunchUrl | undefined>
```

Get the URL the app was launched with, if any.

**Returns:** <code>Promise&lt;<a href="#applaunchurl">AppLaunchUrl</a>&gt;</code>

**Since:** 1.0.0

--------------------


### minimizeApp()

```typescript
minimizeApp() => Promise<void>
```

Minimizes the application.

Only available for Android.

**Since:** 1.1.0

--------------------


### toggleBackButtonHandler(...)

```typescript
toggleBackButtonHandler(options: ToggleBackButtonHandlerOptions) => Promise<void>
```

Enables or disables the plugin's back button handling during runtime.

Only available for Android.

| Param         | Type                                                                                      |
| ------------- | ----------------------------------------------------------------------------------------- |
| **`options`** | <code><a href="#togglebackbuttonhandleroptions">ToggleBackButtonHandlerOptions</a></code> |

**Since:** 7.1.0

--------------------


### addListener('appStateChange', ...)

```typescript
addListener(eventName: 'appStateChange', listenerFunc: StateChangeListener) => Promise<PluginListenerHandle>
```

Listen for changes in the app or the activity states.

On iOS it's fired when the native [UIApplication.willResignActiveNotification](https://developer.apple.com/documentation/uikit/uiapplication/1622973-willresignactivenotification) and
[UIApplication.didBecomeActiveNotification](https://developer.apple.com/documentation/uikit/uiapplication/1622953-didbecomeactivenotification) events get fired.
On Android it's fired when the Capacitor's Activity [onResume](https://developer.android.com/reference/android/app/Activity#onResume()) and [onStop](https://developer.android.com/reference/android/app/Activity#onStop()) methods gets called.
On Web it's fired when the document's visibilitychange gets fired.

| Param              | Type                                                                |
| ------------------ | ------------------------------------------------------------------- |
| **`eventName`**    | <code>'appStateChange'</code>                                       |
| **`listenerFunc`** | <code><a href="#statechangelistener">StateChangeListener</a></code> |

**Returns:** <code>Promise&lt;<a href="#pluginlistenerhandle">PluginListenerHandle</a>&gt;</code>

**Since:** 1.0.0

--------------------


### addListener('pause', ...)

```typescript
addListener(eventName: 'pause', listenerFunc: () => void) => Promise<PluginListenerHandle>
```

Listen for when the app or the activity are paused.

On iOS it's fired when the native [UIApplication.didEnterBackgroundNotification](https://developer.apple.com/documentation/uikit/uiapplication/1623071-didenterbackgroundnotification) event gets fired.
On Android it's fired when the Capacitor's Activity [onPause](https://developer.android.com/reference/android/app/Activity#onPause()) method gets called.
On Web it's fired when the document's visibilitychange gets fired and document.hidden is true.

| Param              | Type                       |
| ------------------ | -------------------------- |
| **`eventName`**    | <code>'pause'</code>       |
| **`listenerFunc`** | <code>() =&gt; void</code> |

**Returns:** <code>Promise&lt;<a href="#pluginlistenerhandle">PluginListenerHandle</a>&gt;</code>

**Since:** 4.1.0

--------------------


### addListener('resume', ...)

```typescript
addListener(eventName: 'resume', listenerFunc: () => void) => Promise<PluginListenerHandle>
```

Listen for when the app or activity are resumed.

On iOS it's fired when the native [UIApplication.willEnterForegroundNotification](https://developer.apple.com/documentation/uikit/uiapplication/1622944-willenterforegroundnotification) event gets fired.
On Android it's fired when the Capacitor's Activity [onResume](https://developer.android.com/reference/android/app/Activity#onResume()) method gets called,
but only after resume has fired first.
On Web it's fired when the document's visibilitychange gets fired and document.hidden is false.

| Param              | Type                       |
| ------------------ | -------------------------- |
| **`eventName`**    | <code>'resume'</code>      |
| **`listenerFunc`** | <code>() =&gt; void</code> |

**Returns:** <code>Promise&lt;<a href="#pluginlistenerhandle">PluginListenerHandle</a>&gt;</code>

**Since:** 4.1.0

--------------------


### addListener('appUrlOpen', ...)

```typescript
addListener(eventName: 'appUrlOpen', listenerFunc: URLOpenListener) => Promise<PluginListenerHandle>
```

Listen for url open events for the app. This handles both custom URL scheme links as well
as URLs your app handles (Universal Links on iOS and App Links on Android)

| Param              | Type                                                        |
| ------------------ | ----------------------------------------------------------- |
| **`eventName`**    | <code>'appUrlOpen'</code>                                   |
| **`listenerFunc`** | <code><a href="#urlopenlistener">URLOpenListener</a></code> |

**Returns:** <code>Promise&lt;<a href="#pluginlistenerhandle">PluginListenerHandle</a>&gt;</code>

**Since:** 1.0.0

--------------------


### addListener('appRestoredResult', ...)

```typescript
addListener(eventName: 'appRestoredResult', listenerFunc: RestoredListener) => Promise<PluginListenerHandle>
```

If the app was launched with previously persisted plugin call data, such as on Android
when an activity returns to an app that was closed, this call will return any data
the app was launched with, converted into the form of a result from a plugin call.

On Android, due to memory constraints on low-end devices, it's possible
that, if your app launches a new activity, your app will be terminated by
the operating system in order to reduce memory consumption.

For example, that means the Camera API, which launches a new Activity to
take a photo, may not be able to return data back to your app.

To avoid this, Capacitor stores all restored activity results on launch.
You should add a listener for `appRestoredResult` in order to handle any
plugin call results that were delivered when your app was not running.

Once you have that result (if any), you can update the UI to restore a
logical experience for the user, such as navigating or selecting the
proper tab.

We recommend every Android app using plugins that rely on external
Activities (for example, Camera) to have this event and process handled.

| Param              | Type                                                          |
| ------------------ | ------------------------------------------------------------- |
| **`eventName`**    | <code>'appRestoredResult'</code>                              |
| **`listenerFunc`** | <code><a href="#restoredlistener">RestoredListener</a></code> |

**Returns:** <code>Promise&lt;<a href="#pluginlistenerhandle">PluginListenerHandle</a>&gt;</code>

**Since:** 1.0.0

--------------------


### addListener('backButton', ...)

```typescript
addListener(eventName: 'backButton', listenerFunc: BackButtonListener) => Promise<PluginListenerHandle>
```

Listen for the hardware back button event (Android only). Listening for this event will disable the
default back button behaviour, so you might want to call `window.history.back()` manually.
If you want to close the app, call `App.exitApp()`.

| Param              | Type                                                              |
| ------------------ | ----------------------------------------------------------------- |
| **`eventName`**    | <code>'backButton'</code>                                         |
| **`listenerFunc`** | <code><a href="#backbuttonlistener">BackButtonListener</a></code> |

**Returns:** <code>Promise&lt;<a href="#pluginlistenerhandle">PluginListenerHandle</a>&gt;</code>

**Since:** 1.0.0

--------------------


### removeAllListeners()

```typescript
removeAllListeners() => Promise<void>
```

Remove all native listeners for this plugin

**Since:** 1.0.0

--------------------


### Interfaces


#### AppInfo

| Prop          | Type                | Description                                                                                         | Since |
| ------------- | ------------------- | --------------------------------------------------------------------------------------------------- | ----- |
| **`name`**    | <code>string</code> | The name of the app.                                                                                | 1.0.0 |
| **`id`**      | <code>string</code> | The identifier of the app. On iOS it's the Bundle Identifier. On Android it's the Application ID    | 1.0.0 |
| **`build`**   | <code>string</code> | The build version. On iOS it's the CFBundleVersion. On Android it's the versionCode.                | 1.0.0 |
| **`version`** | <code>string</code> | The app version. On iOS it's the CFBundleShortVersionString. On Android it's package's versionName. | 1.0.0 |


#### AppState

| Prop           | Type                 | Description                       | Since |
| -------------- | -------------------- | --------------------------------- | ----- |
| **`isActive`** | <code>boolean</code> | Whether the app is active or not. | 1.0.0 |


#### AppLaunchUrl

| Prop      | Type                | Description                   | Since |
| --------- | ------------------- | ----------------------------- | ----- |
| **`url`** | <code>string</code> | The url used to open the app. | 1.0.0 |


#### ToggleBackButtonHandlerOptions

| Prop          | Type                 | Description                                                          | Since |
| ------------- | -------------------- | -------------------------------------------------------------------- | ----- |
| **`enabled`** | <code>boolean</code> | Indicates whether to enable or disable default back button handling. | 7.1.0 |


#### PluginListenerHandle

| Prop         | Type                                      |
| ------------ | ----------------------------------------- |
| **`remove`** | <code>() =&gt; Promise&lt;void&gt;</code> |


#### URLOpenListenerEvent

| Prop                       | Type                 | Description                                                                                                                                                                        | Since |
| -------------------------- | -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- |
| **`url`**                  | <code>string</code>  | The URL the app was opened with.                                                                                                                                                   | 1.0.0 |
| **`iosSourceApplication`** | <code>any</code>     | The source application opening the app (iOS only) https://developer.apple.com/documentation/uikit/uiapplicationopenurloptionskey/1623128-sourceapplication                         | 1.0.0 |
| **`iosOpenInPlace`**       | <code>boolean</code> | Whether the app should open the passed document in-place or must copy it first. https://developer.apple.com/documentation/uikit/uiapplicationopenurloptionskey/1623123-openinplace | 1.0.0 |


#### RestoredListenerEvent

| Prop             | Type                              | Description                                                                                                                                       | Since |
| ---------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ----- |
| **`pluginId`**   | <code>string</code>               | The pluginId this result corresponds to. For example, `Camera`.                                                                                   | 1.0.0 |
| **`methodName`** | <code>string</code>               | The methodName this result corresponds to. For example, `getPhoto`                                                                                | 1.0.0 |
| **`data`**       | <code>any</code>                  | The result data passed from the plugin. This would be the result you'd expect from normally calling the plugin method. For example, `CameraPhoto` | 1.0.0 |
| **`success`**    | <code>boolean</code>              | Boolean indicating if the plugin call succeeded.                                                                                                  | 1.0.0 |
| **`error`**      | <code>{ message: string; }</code> | If the plugin call didn't succeed, it will contain the error message.                                                                             | 1.0.0 |


#### BackButtonListenerEvent

| Prop            | Type                 | Description                                                                                               | Since |
| --------------- | -------------------- | --------------------------------------------------------------------------------------------------------- | ----- |
| **`canGoBack`** | <code>boolean</code> | Indicates whether the browser can go back in history. False when the history stack is on the first entry. | 1.0.0 |


### Type Aliases


#### StateChangeListener

<code>(state: <a href="#appstate">AppState</a>): void</code>


#### URLOpenListener

<code>(event: <a href="#urlopenlistenerevent">URLOpenListenerEvent</a>): void</code>


#### RestoredListener

<code>(event: <a href="#restoredlistenerevent">RestoredListenerEvent</a>): void</code>


#### BackButtonListener

<code>(event: <a href="#backbuttonlistenerevent">BackButtonListenerEvent</a>): void</code>

</docgen-api>
