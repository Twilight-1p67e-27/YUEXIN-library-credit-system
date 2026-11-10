# 阅信 · 图书馆信用管理系统

这是一套可自行部署的初版：FastAPI + SQLite 后端、响应式网页、Capacitor Android/iOS 原生工程（Java/Swift NFC 插件）。五个指定学工号在注册时由后端自动授予管理员权限，2026211348 具有最高权限。单机部署支持 Linux、Debian、带 Container Manager 的群晖；无 Docker 时可使用 Python 启动。SQLite 适合单服务器，数据库文件应保存在本机磁盘，不要放在 SMB/NFS 上。

## 先启动体验

在项目根目录（本 README 所在目录）执行：

```sh
python -m venv .venv
# Linux
. .venv/bin/activate
# Windows 则执行 .venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

浏览器访问 http://127.0.0.1:8000 。API 交互文档位于 `/docs`。默认数据库为当前工作目录下的 `data/library.db`。网页与 API 同源，无需额外构建。界面中的学校服务器地址填写完整的 `https://域名:端口` 或 `http://公网IP:端口`，不带路径；连接其他学校时会退出当前账号。

### 注册与管理员

用户输入学工号、校园卡 UID 和密码即可直接注册，昵称、邮箱可选，初始信誉分 100。学工号和 UID 各自唯一，不增加身份校验步骤。

以下五个学工号在首次注册时自动获得管理员权限：2026211348、2026210633、2026210635、2026210668、2026210666。请按项目安排在对外开放前注册好这些账号。没有预置密码。

所有管理员可以在管理界面手动创建账号：输入 UID、学工号，可选填写初始密码、昵称、邮箱。密码留空时自动生成，在创建成功后显示一次，数据库仍只保存哈希。管理员代建指定名单中的账号时，也会按相同规则授予管理员权限。

2026211348 是最高管理员，额外拥有“权限管理”界面，可给其他任意已注册账号授予或移除管理员权限，包括上述初始管理员。权限变更在下一次 API 请求时生效，重启不会重新授予被移除的权限；最高管理员自己的权限不可修改。普通管理员不能管理其他账号的角色。

### 管理中心界面

管理员登录后，在个人中心点击“管理中心”进入独立界面。功能入口为网格按钮，分别切换用户列表、创建账号、重置密码、权限管理（仅最高管理员显示）；同一时间只展示一个功能。1.4 新增信誉分调整、二次确认删除账号、账号列表学工号/UID 搜索，以及所有新密码输入处的六档强度提示（不限制密码）。用户数据以表格展示，手机上可左右滑动查看全部列。点击“返回个人中心”回到信誉分与个人资料页。返回或退出时清理已展示的初始密码。

### 配置设备密钥

在同一项目目录、相同 DB_PATH 环境中执行：

```sh
python backend/manage.py device desk-001
# 用于线下开户注册的终端
python backend/manage.py device enrollment-001 --enrollment
python backend/manage.py revoke-device desk-001
```

## Debian / 群晖部署

安装 Docker / Compose；群晖在 Container Manager 中选择本目录的 `compose.yaml` 建立项目：

```sh
docker compose up -d --build
docker compose exec library python backend/manage.py device desk-001
```

默认只映射宿主机 `127.0.0.1:8000`。在群晖反向代理或 Nginx/Caddy 中配置 HTTPS 域名并转发到该地址。若反向代理也在容器内，可通过同一 Docker 网络访问 `library:8000`。网页、App、设备可使用该 HTTPS 域名。若需要公网 IP 直接访问，把 compose.yaml 中端口映射改为 `0.0.0.0:8000:8000`，执行 `docker compose up -d`，并在云平台安全组放行 TCP 8000。随后访问 `http://公网IPv4:8000`，App 填同一个地址。群晖型号若不支持容器，可在支持 Python 3.12 的环境按上述方式运行并配置服务守护。没有实际在群晖硬件或 Linux 容器上运行过本项目。

配置项：

| 环境变量 | 默认 | 用途 |
|---|---|---|
| DB_PATH | data/library.db（容器 /data/library.db） | 数据库路径 |
| CREDIT_THRESHOLD | 60 | 分数大于等于此值允许供电，建议 0–100 |
| CORS_ORIGINS | http://localhost,https://localhost,capacitor://localhost | App WebView 来源；多个用逗号分隔 |

