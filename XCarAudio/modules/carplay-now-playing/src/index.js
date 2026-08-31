import { NativeModules } from 'react-native';

const { CarplayNowPlaying } = NativeModules;

export default CarplayNowPlaying || {
  pushNowPlaying: async () => {
    console.warn('CarplayNowPlaying native module not found');
    return { debugLog: "Module Not Found" };
  }
};
