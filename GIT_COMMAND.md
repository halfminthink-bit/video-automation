# Git操作まとめ - Claude Codeと連携したワークフロー

## 📋 基本的な流れ

```
Claude Codeが変更 → リモートにプッシュ → ローカルで取得 → PRを作成 → マージ → ローカルに反映
```

---

## 🔄 日常的によく使うコマンド

### 1. 最新状態を確認・取得

```powershell
# リモートの最新情報を取得（ローカルは変更しない）
git fetch origin

# 現在のブランチを確認
git branch

# 現在の状態を確認
git status

# リモートブランチ一覧を確認
git branch -r
```

### 2. mainブランチを最新にする

```powershell
# mainに移動
git checkout main

# リモートの最新を取得してマージ
git pull origin main

# 確認
git log --oneline -5
```

---

## 🚀 Claude Codeが変更を作った後の流れ

### パターンA: Claude Codeが新しいブランチを作成した場合

```powershell
# 1. リモートの最新情報を取得
git fetch origin

# 2. Claude Codeが作ったブランチを確認
git branch -r | findstr claude/

# 3. そのブランチをローカルにチェックアウト
git checkout -b ブランチ名 origin/ブランチ名

# 例:
git checkout -b claude/fix-something-123 origin/claude/fix-something-123

# 4. PRを作成
gh pr create --fill

# 5. GitHubでマージ後、mainに戻って最新化
git checkout main
git pull origin main
```

### パターンB: 既存のブランチに追加コミットがある場合

```powershell
# 1. そのブランチに移動
git checkout ブランチ名

# 2. リモートから最新を取得
git pull origin ブランチ名

# 3. 変更内容を確認
git log --oneline -3

# 4. 必要ならプッシュ（通常は自動で反映されている）
git push origin ブランチ名
```

---

## 📝 PRの作成方法（3つの方法）

### 方法1: GitHub CLI（最も簡単・推奨）

```powershell
# ブランチにいる状態で
gh pr create --fill
```

### 方法2: ブラウザのURL

```
https://github.com/halfminthink-bit/video-automation/compare/main...ブランチ名
```

### 方法3: GitHubのブランチページから

```
https://github.com/halfminthink-bit/video-automation/branches
```
右側の「New pull request」ボタンをクリック

---

## 🧹 マージ後のクリーンアップ

```powershell
# 1. mainに戻って最新化
git checkout main
git pull origin main

# 2. ローカルのマージ済みブランチを削除
git branch -d ブランチ名

# 複数削除する場合
git branch -d claude/fix-something-123
git branch -d claude/another-fix-456

# 3. リモートのブランチも削除（任意）
git push origin --delete ブランチ名
```

---

## ⚠️ よくあるトラブルと解決方法

### 「Your branch is behind」と表示される

```powershell
# リモートの方が新しいので、取得してマージ
git pull origin ブランチ名
```

### 「rejected」でプッシュできない

```powershell
# まずpullしてから再度push
git pull origin ブランチ名
git push origin ブランチ名
```

### ブランチが見つからない

```powershell
# リモートから最新情報を取得
git fetch origin

# リモートブランチを確認
git branch -r | findstr ブランチ名
```

### PRが見えない・作れない

```powershell
# ブランチが正しくプッシュされているか確認
git ls-remote --heads origin | findstr ブランチ名

# なければプッシュ
git push origin ブランチ名
```

---

## 🎯 完全なワークフローの例

```powershell
# ===== Claude Codeが変更を作った後 =====

# 1. 最新情報を取得
git fetch origin

# 2. Claude Codeのブランチを確認
git branch -r | findstr claude/

# 3. そのブランチをチェックアウト
git checkout -b claude/fix-subtitle-123 origin/claude/fix-subtitle-123

# 4. 変更内容を確認（任意）
git log --oneline -3
git show HEAD

# 5. PRを作成
gh pr create --fill

# ===== GitHubでマージボタンを押した後 =====

# 6. mainに戻る
git checkout main

# 7. 最新を取得
git pull origin main

# 8. 不要なブランチを削除
git branch -d claude/fix-subtitle-123

# 9. 作業完了！次のタスクへ
```

---

## 📌 覚えておくべき重要なコマンド（ベスト5）

```powershell
# 1. リモートの最新情報を取得
git fetch origin

# 2. mainを最新にする
git checkout main && git pull origin main

# 3. Claude Codeのブランチをチェックアウト
git checkout -b ブランチ名 origin/ブランチ名

# 4. PRを作成
gh pr create --fill

# 5. 不要なブランチを削除
git branch -d ブランチ名
```

---

## 🔧 便利なエイリアス設定（任意）

PowerShellのプロファイルに追加すると便利：

```powershell
# プロファイルを開く
notepad $PROFILE

# 以下を追加
function git-sync {
    git checkout main
    git pull origin main
}

function git-cleanup {
    git branch --merged | Where-Object { $_ -notmatch "main" } | ForEach-Object { git branch -d $_.Trim() }
}

# 使い方
git-sync      # mainを最新にする
git-cleanup   # マージ済みブランチを削除
```

---

これで基本的なGit操作は網羅できているはずです！何か不明点があれば聞いてください 🚀