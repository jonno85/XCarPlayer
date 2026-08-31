#import <React/RCTBridgeModule.h>

@interface RCT_EXTERN_MODULE (CarplayNowPlaying, NSObject)

RCT_EXTERN_METHOD(pushNowPlaying:(RCTPromiseResolveBlock)resolve rejecter:(RCTPromiseRejectBlock)reject)

@end