独立托管网页时，将网页的准确来源加入 CORS_ORIGINS。HTTPS 网页不能访问 HTTP API。1.3 起 Android/iOS App 同时接受 HTTP 和 HTTPS，可直接填写 `http://公网IPv4:8000`，不需要域名或证书。原生网络请求使用 CapacitorHttp，Android 已配置明文网络策略，iOS 已配置 ATS 例外。HTTPS 仍按系统信任链验证证书。HTTP 会明文传输密码和登录令牌。

备份使用 SQLite 的在线备份 API 或停止服务后复制数据库及相关 WAL 文件；运行中只复制主 db 文件可能丢数据。容器命名卷 `library-data` 应纳入备份。升级前备份。1.1 版本启动时自动清理旧版本弃用的注册辅助表，保留用户、分数、设备和审计数据；后续结构变更需配套迁移。日志和数据库限制服务器运维人员访问。

提供在线一致性备份命令 `python backend/backup.py /安全目录/新的备份.db`，目标文件不能已存在。使用时须设置与运行服务相同的 DB_PATH。非容器部署示例位于 `deploy/library-credit.service`：将项目安装到 `/opt/library-credit`，创建 `library` 系统用户及其可写的 `/var/lib/library-credit`，安装虚拟环境和依赖，再把单元文件安装到 `/etc/systemd/system/` 并执行 `systemctl enable --now library-credit`。Caddy HTTPS 反向代理示例位于 `deploy/Caddyfile`，需替换实际域名。

## 手机 App

Android 和 iOS 共用网页功能，通过原生 NFC 插件读取 UID，保持读卡原始字节顺序，转为大写十六进制，不转换为卡面十进制编号。支持输入 4/7/10 字节 UID（8/14/20 位十六进制），可带空格、冒号或短横线。设备端必须使用相同顺序和格式。SAK 0x20 不是唯一的卡片型号证明，需用实物确认；此系统不读取加密扇区，不复制卡片。

```sh
cd mobile
npm ci
npm run sync
# 工程已经生成并配置过，无需再次 cap add
npx cap open android
```

Android 使用 Android Studio 自带 JDK（Capacitor 8 / SDK 36，JDK 21+；若 Gradle 不支持过新的 JDK，应切换到 JDK 21）。命令行构建：

```sh
cd android
./gradlew assembleDebug
```

Windows 使用 `gradlew.bat`。已编译的新版调试安装包为交付目录中的 `library-credit-debug.apk`。发行版需自行配置签名并保管 keystore。调试 APK 不能替代正式发布签名。

iOS 必须在 macOS + Xcode 构建，Windows 无法生成可安装的签名 IPA：

```sh
cd mobile
npm ci
npm run sync
npx cap open ios
```

Xcode 中设置自己的 Team、唯一 Bundle ID，确认 Near Field Communication Tag Reading capability 与 `App.entitlements` 的 TAG 权限，使用真机编译与签名。原生类已包含在 AppDelegate.swift 的编译单元中，Main.storyboard 使用 CampusBridgeViewController；源模板 Nfc.swift 不要再次手动加入编译，以免重复定义。

**iPhone 无法保证读取 MIFARE Classic 卡**，Apple 官方说明该类型不受支持；Android 也取决于卡片和手机。App 保留手输 UID，用户可在学校读卡终端获取 UID，再完成注册。无法通过软件承诺所有 SAK20 卡均可在 iOS 上读卡。尚无实物校园卡，未进行真机 NFC 验证。

原生配置脚本 `node configure-native.mjs` 可在重新生成工程后应用权限与桥接设置；日常修改网页只需 `npm run sync`。网页浏览器不启用 Web NFC（PC 不支持；Web NFC 也不适用于任意校园卡 UID）。

## 单片机接口

设备密钥由部署者签发，保存在设备安全配置区，不得嵌入网页/App。所有设备 API 都需 `X-Device-Key` 请求头；使用 HTTPS 时不要关闭证书验证。

查分及是否允许使用：

```http
POST /api/device/lookup
X-Device-Key: <设备密钥>
Content-Type: application/json

{"uid":"04A1B2C3"}
```

```json
{"registered":true,"credit":100,"allowed":true,"threshold":60,"valid_for_seconds":15}
```

