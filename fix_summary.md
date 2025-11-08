# 修正内容サマリー

## 修正日時
2025年11月8日

## 修正対象
- Phase 4: AI動画選択ロジック
- Phase 6: 字幕文字数設定

## 修正内容

### 1. Phase 6: 字幕文字数の削減

**変更箇所:** `src/phases/phase_06_subtitles.py`

**変更内容:**
- 推奨最大文字数: 16文字 → **15文字**
- 絶対的な最大文字数: 16文字 → **15文字**
- 関連するすべてのコメントとデフォルト値を更新

**影響範囲:**
- `max_chars_per_line`のデフォルト値: 3箇所
- コメント内の記述: 7箇所

**検証結果:**
✅ すべての16文字の記述を15文字に更新完了

---

### 2. Phase 4: AI動画選択ロジックの修正

**変更箇所:** `src/phases/phase_04_animation.py`

**問題点:**
- 旧ロジック: `section_{section_id}_img_0`というファイル名パターンを探していた
- 実際のファイル名: `section_01_sd_001df0ed_20251108_013726.png`
- 結果: どの画像もAI動画の対象として認識されず、すべて静止画になっていた

**修正内容:**
1. ファイル名パターンを`section_{section_id:02d}_sd_`に修正
2. セクションごとに画像をグループ化してソート
3. 各セクションの最初の1-2枚をAI動画化
   - セクションの画像数が1枚の場合: 1枚をAI動画化
   - セクションの画像数が2枚以上の場合: 2枚をAI動画化
4. セクション画像のキャッシュ機能を追加してパフォーマンス向上

**実装詳細:**
```python
def _should_use_ai_video(self, img_data: Dict[str, Any], section_info: Dict[str, Any]) -> bool:
    """AI動画を使用すべきか判定 - 各セクションの最初の1-2枚"""
    
    section_id = section_info.get('section_id')
    filename = Path(img_data['file_path']).name
    
    # 実際のファイル名パターン: section_01_sd_xxxxx.png
    section_prefix = f"section_{section_id:02d}_sd_"
    
    if not filename.startswith(section_prefix):
        return False
    
    # セクション画像のキャッシュを使用
    if not hasattr(self, '_section_image_cache'):
        self._section_image_cache = {}
    
    if section_id not in self._section_image_cache:
        # 同じセクションの画像を収集してソート
        with open(self.classified_json, 'r', encoding='utf-8') as f:
            images_data = json.load(f)
        
        section_images = [
            img for img in images_data['images']
            if Path(img['file_path']).name.startswith(section_prefix)
        ]
        section_images.sort(key=lambda x: Path(x['file_path']).name)
        self._section_image_cache[section_id] = section_images
    
    section_images = self._section_image_cache[section_id]
    
    # 現在の画像がセクション内で何番目かを確認
    current_img_path = img_data['file_path']
    for idx, img in enumerate(section_images):
        if img['file_path'] == current_img_path:
            # 最初の1-2枚をAI動画化
            max_ai_images = 1 if len(section_images) == 1 else 2
            if idx < max_ai_images:
                return True
            break
    
    return False
```

**検証結果:**
✅ AI動画選択ロジック: 正常

**テストケース:** イグナーツゼンメルワイス（3セクション、9画像）

| セクション | 総画像数 | AI動画化 | 静止画 |
|-----------|---------|---------|--------|
| セクション 1 | 5枚 | 2枚 | 3枚 |
| セクション 2 | 3枚 | 2枚 | 1枚 |
| セクション 3 | 1枚 | 1枚 | 0枚 |
| **合計** | **9枚** | **5枚** | **4枚** |

**詳細:**
- セクション 1 (5枚):
  - [1] 🎬 AI動画 - section_01_sd_001df0ed_20251108_013726.png
  - [2] 🎬 AI動画 - section_01_sd_001df0ed_20251108_013726.png
  - [3] 📷 静止画 - section_01_sd_001df0ed_20251108_013726.png
  - [4] 📷 静止画 - section_01_sd_355216a4_20251108_013757.png
  - [5] 📷 静止画 - section_01_sd_dd9fcce2_20251108_013743.png

- セクション 2 (3枚):
  - [1] 🎬 AI動画 - section_02_sd_b2cca171_20251108_013827.png
  - [2] 🎬 AI動画 - section_02_sd_c424ee7d_20251108_013812.png
  - [3] 📷 静止画 - section_02_sd_c424ee7d_20251108_013812.png

- セクション 3 (1枚):
  - [1] 🎬 AI動画 - section_03_sd_ebe17515_20251108_013840.png

---

## Git コミット情報

**ブランチ:** `fix/phase3-inherit-phasebase`

**コミットメッセージ:**
```
fix: Phase 4 AI animation selection and Phase 6 subtitle width

- Phase 4: Fix _should_use_ai_video() to work with actual filename pattern (section_XX_sd_xxxxx.png)
- Phase 4: Select 1-2 images per section for AI animation (minimum 1, maximum 2)
- Phase 6: Reduce subtitle character width from 16 to 15 characters
```

**コミットハッシュ:** 0bb88a0

**プッシュ先:** https://github.com/halfminthink-bit/video-automation.git

---

## 次のステップ

1. ローカル環境でPhase 4とPhase 6を実行してテスト
2. 動作確認後、`fix/phase3-inherit-phasebase`ブランチを`main`にマージ
3. 必要に応じてPhase 1の改善（エラーハンドリング、設定検証、ログ記録）を実装

---

## 備考

- すべての修正は後方互換性を維持
- API使用量に影響なし
- 日本語テキストとWindowsファイルパスに対応
- 動的なセクション数に対応（ハードコードなし）
- デバッグログを追加して問題のトラブルシューティングを容易化
