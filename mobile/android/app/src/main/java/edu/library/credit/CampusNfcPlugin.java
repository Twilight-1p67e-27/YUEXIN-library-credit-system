package edu.library.credit;

import android.nfc.NfcAdapter;
import android.os.Handler;
import android.os.Looper;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "CampusNfc")
public class CampusNfcPlugin extends Plugin {
    private PluginCall pending;
    private NfcAdapter adapter;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable timeout = () -> finish(null, "读卡超时，请重试");
    @PluginMethod public void read(PluginCall call) {
        getActivity().runOnUiThread(() -> {
            if (pending != null) { call.reject("正在读卡，请稍候"); return; }
            adapter = NfcAdapter.getDefaultAdapter(getContext());
            if (adapter == null || !adapter.isEnabled()) { call.reject("此手机未提供 NFC 或 NFC 未开启"); return; }
            pending = call;
            try {
                adapter.enableReaderMode(getActivity(), tag -> {
                    StringBuilder uid = new StringBuilder();
                    for (byte b : tag.getId()) uid.append(String.format("%02X", b & 0xff));
                    getActivity().runOnUiThread(() -> finish(uid.toString(), null));
                }, NfcAdapter.FLAG_READER_NFC_A | NfcAdapter.FLAG_READER_SKIP_NDEF_CHECK, null);
                handler.postDelayed(timeout, 30000);
            } catch (Exception e) { finish(null, "无法开启 NFC：" + e.getMessage()); }
        });
    }
    private void finish(String uid, String error) {
        handler.removeCallbacks(timeout);
        if (adapter != null) adapter.disableReaderMode(getActivity());
        PluginCall call = pending; pending = null;
        if (call == null) return;
        if (error != null) call.reject(error);
        else { JSObject data = new JSObject(); data.put("uid", uid); call.resolve(data); }
    }
    @Override protected void handleOnPause() { if (pending != null) finish(null, "读卡已中止，请保持 App 在前台"); }
}
