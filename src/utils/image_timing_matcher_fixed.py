"""
画像タイミングマッチャー（Image Timing Matcher Fixed）

字幕のテキストに含まれるキーワードに基づいて、
最適なタイミングで画像を切り替える機能を提供する（修正版）。

主な改善点:
- audio_timing.jsonを使用してセクション境界を正確に計算
- 日本語対応の正規化改善
- シンプルな画像配置アルゴリズム
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging


class ImageTimingMatcherFixed:
    """
    字幕タイミングに基づいて画像配置を最適化するクラス（修正版）
    
    機能:
    - 字幕テキストと画像キーワードのマッチング
    - 優先度に基づく画像選択
    - 時間制約の適用
    - フォールバック戦略
    - audio_timing.jsonを使用した正確なセクション境界計算
    """
    
    def __init__(
        self,
        working_dir: Path,
        min_duration: float = 3.0,
        max_duration: float = 15.0,
        section_boundary_switch: bool = True,
        exact_match_weight: float = 10.0,
        partial_match_weight: float = 5.0,
        same_section_weight: float = 3.0,
        keyword_length_weight: float = 1.0,
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化
        
        Args:
            working_dir: 作業ディレクトリ（audio_timing.jsonを読むため）
            min_duration: 最小表示時間（秒）
            max_duration: 最大表示時間（秒）
            section_boundary_switch: セクション境界で強制切り替え
            exact_match_weight: 完全一致の重み
            partial_match_weight: 部分一致の重み
            same_section_weight: 同一セクションの重み
            keyword_length_weight: キーワード長の重み
            logger: ロガー
        """
        self.working_dir = Path(working_dir)
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.section_boundary_switch = section_boundary_switch
        self.exact_match_weight = exact_match_weight
        self.partial_match_weight = partial_match_weight
        self.same_section_weight = same_section_weight
        self.keyword_length_weight = keyword_length_weight
        self.logger = logger or logging.getLogger(__name__)
        
        # audio_timing.jsonを読み込んでセクション境界を計算
        self.section_boundaries = self._load_section_boundaries()
    
    def _load_section_boundaries(self) -> Dict[int, Tuple[float, float]]:
        """
        audio_timing.jsonからセクション境界を読み込む
        
        Returns:
            セクションID -> (開始時間, 終了時間) の辞書
        """
        boundaries = {}
        audio_timing_path = self.working_dir / "02_audio" / "audio_timing.json"
        
        if not audio_timing_path.exists():
            self.logger.warning(f"audio_timing.json not found: {audio_timing_path}")
            return boundaries
        
        try:
            with open(audio_timing_path, 'r', encoding='utf-8') as f:
                audio_timing = json.load(f)
            
            cumulative_time = 0.0
            
            # audio_timing.jsonの構造に応じて処理
            if isinstance(audio_timing, list):
                sections = audio_timing
            elif isinstance(audio_timing, dict):
                sections = audio_timing.get('sections', [audio_timing])
            else:
                self.logger.warning(f"Unexpected audio_timing format: {type(audio_timing)}")
                return boundaries
            
            for section in sections:
                section_id = section.get('section_id')
                char_end_times = section.get('char_end_times', [])
                
                if section_id and char_end_times:
                    section_duration = char_end_times[-1]
                    boundaries[section_id] = (cumulative_time, cumulative_time + section_duration)
                    self.logger.debug(
                        f"Section {section_id}: {cumulative_time:.2f}s - "
                        f"{cumulative_time + section_duration:.2f}s "
                        f"(duration: {section_duration:.2f}s)"
                    )
                    cumulative_time += section_duration
            
        except Exception as e:
            self.logger.error(f"Failed to load section boundaries: {e}", exc_info=True)
        
        return boundaries
    
    def match_images_to_subtitles(
        self,
        script_data: dict,
        classified_images: dict,
        subtitle_timing: List[dict],
        section_id: int
    ) -> List[Dict[str, Any]]:
        """
        字幕タイミングに基づいて画像をマッチング
        
        Args:
            script_data: 台本データ（script.json）
            classified_images: 分類済み画像データ（classified.json）
            subtitle_timing: 字幕タイミングデータ（subtitle_timing.json）
            section_id: セクションID
            
        Returns:
            画像クリップのリスト
        """
        self.logger.info(f"Image timing matcher initialized for Section {section_id}")
        
        # セクション境界を取得
        if section_id in self.section_boundaries:
            section_start, section_end = self.section_boundaries[section_id]
            self.logger.debug(
                f"Section {section_id}: {section_start:.2f}s - {section_end:.2f}s "
                f"(duration: {section_end - section_start:.2f}s)"
            )
        else:
            # フォールバック: 字幕から計算
            section_subtitles = [
                sub for sub in subtitle_timing
                if self._get_subtitle_section(sub, script_data) == section_id
            ]
            if not section_subtitles:
                self.logger.warning(f"No subtitles found for Section {section_id}")
                return []
            section_start = min(sub['start_time'] for sub in section_subtitles)
            section_end = max(sub['end_time'] for sub in section_subtitles)
            self.logger.warning(
                f"Section {section_id} boundaries not found in audio_timing.json, "
                f"using subtitle timing: {section_start:.2f}s - {section_end:.2f}s"
            )
        
        # セクション内の字幕を取得
        section_subtitles = [
            sub for sub in subtitle_timing
            if section_start <= sub['start_time'] < section_end
        ]
        
        # セクション内の画像を取得
        section_images = self._get_section_images(classified_images, section_id)
        
        self.logger.info(
            f"Section {section_id} ({section_start:.1f}s - {section_end:.1f}s): "
            f"Found {len(section_subtitles)} subtitles, {len(section_images)} images"
        )
        
        # デバッグ: 画像のキーワードを表示（5分以降のセクションのみ詳細ログ）
        if section_start >= 300.0 or section_end >= 300.0:
            if section_images:
                self.logger.info(f"[DEBUG] Section {section_id} image keywords:")
                for img in section_images:
                    keywords = img.get('keywords', [])
                    file_path = Path(img.get('file_path', ''))
                    image_section = self._get_image_section(file_path)
                    self.logger.info(
                        f"[DEBUG]   {file_path.name} (section={image_section}): {keywords}"
                    )
            else:
                self.logger.warning(
                    f"[DEBUG] Section {section_id}: No images found! "
                    f"Checking all images..."
                )
                # 全画像を確認
                all_images = classified_images.get('images', [])
                self.logger.warning(f"[DEBUG] Total images: {len(all_images)}")
                for img in all_images[:10]:  # 最初の10個のみ
                    file_path = Path(img.get('file_path', ''))
                    image_section = self._get_image_section(file_path)
                    self.logger.warning(
                        f"[DEBUG]   {file_path.name} (section={image_section})"
                    )
        
        if not section_subtitles:
            self.logger.warning(f"No subtitles found for Section {section_id}")
            return self._create_fallback_clips(section_images, section_start, section_end)
        
        if not section_images:
            self.logger.warning(f"No images found for Section {section_id}")
            return []
        
        # デバッグ: 画像のキーワードを表示
        if section_images:
            self.logger.debug(f"Section {section_id} image keywords:")
            for img in section_images:
                keywords = img.get('keywords', [])
                self.logger.debug(f"  {Path(img.get('file_path', '')).name}: {keywords}")
        
        # 画像クリップを生成（シンプルなアルゴリズム）
        image_clips = []
        current_time = section_start
        image_index = 0
        
        # 字幕ごとに処理
        match_count = 0
        no_match_count = 0
        for subtitle in section_subtitles:
            subtitle_text = self._get_subtitle_text(subtitle)
            start_time = subtitle['start_time']
            end_time = subtitle['end_time']
            
            # キーワードマッチング
            matches = self._find_keyword_matches(
                subtitle_text,
                section_images,
                section_id
            )
            
            # デバッグ: マッチしない場合の詳細ログ（5分以降のみ）
            if start_time >= 300.0:  # 5分以降
                if not matches:
                    no_match_count += 1
                    if no_match_count <= 5:  # 最初の5回のみ詳細ログ
                        self.logger.warning(
                            f"[DEBUG] Section {section_id} at {start_time:.3f}s: "
                            f"No match for subtitle: '{subtitle_text[:50]}...'"
                        )
                        # 正規化されたテキストを表示
                        normalized_text = self._normalize_text(subtitle_text)
                        self.logger.warning(
                            f"[DEBUG] Normalized subtitle: '{normalized_text[:50]}...'"
                        )
                        # 利用可能なキーワードを表示
                        available_keywords = []
                        for img in section_images:
                            keywords = img.get('keywords', [])
                            available_keywords.extend(keywords)
                            # 正規化されたキーワードも表示
                            for kw in keywords:
                                normalized_kw = self._normalize_text(kw)
                                self.logger.warning(
                                    f"[DEBUG]   Keyword: '{kw}' -> normalized: '{normalized_kw}'"
                                )
                        self.logger.warning(
                            f"[DEBUG] Available keywords in Section {section_id}: {available_keywords}"
                        )
                else:
                    match_count += 1
            
            if matches:
                # 最適なマッチを選択
                best_match = max(matches, key=lambda m: m['priority'])
                image_path = best_match['image_path']
                keyword = best_match['keyword']
                match_type = best_match['match_type']
                
                # 新しい画像がマッチした場合、または前の画像と異なる場合は新しいクリップを作成
                if not image_clips or image_clips[-1]['image_path'] != str(image_path):
                    # 前のクリップの終了時間を設定
                    if image_clips:
                        image_clips[-1]['end_time'] = start_time
                    
                    # 新しいクリップを作成
                    image_clips.append({
                        'image_path': str(image_path),
                        'start_time': start_time,
                        'end_time': end_time,  # 一時的に設定（後で更新される可能性あり）
                        'keyword_matched': keyword,
                        'confidence': best_match['confidence'],
                        'match_type': match_type
                    })
                    self.logger.debug(
                        f"Matched '{keyword}' → {Path(image_path).name} "
                        f"at {start_time:.3f}s ({match_type})"
                    )
                else:
                    # 同じ画像が続く場合は終了時間を更新
                    image_clips[-1]['end_time'] = end_time
            
            # マッチしない場合は、前の画像を継続（またはフォールバック）
            elif image_clips:
                # 前の画像を延長
                image_clips[-1]['end_time'] = end_time
            else:
                # 最初の字幕でマッチしない場合はフォールバック画像を使用
                if section_images:
                    fallback_image = self._get_fallback_image(section_images, len(image_clips))
                    if fallback_image:
                        image_clips.append({
                            'image_path': str(fallback_image),
                            'start_time': start_time,
                            'end_time': end_time,
                            'keyword_matched': None,
                            'confidence': 0.0,
                            'match_type': 'fallback'
                        })
        
        # 最後の字幕の終了時間を取得
        if section_subtitles:
            last_subtitle_end = max(sub['end_time'] for sub in section_subtitles)
        else:
            last_subtitle_end = section_end
        
        # 最後の画像の終了時間を調整
        if image_clips:
            # 最後の字幕の終了時間まで延長（セクション終了までではない）
            # ただし、最後の字幕の終了時間がセクション終了より前の場合は、セクション終了まで延長
            if last_subtitle_end < section_end:
                # 最後の字幕の終了時間からセクション終了までの間隔が長い場合（5秒以上）
                gap = section_end - last_subtitle_end
                if gap > 5.0:
                    # 最後の字幕の終了時間で終了（セクション終了まで延長しない）
                    image_clips[-1]['end_time'] = last_subtitle_end
                    self.logger.debug(
                        f"Last image ends at last subtitle end: {last_subtitle_end:.3f}s "
                        f"(gap to section end: {gap:.3f}s)"
                    )
                else:
                    # 間隔が短い場合はセクション終了まで延長
                    image_clips[-1]['end_time'] = section_end
                    self.logger.debug(
                        f"Last image extended to section end: {section_end:.3f}s"
                    )
            else:
                # 最後の字幕の終了時間がセクション終了と同じかそれ以降の場合は、セクション終了まで延長
                image_clips[-1]['end_time'] = section_end
        
        # 時間制約を適用
        image_clips = self._apply_time_constraints(image_clips, section_end)
        
        # ログ出力
        if image_clips:
            avg_duration = sum(
                clip['end_time'] - clip['start_time']
                for clip in image_clips
            ) / len(image_clips)
            
            # デバッグ: 各クリップの詳細情報（5分以降のセクションのみ）
            if section_start >= 300.0 or section_end >= 300.0:
                self.logger.info(
                    f"Section {section_id}: {len(image_clips)} image clips, "
                    f"avg duration: {avg_duration:.1f}s"
                )
                self.logger.info(
                    f"[DEBUG] Section {section_id} match stats: "
                    f"{match_count} matches, {no_match_count} no matches"
                )
                for i, clip in enumerate(image_clips):
                    duration = clip['end_time'] - clip['start_time']
                    self.logger.info(
                        f"[DEBUG] Clip {i+1}: {Path(clip['image_path']).name} "
                        f"({clip['start_time']:.1f}s - {clip['end_time']:.1f}s, "
                        f"{duration:.1f}s) keyword: {clip.get('keyword_matched', 'N/A')}"
                    )
            else:
                self.logger.info(
                    f"Section {section_id}: {len(image_clips)} image clips, "
                    f"avg duration: {avg_duration:.1f}s"
                )
        
        return image_clips
    
    def _find_keyword_matches(
        self,
        subtitle_text: str,
        images: List[dict],
        section_id: int
    ) -> List[Dict[str, Any]]:
        """
        キーワードマッチング
        
        Args:
            subtitle_text: 字幕テキスト
            images: 画像リスト
            section_id: セクションID
            
        Returns:
            マッチ結果のリスト
        """
        matches = []
        normalized_text = self._normalize_text(subtitle_text)
        
        for image in images:
            image_path = Path(image.get('file_path', ''))
            image_keywords = image.get('keywords', [])
            image_section = self._get_image_section(image_path)
            
            for keyword in image_keywords:
                normalized_keyword = self._normalize_text(keyword)
                
                # 完全一致
                is_match = normalized_keyword in normalized_text
                # デバッグ: Section 4で「最後の晩餐」のマッチングを詳細に確認
                if section_id == 4 and '最後の晩餐' in keyword:
                    self.logger.warning(
                        f"[MATCH DEBUG] Section {section_id}: "
                        f"keyword='{keyword}' (normalized='{normalized_keyword}') "
                        f"in text='{normalized_text[:80]}' -> {is_match}"
                    )
                    self.logger.warning(
                        f"[MATCH DEBUG] normalized_keyword length: {len(normalized_keyword)}, "
                        f"normalized_text length: {len(normalized_text)}"
                    )
                
                if is_match:
                    match_type = 'exact'
                    confidence = 1.0
                    priority = self._calculate_priority(
                        match_type=match_type,
                        is_same_section=(image_section == section_id),
                        keyword_length=len(keyword),
                        confidence=confidence
                    )
                    matches.append({
                        'image_path': image_path,
                        'keyword': keyword,
                        'match_type': match_type,
                        'confidence': confidence,
                        'priority': priority
                    })
                
                # 部分一致（キーワードの一部が字幕に含まれる）
                else:
                    keyword_words = normalized_keyword.split()
                    for word in keyword_words:
                        if len(word) >= 2 and word in normalized_text:
                            match_type = 'partial'
                            confidence = 0.5 + (len(word) / len(normalized_keyword)) * 0.3
                            priority = self._calculate_priority(
                                match_type=match_type,
                                is_same_section=(image_section == section_id),
                                keyword_length=len(keyword),
                                confidence=confidence
                            )
                            matches.append({
                                'image_path': image_path,
                                'keyword': keyword,
                                'match_type': match_type,
                                'confidence': confidence,
                                'priority': priority
                            })
                            break  # 1つのキーワードで1回だけマッチ
        
        return matches
    
    def _calculate_priority(
        self,
        match_type: str,
        is_same_section: bool,
        keyword_length: int,
        confidence: float
    ) -> float:
        """
        マッチの優先度を計算
        
        Args:
            match_type: マッチタイプ（'exact' or 'partial'）
            is_same_section: 同一セクションかどうか
            keyword_length: キーワードの長さ
            confidence: 信頼度
            
        Returns:
            優先度スコア
        """
        priority = 0.0
        
        # マッチタイプの重み
        if match_type == 'exact':
            priority += self.exact_match_weight
        elif match_type == 'partial':
            priority += self.partial_match_weight
        
        # 同一セクションの重み
        if is_same_section:
            priority += self.same_section_weight
        
        # キーワード長の重み（長い方が優先）
        priority += keyword_length * self.keyword_length_weight
        
        # 信頼度
        priority *= confidence
        
        return priority
    
    def _apply_time_constraints(
        self,
        clips: List[Dict[str, Any]],
        section_end: float
    ) -> List[Dict[str, Any]]:
        """
        時間制約を適用
        
        Args:
            clips: 画像クリップのリスト
            section_end: セクションの終了時間
            
        Returns:
            制約適用後のクリップリスト
        """
        if not clips:
            return clips
        
        # 最小表示時間を確保
        for clip in clips:
            duration = clip['end_time'] - clip['start_time']
            if duration < self.min_duration:
                clip['end_time'] = clip['start_time'] + self.min_duration
        
        # 最大表示時間を制限（最後のクリップは除外）
        for i, clip in enumerate(clips):
            duration = clip['end_time'] - clip['start_time']
            is_last_clip = (i == len(clips) - 1)
            if duration > self.max_duration and not is_last_clip:
                clip['end_time'] = clip['start_time'] + self.max_duration
        
        # セクション境界で強制切り替え
        if self.section_boundary_switch:
            if clips:
                last_clip = clips[-1]
                if last_clip['end_time'] > section_end:
                    last_clip['end_time'] = section_end
        
        # 重複を解消
        result = []
        for i, clip in enumerate(clips):
            if i == 0:
                result.append(clip)
            else:
                prev_clip = result[-1]
                if clip['start_time'] < prev_clip['end_time']:
                    # 重複している場合は前のクリップを延長
                    prev_clip['end_time'] = clip['end_time']
                else:
                    result.append(clip)
        
        return result
    
    def _get_subtitle_section(
        self,
        subtitle: dict,
        script_data: dict
    ) -> int:
        """
        字幕が属するセクションを取得（audio_timing.jsonの境界を使用）
        
        Args:
            subtitle: 字幕データ
            script_data: 台本データ
            
        Returns:
            セクションID
        """
        start_time = subtitle.get('start_time', 0.0)
        
        # セクション境界から判定
        for section_id, (section_start, section_end) in self.section_boundaries.items():
            if section_start <= start_time < section_end:
                return section_id
        
        # フォールバック: script.jsonから判定
        sections = script_data.get('sections', [])
        cumulative_time = 0.0
        
        for section in sections:
            section_duration = section.get('estimated_duration', 0.0)
            if cumulative_time <= start_time < cumulative_time + section_duration:
                return section.get('section_id', 1)
            cumulative_time += section_duration
        
        # デフォルト: 最初のセクション
        return sections[0].get('section_id', 1) if sections else 1
    
    def _get_section_images(
        self,
        classified_images: dict,
        section_id: int
    ) -> List[dict]:
        """
        セクション内の画像を取得
        
        Args:
            classified_images: 分類済み画像データ
            section_id: セクションID
            
        Returns:
            画像リスト
        """
        all_images = classified_images.get('images', [])
        section_images = []
        
        for image in all_images:
            file_path = Path(image.get('file_path', ''))
            image_section = self._get_image_section(file_path)
            
            if image_section == section_id:
                section_images.append(image)
        
        return section_images
    
    def _get_image_section(self, image_path: Path) -> int:
        """
        画像が属するセクションを取得（ファイル名から）
        
        Args:
            image_path: 画像パス
            
        Returns:
            セクションID
        """
        filename = image_path.name
        match = re.search(r'section_(\d+)', filename)
        if match:
            return int(match.group(1))
        return 1  # デフォルト
    
    def _get_subtitle_text(self, subtitle: dict) -> str:
        """
        字幕テキストを取得
        
        Args:
            subtitle: 字幕データ
            
        Returns:
            字幕テキスト
        """
        line1 = subtitle.get('text_line1', '')
        line2 = subtitle.get('text_line2', '')
        return f"{line1} {line2}".strip()
    
    def _normalize_text(self, text: str) -> str:
        """
        テキストを正規化（日本語対応改善版）
        
        Args:
            text: テキスト
            
        Returns:
            正規化されたテキスト
        """
        # 全角を半角に変換（1文字ずつ対応）
        translation_map = {
            '　': ' ',  # 全角スペース
            '，': ',',  # 全角カンマ
            '．': '.',  # 全角ピリオド
            '：': ':',  # 全角コロン
            '；': ';',  # 全角セミコロン
            '？': '?',  # 全角疑問符
            '！': '!',  # 全角感嘆符
            '（': '(',  # 全角左括弧
            '）': ')',  # 全角右括弧
            '【': '[',  # 全角左角括弧
            '】': ']',  # 全角右角括弧
            '「': '"',  # 全角左鍵括弧
            '」': '"',  # 全角右鍵括弧
            '『': '"',  # 全角左二重鍵括弧
            '』': '"',  # 全角右二重鍵括弧
        }
        
        for fullwidth, halfwidth in translation_map.items():
            text = text.replace(fullwidth, halfwidth)
        
        # 日本語を保持しつつ、記号のみ除去（日本語の句読点も除去）
        # ASCII記号と日本語記号を除去
        text = re.sub(r'[!-/:-@\[-`{-~。、，！？「」『』（）【】・]', '', text)
        
        # 小文字に変換（日本語は影響を受けない）
        return text.lower()
    
    def _get_fallback_image(
        self,
        images: List[dict],
        image_index: int
    ) -> Optional[Path]:
        """
        フォールバック画像を取得（循環的に使用）
        
        Args:
            images: 画像リスト
            image_index: 現在の画像インデックス
            
        Returns:
            画像パス（見つからない場合はNone）
        """
        if not images:
            return None
        
        # 循環的に使用
        image = images[image_index % len(images)]
        return Path(image.get('file_path', ''))
    
    def _create_fallback_clips(
        self,
        images: List[dict],
        start_time: float,
        end_time: float
    ) -> List[Dict[str, Any]]:
        """
        フォールバッククリップを作成（均等分割）
        
        Args:
            images: 画像リスト
            start_time: 開始時間
            end_time: 終了時間
            
        Returns:
            クリップリスト
        """
        if not images:
            return []
        
        duration = end_time - start_time
        duration_per_image = duration / len(images)
        
        clips = []
        current_time = start_time
        
        for image in images:
            image_path = Path(image.get('file_path', ''))
            clips.append({
                'image_path': str(image_path),
                'start_time': current_time,
                'end_time': current_time + duration_per_image,
                'keyword_matched': None,
                'confidence': 0.0,
                'match_type': 'fallback'
            })
            current_time += duration_per_image
        
        return clips

