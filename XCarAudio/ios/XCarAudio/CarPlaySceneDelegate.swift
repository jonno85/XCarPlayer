import CarPlay
import react_native_carplay

class CarPlaySceneDelegate: UIResponder, CPTemplateApplicationSceneDelegate {

  func templateApplicationScene(
    _ templateApplicationScene: CPTemplateApplicationScene,
    didConnect interfaceController: CPInterfaceController,
    to window: CPWindow
  ) {
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

