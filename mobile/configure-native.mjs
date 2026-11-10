// Run once after cap add. Re-running is safe.
import {readFileSync as read,writeFileSync as write,copyFileSync as copy} from 'node:fs';
const edit=(p,fn)=>write(p,fn(read(p,'utf8')));
const dir='android/app/src/main/';
copy('CampusNfcPlugin.java',dir+'java/edu/library/credit/CampusNfcPlugin.java');
edit(dir+'java/edu/library/credit/MainActivity.java',s=>`package edu.library.credit;
import android.os.Bundle;
import com.getcapacitor.BridgeActivity;
public class MainActivity extends BridgeActivity {
 @Override public void onCreate(Bundle state) {
  registerPlugin(CampusNfcPlugin.class);
  super.onCreate(state);
 }
}
`);
edit(dir+'AndroidManifest.xml',s=>s.includes('android.permission.NFC')?s:s.replace('<application','<uses-permission android:name="android.permission.NFC"/><uses-feature android:name="android.hardware.nfc" android:required="false"/><application'));
edit('ios/App/App/AppDelegate.swift',s=>s.includes('class CampusNfcPlugin')?s:s+'\n'+read('Nfc.swift','utf8'));
edit('ios/App/App/Base.lproj/Main.storyboard',s=>s.replace('customClass="CAPBridgeViewController" customModule="Capacitor"','customClass="CampusBridgeViewController" customModule="App"'));
// Keep permission declarations in the root dictionary, not a scene configuration.
edit('ios/App/App/Info.plist',s=>{
 s=s.replace(/<key>NFCReaderUsageDescription<\/key>\s*<string>[^<]*<\/string>/g,'');
 if(!s.includes('<key>NSAppTransportSecurity</key>'))s=s.replace(/<\/dict>\s*<\/plist>/,'<key>NSAppTransportSecurity</key><dict><key>NSAllowsArbitraryLoads</key><true/></dict></dict></plist>');
 if(!s.includes('<key>NSLocalNetworkUsageDescription</key>'))s=s.replace(/<\/dict>\s*<\/plist>/,'<key>NSLocalNetworkUsageDescription</key><string>连接你填写的图书馆服务器</string></dict></plist>');
 return s.replace(/<\/dict>\s*<\/plist>/,'<key>NFCReaderUsageDescription</key><string>读取校园卡 UID 以绑定学工号</string></dict></plist>');
});
write('ios/App/App/App.entitlements',`<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict><key>com.apple.developer.nfc.readersession.formats</key><array><string>TAG</string></array></dict></plist>`);
edit('ios/App/App.xcodeproj/project.pbxproj',s=>s.includes('CODE_SIGN_ENTITLEMENTS')?s:s.replaceAll('CODE_SIGN_STYLE = Automatic;','CODE_SIGN_STYLE = Automatic;\n\t\t\t\tCODE_SIGN_ENTITLEMENTS = App/App.entitlements;'));
console.log('Native NFC configured. iOS requires signing and NFC capability in Xcode.');

edit(dir+'AndroidManifest.xml',s=>{
 s=s.replace(/\sandroid:usesCleartextTraffic="[^"]*"/g,'').replace(/\sandroid:networkSecurityConfig="[^"]*"/g,'');
 return s.replace('<application','<application android:usesCleartextTraffic="true" android:networkSecurityConfig="@xml/network_security_config"');
});
write(dir+'res/xml/network_security_config.xml',`<?xml version="1.0" encoding="utf-8"?><network-security-config><base-config cleartextTrafficPermitted="true"><trust-anchors><certificates src="system"/></trust-anchors></base-config></network-security-config>`);
console.log('HTTP enabled for native Android/iOS requests.');
