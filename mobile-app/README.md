# X Car Audio mobile app

React Native/Expo mobile player and controller for AudioStation and the companion Synology downloader.

## Run

```sh
corepack enable
yarn install
yarn start
```

Native builds:

```sh
yarn ios
yarn android
```

Configure the downloader URL and NAS connection in the app’s Settings screen. The downloader service is maintained separately in [`../synology-downloader/`](../synology-downloader/).

Product and platform details are in [`docs/X Car Audio_prd.md`](docs/X%20Car%20Audio_prd.md).
