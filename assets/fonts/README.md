# YouTubeサムネイル用フォント

このディレクトリには、YouTubeサムネイル生成に最適な日本語フォントを配置します。

## 推奨フォント（無料・商用利用可）

### 1. 源暎きわみゴ (GenEi Kiwami Gothic) ⭐⭐⭐⭐⭐

**特徴**: 超極太でインパクト大、視認性最高

**ダウンロード先**: https://okoneya.jp/font/download.html

**ファイル名**: `GenEiKiwamiGothic-EB.ttf`

---

### 2. キルゴU (Kill Gothic U) ⭐⭐⭐⭐⭐

**特徴**: ゴツゴツした太めのウェイト、サムネイル定番

**ダウンロード先**: https://forest.watch.impress.co.jp/library/software/killgothic_u/

**ファイル名**: `GN-KillGothic-U-KanaNB.ttf` （最も太いウェイト）

---

### 3. コーポレート・ロゴ (Corporate Logo) ⭐⭐⭐⭐

**特徴**: YouTube黎明期から人気、汎用性が高い

**ダウンロード先**: https://logotype.jp/corporate-logo-font-dl.html

**ファイル名**: `Corporate-Logo-ver3.otf`

---

### 4. デラゴシック (Dela Gothic One) ⭐⭐⭐⭐

**特徴**: 超極太フォルム、インパクト大

**ダウンロード先**: https://fonts.google.com/specimen/Dela+Gothic+One

**ファイル名**: `DelaGothicOne-Regular.ttf`

---

### 5. 零ゴシック (Rei Gothic) ⭐⭐⭐⭐

**特徴**: ガラスのように割れた加工、最近人気

**ダウンロード先**: https://goodfreefonts.com/rei-gothic/

**ファイル名**: `ReiGothic-Regular.ttf`

---

## インストール方法

### 方法1: このディレクトリに直接配置（推奨）

1. 上記のダウンロード先から各フォントをダウンロード
2. このディレクトリ (`assets/fonts/`) に配置
3. Phase 8が自動的に検出して使用します

```
assets/fonts/
├── GenEiKiwamiGothic-EB.ttf
├── GN-KillGothic-U-KanaNB.ttf
├── Corporate-Logo-ver3.otf
├── DelaGothicOne-Regular.ttf
└── ReiGothic-Regular.ttf
```

### 方法2: システムフォントとしてインストール

フォントをダウンロードせずに、システムにインストールされている日本語フォント（Noto Sans CJK JP Boldなど）を使用することもできます。

---

## 優先順位

Phase 8は以下の優先順位でフォントを検索します：

1. **assets/fonts/内のフォント** （源暎きわみゴ、キルゴUなど）
2. **システムフォント** （Noto Sans CJK JP Bold）
3. **デフォルトフォント** （フォールバック）

---

## ライセンス情報

| フォント名 | ライセンス | 商用利用 | 再配布 |
|-----------|----------|---------|--------|
| 源暎きわみゴ | SIL OFL 1.1 | ✅ 可 | ✅ 可 |
| キルゴU | M+ FONT LICENSE | ✅ 可 | ✅ 可 |
| コーポレート・ロゴ | SIL OFL 1.1 | ✅ 可 | ✅ 可 |
| デラゴシック | SIL OFL 1.1 | ✅ 可 | ✅ 可 |
| 零ゴシック | 要確認 | ✅ 可 | 要確認 |

**すべて商用利用可能で無料です。**

---

## トラブルシューティング

### フォントが見つからない場合

Phase 8実行時に以下の警告が表示される場合：

```
⚠ Japanese font not found, using default font
```

**解決方法**:

1. 推奨フォントをダウンロードして `assets/fonts/` に配置
2. または、システムに Noto Sans CJK JP をインストール:

```bash
# Ubuntu/Debian
sudo apt-get install fonts-noto-cjk

# macOS
brew install --cask font-noto-sans-cjk-jp
```

---

## 参考リンク

- [YouTubeで使われているフォント調査](https://note.screen-hiragino.jp/n/n2019dff6af1c)
- [YouTubeサムネイル用フリーフォント](https://goodfreefonts.com/3957/)
- [Noto Sans CJK JP](https://www.google.com/get/noto/)
