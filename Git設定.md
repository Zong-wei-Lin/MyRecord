# Git 新手入門

這份筆記幫你從零開始學 Git，從設定、工作流程到最常用指令都寫得清楚。適合剛開始學 Git 的你。

## 1. 先設定你的 Git 身份

在電腦上安裝好 Git 之後，第一件事是設定你的使用者名稱與 Email。這會出現在每一次提交記錄中。

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

如果要確認設定是否成功：

```bash
git config --global --list
```

## 2. Git 的基本觀念

- Git 不是單純備份檔案，它是在記錄檔案變化的歷史。
- 本地資料夾可以變成一個 Git 倉庫。
- `commit` 是將暫存內容存進歷史紀錄。
- `remote` 是遠端倉庫，例如 GitHub，用來備份和分享。

## 3. 最有效的 5 個常用指令

這 5 個指令掌握好，就能處理 80% 的個人開發需求。

1. `git init`
   - 作用：在目前資料夾內建立 Git 倉庫，開始追蹤檔案變化。
   - 遊戲比喻：開啟一個新的遊戲存檔欄位。

2. `git status`
   - 作用：檢查目前檔案狀態。會告訴你哪些檔案已修改、哪些檔案在暫存區內。
   - 遊戲比喻：查看目前的任務進度和背包狀況。

3. `git add <檔案>`
   - 作用：把指定的檔案加入暫存區，準備提交。
   - 遊戲比喻：把想放進存檔的東西，先放進購物車。

4. `git commit -m "訊息"`
   - 作用：正式提交暫存區內容，並附上這次存檔的說明文字。
   - 遊戲比喻：按下「確認存檔」，並寫下備忘錄。

5. `git log`
   - 作用：查看過去所有提交歷史紀錄。
   - 遊戲比喻：打開舊的存檔列表，看自己玩到哪了。

## 4. 一個完整的基本流程

假設你在新的資料夾裡工作，從初始化開始：

```bash
mkdir my-project
cd my-project
git init
```

建立一個檔案：

```bash
echo "Hello Git" > README.md
```

查看狀態：

```bash
git status
```

加入暫存：

```bash
git add README.md
```

提交：

```bash
git commit -m "Add README"
```

查看提交歷史：

```bash
git log
```

## 5. 如果你要連到 GitHub

1. 在 GitHub 上建立一個新的 repository。
2. 把遠端倉庫加進本地 repo：

```bash
git remote add origin https://github.com/你的帳號/你的倉庫.git
```

3. 推送到 GitHub：

```bash
git push -u origin main
```

> 注意：如果你的預設分支不是 `main`，請改成 `master` 或你自己的分支名稱。

## 5.1 origin 與 main 是什麼意思

- `origin`
  - 是遠端倉庫（remote）的名稱別名。
  - 通常代表你在 GitHub、GitLab 或其他遠端平台上的那個倉庫。
  - 它不是 Git 固定的名字，但大多數人和 Git 會預設使用 `origin`。

- `main`
  - 是分支（branch）的名稱。
  - 通常代表主要開發分支，也就是你常用的「主要進度」分支。
  - 舊專案有時候叫 `master`，現在新專案多半用 `main`。

簡單比喻：

- `origin` = 遠端伺服器上的遊戲存檔槽位置
- `main` = 你目前主要使用的遊戲進度分支

常見命令：

- `git push origin main`：把本地 `main` 分支推送到遠端 `origin`
- `git pull origin main`：從遠端 `origin` 的 `main` 分支抓最新更新

## 6. 常見概念小整理

- `working directory`：你現在編輯檔案的資料夾。
- `staging area`：你準備提交的檔案清單。
- `commit history`：已經存檔的版本紀錄。
- `remote`：遠端儲存庫，例如 GitHub。
- `branch`：分支，讓你可以同時做多個功能開發。

## 7. 你可以先練習的 3 個指令

- `git diff`：看檔案差異。
- `git checkout -- <檔案>`：還原檔案到最後一次提交的狀態。
- `git branch`：查看分支或建立新分支。

---

這樣你就有一個從入門到基本實作的 Git 筆記。練習 `init`、`status`、`add`、`commit`、`log` 這 5 個指令，其他概念慢慢補就好。

