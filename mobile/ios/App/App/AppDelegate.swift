import UIKit
import Capacitor

@UIApplicationMain
class AppDelegate: UIResponder, UIApplicationDelegate {

    var window: UIWindow?

    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        // Override point for customization after application launch.
        return true
    }

    func applicationWillResignActive(_ application: UIApplication) {
        // Sent when the application is about to move from active to inactive state. This can occur for certain types of temporary interruptions (such as an incoming phone call or SMS message) or when the user quits the application and it begins the transition to the background state.
        // Use this method to pause ongoing tasks, disable timers, and invalidate graphics rendering callbacks. Games should use this method to pause the game.
    }

    func applicationDidEnterBackground(_ application: UIApplication) {
        // Use this method to release shared resources, save user data, invalidate timers, and store enough application state information to restore your application to its current state in case it is terminated later.
        // If your application supports background execution, this method is called instead of applicationWillTerminate: when the user quits.
    }

    func applicationWillEnterForeground(_ application: UIApplication) {
        // Called as part of the transition from the background to the active state; here you can undo many of the changes made on entering the background.
    }

    func applicationDidBecomeActive(_ application: UIApplication) {
        // Restart any tasks that were paused (or not yet started) while the application was inactive. If the application was previously in the background, optionally refresh the user interface.
    }

    func applicationWillTerminate(_ application: UIApplication) {
        // Called when the application is about to terminate. Save data if appropriate. See also applicationDidEnterBackground:.
    }

    func application(_ application: UIApplication,
                     configurationForConnecting connectingSceneSession: UISceneSession,
                     options: UIScene.ConnectionOptions) -> UISceneConfiguration {
        let config = UISceneConfiguration(name: "Default Configuration",
                                          sessionRole: connectingSceneSession.role)
        config.delegateClass = SceneDelegate.self
        return config
    }
}

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
