import CarPlay
import react_native_carplay

class CarPlaySceneDelegate: UIResponder, CPTemplateApplicationSceneDelegate {
  var window: UIWindow?
  private var interfaceController: CPInterfaceController?

  func templateApplicationScene(
    _ templateApplicationScene: CPTemplateApplicationScene,
    didConnect interfaceController: CPInterfaceController,
    to window: CPWindow
  ) {
    self.interfaceController = interfaceController
    self.window = window
    
    RNCarPlay.connect(
      with: interfaceController,
      window: window
    )
  }

  func templateApplicationScene(
    _ templateApplicationScene: CPTemplateApplicationScene,
    didDisconnectInterfaceController interfaceController: CPInterfaceController
  ) {
    RNCarPlay.disconnect()
  }
}

