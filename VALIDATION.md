# 验证记录

版本：1.1。日期：2026-11-10。环境：Windows，Python 3.12，Node.js；未连接实物校园卡或单片机。

- 后端：`python -m pytest tests -q`，12 项全部通过。
- 并发验证：同一事件 8 个并发请求只有 1 次扣分，最终 90 分。
- 网页：使用 Playwright + 本机 Chrome 验证注册、登录、管理员列表、资料修改、退出；无 JavaScript 页面错误。
- 响应式：1280px 桌面与 390px 手机视口，未发现水平溢出；截图为 preview-desktop.png、preview-mobile.png。修改退出密码框清理后复测登录、列表、资料与退出通过。
- SQLite 在线备份：备份后 PRAGMA integrity_check 返回 ok。
- 手机依赖：Capacitor Android/iOS/core/CLI 8.6.0，npm audit 报告 0 vulnerabilities。
- 网页脚本：node --check 通过；原生工程 cap sync 成功。
- Android：使用 Microsoft JDK 21.0.13 + SDK 36，Gradle assembleDebug 成功（93 tasks），已生成 library-credit-debug.apk。尚未使用真机 NFC 验证。
- APK 元数据检查通过：包名 edu.library.credit，最低 Android API 24，target/compile API 36，已声明 NFC 权限且 NFC 硬件为可选。尝试模拟器安装验收时 ADB 显示 unauthorized，因此未完成安装启动验证；不将编译成功视为运行验收。

本机 Android Studio 的 JBR 25 与 Gradle 8.14.3 不兼容，构建改用 JDK 21。本机 Windows 的 Unix-domain socket 还引发 Gradle 回环连接错误，构建进程临时设置 `JAVA_TOOL_OPTIONS=-Djdk.net.unixdomain.tmpdir=C:/nonexistent-library-build-tmp`（该目录不存在，使 JDK 回退 TCP），解决后完成编译；此设置未修改系统全局环境，也非服务端部署要求。

## 尚未验证

- iOS 尚未在 macOS/Xcode 上编译、签名或真机安装。
- Android/iOS 真机 NFC、具体 SAK20 校园卡的兼容性、实物 UID 字节顺序，均需现场联调。
- Linux/群晖容器实际部署、HTTPS 证书与学校网络、全校规模负载，未在目标环境验收。
- 占座检测算法、传感器、硬件固件和 220V 继电器执行电路不在此软件交付范围内。

## 1.1 更新验证

- 已移除注册表单、API 模型、设备注册、部署配置、命令行工具中的注册辅助码机制；旧数据库启动时清理弃用表。
- 新增测试覆盖：五个指定账号自动授权、管理员代建账号（指定或自动生成密码）、最高管理员授权与撤权、普通用户/普通管理员越权拦截、撤权后现有会话权限立即变化、重启保留角色、旧数据库升级。
- Playwright + Chrome 新版操作验收通过：直接注册最高管理员、自动显示最高权限界面、仅 UID/学工号代建账号并生成密码、新账号登录、授予管理员、普通管理员不显示角色管理、移除管理员后刷新隐藏管理界面、退出清理初始密码展示；无页面脚本错误，390px 宽度无横向溢出。
- 新版 Android assembleDebug 成功：versionCode 2 / versionName 1.1，APK 元数据检查通过。没有新增真机 NFC 或 iOS 构建验证。

## 1.2 管理中心界面

- 管理功能已从个人资料页拆出，改为入口按钮与独立管理视图。
- 网格功能选择，每次只显示一个工作面板；用户数据使用六列表格。
- Playwright + Chrome 验证通过：管理入口、返回个人中心、四项功能切换、表格列、代建账号、权限增删、普通管理员隐藏权限入口、撤权后关闭管理视图、390px 布局及退出清理；无页面脚本错误。
- Android/iOS 网页资源同步更新；真机 NFC 和 iOS 签名验证范围不变。
- Android 1.2（versionCode 3）重新编译成功，APK 元数据检查通过。

## 1.3 HTTP 手机连接

- Android/iOS 支持填写 HTTP 公网 IPv4 与端口；保留 HTTPS 支持。
- 手机 API 请求改走原生 CapacitorHttp，包含 JSON 正文、Bearer 令牌、连接和读取超时；网页保留 fetch 路径。
- Android 配置 cleartextTrafficPermitted 与 usesCleartextTraffic；iOS 配置根级 NSAppTransportSecurity / NSAllowsArbitraryLoads。同步修复 NFCReaderUsageDescription 原先误放在 scene 字典内的问题，现位于根字典。
- 使用 Playwright 模拟 Capacitor 原生桥接，并将请求交给真实 HTTP 测试后端，验证连接、注册、登录、修改资料、管理员表格、退出、401 处理与普通浏览器 HTTP 分支均通过。此测试不等于真实 Android/iOS 网络栈验收。
- iOS plist 结构检查通过；Android 1.3（versionCode 4）assembleDebug 成功，APK 中明文网络配置检查通过。
- 尚未新增真机 HTTP、NFC 或 macOS/iOS 编译签名验证。

## 1.4 管理功能与密码提示

- 后端 17 项测试通过：新增搜索参数/分页/特殊字符、信誉分上下限及权限、重复与并发调整、删除确认与绑定检查、会话撤销、卡片解绑、历史记录保留、管理员删除权限。
- Playwright + Chrome 分别验证网页 fetch 和模拟原生 CapacitorHttp 桥接到真实 HTTP 后端：创建弱密码账号、手工减少/增加分数、UID 搜索和清空、空搜索结果、删除取消/错误确认/正确删除、退出及 390px 布局，均通过，无页面脚本错误。
- 四处新密码输入均验证提示；六档文字及最高档 CSS 动画和背景位置实时变化验证通过。密码强度为本地启发式提示，不是密码安全保证，不改变后端密码规则。
- 模拟桥接测试不能替代真实手机网络与系统对话框验收。本次没有新增真机 NFC 或 iOS 编译签名验证。
- Android 1.4（versionCode 5）最终 assembleDebug 成功，APK 版本检查通过；HTTP 支持保留。