未注册卡返回 `registered=false, credit=null, allowed=false`。终端应在插卡时查分、定时续查，拔卡立即断开使能；超时、网络错误、无卡、拒绝访问、allowed=false 均默认不供电。响应有效期 15 秒是终端必须实现的约束，后端不能直接切断继电器。不要将手机登录状态用作座位授权。220V 执行部分需使用合适的隔离、额定负载和认证模块，由具备资质人员实施；这里没有设计市电接线或硬件固件。

上报一次已确认的占座违规：

```http
POST /api/device/violations
X-Device-Key: <设备密钥>
Content-Type: application/json

{"uid":"04A1B2C3","event_id":"desk-001-20261110-000001","points":10,"reason":"占座检测规则确认的事件"}
```

`event_id` 必须全局唯一并在断网重试时保持不变。重复相同事件返回原扣分结果，不重复扣分；同 ID 不同内容返回 409。扣分与事件记录在同一数据库事务内，分数不低于 0。传感器算法、误判申诉、人工恢复信誉分和座位占用会话尚未实现；接口按终端提交的 UID 扣分，终端应确保其对应发生违规时的实际持卡人。

线下注册备用接口 `POST /api/device/register`，请求体与 `/api/register` 完全相同，且必须使用带 enrollment 权限的设备密钥。终端可以通过键盘/屏幕输入学工号、密码并读卡，不需要手机和网页；仍需联网到服务器，当前不实现断网注册排队。

用户接口：`POST /api/register`、`POST /api/login`、`GET/PATCH /api/me`、`POST /api/me/password`、`POST /api/logout`。登录后通过 `Authorization: Bearer <token>` 访问。新增管理接口：`POST /api/admin/users`（student_id、uid 必填，password、nickname、email 可选），`PATCH /api/admin/users/{学工号}/admin`（正文 `{"admin":true}` 或 `{"admin":false}`，仅最高管理员可用）。其余管理接口：`GET /api/admin/users?offset=0&limit=100`（最多 200），`POST /api/admin/users/{学工号}/password`（正文 new_password、admin_password）。管理员可对任意用户逐个重置密码，包括其他管理员；没有“一键将全校密码设为相同值”的入口。

## 密码与身份边界

密码不设复杂度要求，但不可为空，最大 1024 字符用于资源限制。客户端按用户填写的 HTTP/HTTPS 地址传输用户输入；HTTP 不加密传输，后端仍仅存储带盐的 Argon2id 哈希，登录时验证该哈希，不保存明文。不要把固定的客户端哈希直接当作登录密码协议，它会成为可重放的凭据。登录令牌只保存在客户端内存，关闭/刷新后需重新登录，服务器只保存令牌摘要，24 小时过期。修改密码或管理员重置会撤销该用户所有令牌。

注册和登录按连接来源限速；反向代理下当前有意不信任 forwarded headers，因此用户可能共享代理来源配额。大规模部署需在可信代理上配置细粒度限流，并按实际并发调整，当前不是面向全校高负载的性能验收结果。本项目按自助注册、指定学工号自动授权的模式运行，不对接学校身份认证。

## 验证

```sh
pip install pytest==9.2.0 httpx==0.28.1
python -m pytest tests -q
```

覆盖：Argon2id 存储、UID 唯一性、指定账号自动授权、最高管理员权限管理与越权拦截、管理员代建账号、旧库升级、密码重置/修改撤销登录、设备密钥、未知卡拒绝、重复事件不重复扣分、事件冲突、信誉分下限、线下注册权限、资料修改、退出和限流。验收记录见 `VALIDATION.md`。

参考：[Apple Core NFC 兼容说明](https://developer.apple.com/videos/play/wwdc2019/715/)、[Android NFC 技术支持](https://developer.android.com/develop/connectivity/nfc/advanced-nfc)、[Capacitor 环境要求](https://capacitorjs.com/docs/getting-started/environment-setup)。

升级已部署的 Debian 服务器见 `UPGRADE-1.4.md`，该步骤保留公网端口配置和原数据库。新增接口：`POST /api/admin/users/{学工号}/credit`（request_id、delta、reason）、`POST /api/admin/users/{学工号}/delete`（confirm_student_id、uid）；账号列表支持 q 搜索参数。
