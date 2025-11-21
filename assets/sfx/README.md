# 効果音（Sound Effects）

このディレクトリには、動画で使用する効果音ファイルを配置します。

## セクションタイトル用効果音

### ファイル名
`impact_title.mp3`

### 仕様
- **長さ**: 0.5〜1.5秒
- **特徴**: 重厚感、ドーン系、インパクトあり
- **音量**: 適度（設定で0.5倍に調整されます）

### 推奨サイト
- [効果音ラボ](https://soundeffect-lab.info/)
  - カテゴリ: 衝撃音、決定音
  - おすすめ: 「ドーン1」「インパクト音」など

### 配置方法
1. 上記サイトから効果音をダウンロード
2. MP3形式に変換（必要に応じて）
3. `assets/sfx/impact_title.mp3` として保存

### 設定
効果音の音量や有効/無効は `config/phases/video_composition.yaml` で調整できます：

```yaml
section_title:
  sound_effect:
    enabled: true
    file: "assets/sfx/impact_title.mp3"
    volume: 0.5
```

## 注意事項
- 効果音ファイルが存在しない場合は、警告が表示されますが、動画生成は続行されます
- 著作権フリーの効果音を使用してください
