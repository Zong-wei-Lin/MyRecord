# SSH 重點

## 參考資料

- 原始教學：<https://blog.kyomind.tw/vm-ssh-setup/\>

## 1. 產生 SSH 金鑰

```bash
ssh-keygen -t rsa -f ~/.ssh/<檔名> -C "your_username"
```

參數說明：

- `-t`：指定金鑰類型（例如 `rsa`、`ed25519`）
- `-f`：指定輸出的金鑰檔名
- `-C`：指定註解（通常填寫使用者名稱或 Email）

建議使用較新且更安全的金鑰類型：

```bash
ssh-keygen -t ed25519 -f ~/.ssh/<檔名> -C "your_username"
```

生成後會得到兩個檔案：

- `~/.ssh/<檔名>`：私鑰
- `~/.ssh/<檔名>.pub`：公鑰

## 2. 私鑰與公鑰位置

- 私鑰（`<檔名>`）放在本機端（用戶端）
- 公鑰（`<檔名>.pub`）放在伺服器端

## 3. 設定私鑰權限

```bash
chmod 600 ~/.ssh/<檔名>
```

> 私鑰權限必須設定為 `600`，否則 SSH 會拒絕使用。

## 4. 設定 SSH config

編輯：

```bash
vim ~/.ssh/config
```

範例配置：

```text
Host gcp
    HostName <VM 的實際 IP>
    User kyo
    IdentityFile ~/.ssh/gcp
```

## 5. 使用方式

儲存後，可以直接執行：

```bash
ssh gcp
```

以上即為 SSH 金鑰產生與 `~/.ssh/config` 設定的重點。
