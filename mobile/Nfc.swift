import Capacitor
import CoreNFC

@objc(CampusNfcPlugin)
public class CampusNfcPlugin: CAPPlugin, CAPBridgedPlugin, NFCTagReaderSessionDelegate {
    public let identifier = "CampusNfcPlugin"
    public let jsName = "CampusNfc"
    public let pluginMethods: [CAPPluginMethod] = [CAPPluginMethod(name: "read", returnType: CAPPluginReturnPromise)]
    private var pending: CAPPluginCall?
    private var session: NFCTagReaderSession?
    @objc func read(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            guard self.pending == nil else { call.reject("正在读卡，请稍候"); return }
            guard NFCTagReaderSession.readingAvailable else { call.reject("此 iPhone 不支持 NFC 读卡"); return }
            self.pending = call
            self.session = NFCTagReaderSession(pollingOption: .iso14443, delegate: self, queue: .main)
            self.session?.alertMessage = "请贴近校园卡；MIFARE Classic 卡可能无法读取，可使用终端提供的 UID。"
            self.session?.begin()
        }
    }
    public func tagReaderSessionDidBecomeActive(_ session: NFCTagReaderSession) {}
    public func tagReaderSession(_ session: NFCTagReaderSession, didInvalidateWithError error: Error) {
        pending?.reject("读卡结束或卡片不兼容：\(error.localizedDescription)")
        pending = nil; self.session = nil
    }
    public func tagReaderSession(_ session: NFCTagReaderSession, didDetect tags: [NFCTag]) {
        guard tags.count == 1 else { session.alertMessage = "请仅放置一张卡"; session.restartPolling(); return }
        let data: Data
        switch tags[0] {
        case .miFare(let tag): data = tag.identifier
        case .iso7816(let tag): data = tag.identifier
        default: session.invalidate(errorMessage: "卡片类型不支持，请使用终端读取 UID"); return
        }
        pending?.resolve(["uid": data.map { String(format: "%02X", $0) }.joined()])
        pending = nil; session.invalidate(); self.session = nil
    }
}
class CampusBridgeViewController: CAPBridgeViewController {
    override func capacitorDidLoad() { bridge?.registerPluginInstance(CampusNfcPlugin()) }
}
