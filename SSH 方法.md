#SSH 重點

參考這網址
https://blog.kyomind.tw/vm-ssh-setup/



ssh-keygen -t rsa -f ~/.ssh/檔名 -C "your_username"
# -t 指定類型
# -f 指定檔名
# -C 指定註解
rsa 可改成 ed25519 (較新較安全)
# ssh-keygen -t ed25519 -f ~/.ssh/檔名 -C "your_username"
# 產生公私鑰
# 會產生兩個檔案
# 檔名 (私鑰)
# 檔名.pub (公鑰)
# 私鑰要放在用戶端
# 公鑰要放在伺服器端
# 私鑰要設定權限 600
chmod 600 ~/.ssh/檔名
# 設定 ssh config
vim ~/.ssh/config
Host gcp
    HostName <VM 的實際 ip>
    User kyo
    IdentityFile ~/.ssh/gcp
