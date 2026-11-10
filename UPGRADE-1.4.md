# Debian 升级到 1.4

本次新增了后端接口和数据库表，不能只安装 App；服务器和 App 都要更新。现有账号、密码、信誉分会保留。按原先的 Docker 部署目录操作，下面服务器命令以 root 执行。

## 1. 上传源码包

下载本次新版 library-credit-source.zip。在 Windows PowerShell 执行，将用户名和公网 IP 替换为你的实际值：

```powershell
scp "C:\Users\Administrator\Documents\Codex\2026-11-10\w-m\outputs\library-credit-source.zip" 用户名@公网IP:/tmp/library-credit-source.zip
```

## 2. 先备份数据库

在 Debian 服务器执行：

```bash
cd /opt/library-project/library-credit
mkdir -p /root/library-backups
backup_name="before-1.4-$(date +%Y%m%d-%H%M%S).db"
docker compose exec -T library python backend/backup.py "/tmp/$backup_name"
docker compose cp "library:/tmp/$backup_name" "/root/library-backups/$backup_name"
```

确认命令成功，再继续。

## 3. 替换程序并重新启动

```bash
mkdir -p /opt/library-upgrade-1.4
unzip -o /tmp/library-credit-source.zip -d /opt/library-upgrade-1.4

cp -a /opt/library-upgrade-1.4/library-credit/backend /opt/library-project/library-credit/
cp -a /opt/library-upgrade-1.4/library-credit/web /opt/library-project/library-credit/
cp -a /opt/library-upgrade-1.4/library-credit/Dockerfile /opt/library-project/library-credit/

cd /opt/library-project/library-credit
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:8000/health
```

上面有意保留你的 compose.yaml，所以已经修改为 `0.0.0.0:8000:8000` 的公网端口配置不会被覆盖。数据库存在 Docker 数据卷中，不在被替换的程序目录内。不要执行 `docker compose down -v`。

health 返回 `{"status":"ok"}` 后，用原来的 `http://公网IP:8000` 打开网页。电脑浏览器可按 Ctrl+F5 刷新缓存；Android 安装本次 1.4 APK，再登录。

如失败，查看：

```bash
docker compose logs --tail=100 library
```

## 本次功能

- 信誉分调整：管理员输入目标学工号、增加/减少、分数和原因。结果限制在 0～100；同一请求重试不重复调整，记录操作者、原因及调整前后分数。
- 账号搜索：在账号列表按部分学工号或 UID 搜索；UID 不区分十六进制大小写，支持带冒号、空格、短横线。分页和总数针对搜索结果。
- 删除账号：先查询展示账号，再重新输入完整学工号确认。取消和输入错误都不会发起删除。删除会解绑卡片并撤销登录状态，历史审计与已发生的违规/调整记录保留。最高管理员不可删除，不能删除当前登录账号，普通管理员不能删除其他管理员账号。
- 密码提示：注册、个人修改密码、管理员创建账号、管理员重置密码均提供六档本地强度提示。提示不限制密码设置，不上传额外的密码分析请求；最高档使用动态彩色文字，系统开启减少动态效果时采用静态彩色。

iOS 源码已同步，但仍需在 macOS/Xcode 编译签名；本次没有进行真机验收。
