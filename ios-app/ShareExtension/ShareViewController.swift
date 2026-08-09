import UIKit
import Social
import UniformTypeIdentifiers

/// Scaffold for Xcode Share Extension after `expo prebuild`.
/// Opens main app with kyro://save?url=...
class ShareViewController: UIViewController {
  override func viewDidAppear(_ animated: Bool) {
    super.viewDidAppear(animated)
    guard let item = extensionContext?.inputItems.first as? NSExtensionItem,
          let provider = item.attachments?.first else {
      extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
      return
    }
    let type = UTType.url.identifier
    if provider.hasItemConformingToTypeIdentifier(type) {
      provider.loadItem(forTypeIdentifier: type, options: nil) { data, _ in
        let url = (data as? URL)?.absoluteString
          ?? (data as? String)
          ?? ""
        self.openKyro(url: url)
      }
    } else if provider.hasItemConformingToTypeIdentifier(UTType.plainText.identifier) {
      provider.loadItem(forTypeIdentifier: UTType.plainText.identifier, options: nil) { data, _ in
        self.openKyro(url: (data as? String) ?? "")
      }
    } else {
      extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
    }
  }

  private func openKyro(url: String) {
    let encoded = url.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
    guard let open = URL(string: "kyro://save?url=\(encoded)") else {
      extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
      return
    }
    var responder: UIResponder? = self
    while responder != nil {
      if let app = responder as? UIApplication {
        app.open(open)
        break
      }
      responder = responder?.next
    }
    // iOS 18+: openURL on extensionContext
    extensionContext?.open(open, completionHandler: { _ in
      self.extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
    })
  }
}
