import CarPlay
import React

@objc(CarplayNowPlaying)
public class CarplayNowPlaying: NSObject {
  @objc
  public static func requiresMainQueueSetup() -> Bool {
    return true
  }

  @objc(pushNowPlaying:rejecter:)
  public func pushNowPlaying(_ resolve: @escaping (Any?) -> Void, rejecter: @escaping (String?, String?, NSError?) -> Void) {
    var debugLog = "V4: "
    DispatchQueue.main.async {
      let scenes = UIApplication.shared.connectedScenes
      debugLog += "SC:\(scenes.count) "
      
      for scene in scenes {
        if let carScene = scene as? CPTemplateApplicationScene {
          debugLog += "Scene_Found "
          let ic = carScene.interfaceController
          let templates = ic.templates
          
          debugLog += "Stack:[\(templates.map { String(describing: type(of: $0)) }.joined(separator: ","))] "
          
          // CRITICAL FIX: Providing the 'id' expected by library's forced cast
          let np = CPNowPlayingTemplate.shared
          if np.userInfo == nil {
             np.userInfo = ["id": "NowPlaying"]
          }
          
          // CRITICAL: NEVER push if already there.
          if templates.contains(where: { $0 is CPNowPlayingTemplate }) {
            if ic.topTemplate is CPNowPlayingTemplate {
              debugLog += "ALREADY_TOP "
              resolve(debugLog)
              return
            }
            debugLog += "POP_TO_NP "
            ic.pop(to: np, animated: true)
            resolve(debugLog)
            return
          }
          
          // Standard push
          debugLog += "PUSH_NP "
          ic.pushTemplate(np, animated: true, completion: nil)
          
          resolve(debugLog)
          return
        }
      }
      resolve(debugLog + "NO_CAR_SCENE")
    }
  }
}
