"""
画像タイミングマッチャー（Image Timing Matcher）

字幕のテキストに含まれるキーワードに基づいて、
最適なタイミングで画像を切り替える機能を提供する。
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging


class ImageTimingMatcher:
    """
    字幕タイミングに基づいて画像配置を最適化するクラス
    
    機能:
    - 字幕テキストと画像キーワードのマッチング
    - 優先度に基づく画像選択
    - 時間制約の適用
    - フォールバック戦略
    """
    
    def __init__(
        self,
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
            min_duration: 最小表示時間（秒）
            max_duration: 最大表示時間（秒）
            section_boundary_switch: セクション境界で強制切り替え
            exact_match_weight: 完全一致の重み
            partial_match_weight: 部分一致の重み
            same_section_weight: 同一セクションの重み
            keyword_length_weight: キーワード長の重み
            logger: ロガー
        """
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.section_boundary_switch = section_boundary_switch
        self.exact_match_weight = exact_match_weight
        self.partial_match_weight = partial_match_weight
        self.same_section_weight = same_section_weight
        self.keyword_length_weight = keyword_length_weight
        self.logger = logger or logging.getLogger(__name__)
    
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
            画像クリップのリスト:
            [
                {
                    "image_path": "path/to/image.png",
                    "start_time": 0.0,
                    "end_time": 5.2,
                    "keyword_matched": "モナリザ",
                    "confidence": 1.0,
                    "match_type": "exact"
                },
                ...
            ]
        """
        self.logger.info(f"Image timing matcher initialized for Section {section_id}")
        
        # セクション内の字幕を取得
        section_subtitles = [
            sub for sub in subtitle_timing
            if self._get_subtitle_section(sub, script_data) == section_id
        ]
        
        # セクション内の画像を取得
        section_images = self._get_section_images(classified_images, section_id)
        
        self.logger.info(
            f"Section {section_id}: Found {len(section_subtitles)} subtitles, "
            f"{len(section_images)} images"
        )
        
        # デバッグ: 画像のキーワードを表示
        if section_images:
            self.logger.debug(f"Section {section_id} image keywords:")
            for img in section_images:
                keywords = img.get('keywords', [])
                self.logger.debug(f"  {Path(img.get('file_path', '')).name}: {keywords}")
        
        if not section_subtitles:
            self.logger.warning(f"No subtitles found for Section {section_id}")
            return self._create_fallback_clips(section_images, 0.0, 10.0)
        
        if not section_images:
            self.logger.warning(f"No images found for Section {section_id}")
            return []
        
        # セクションの開始時間と終了時間を取得
        section_start = min(sub['start_time'] for sub in section_subtitles)
        section_end = max(sub['end_time'] for sub in section_subtitles)
        
        # 画像クリップを生成
        image_clips = []
        used_images = set()
        current_time = section_start
        last_image_path = None
        last_clip_end = section_start
        
        for subtitle in section_subtitles:
            subtitle_text = self._get_subtitle_text(subtitle)
            start_time = subtitle['start_time']
            end_time = subtitle['end_time']
            
            # 前のクリップとギャップがある場合は埋める
            if last_clip_end < start_time - 0.1 and image_clips:
                # 前の画像を延長してギャップを埋める
                image_clips[-1]['end_time'] = start_time
                last_clip_end = start_time
            
            # キーワードマッチング（使用済みチェックを緩和：同じ画像を複数回使用可能）
            matches = self._find_keyword_matches(
                subtitle_text,
                section_images,
                section_id,
                set()  # 使用済みチェックを緩和
            )
            
            if matches:
                # 最適なマッチを選択
                best_match = max(matches, key=lambda m: m['priority'])
                
                image_path = best_match['image_path']
                keyword = best_match['keyword']
                match_type = best_match['match_type']
                confidence = best_match['confidence']
                
                # 表示時間を計算
                display_duration = min(
                    max(end_time - start_time, self.min_duration),
                    self.max_duration
                )
                
                # 前の画像と同じで、連続している場合は延長
                if (last_image_path == image_path and image_clips and 
                    image_clips[-1]['end_time'] >= start_time - 0.5):
                    # 前のクリップを延長
                    image_clips[-1]['end_time'] = max(image_clips[-1]['end_time'], end_time)
                    last_clip_end = image_clips[-1]['end_time']
                else:
                    # 新しいクリップを作成
                    image_clips.append({
                        'image_path': str(image_path),
                        'start_time': start_time,
                        'end_time': start_time + display_duration,
                        'keyword_matched': keyword,
                        'confidence': confidence,
                        'match_type': match_type
                    })
                    used_images.add(image_path)
                    last_image_path = image_path
                    last_clip_end = start_time + display_duration
                
                self.logger.debug(
                    f"Matched '{keyword}' → {Path(image_path).name} "
                    f"at {start_time:.3f}s ({match_type})"
                )
            else:
                # フォールバック: 未使用画像または前の画像を継続
                # 前の画像を延長できる場合は延長（連続している、またはギャップが小さい場合）
                if image_clips and (last_clip_end >= start_time - 0.5 or 
                                   (start_time - last_clip_end) < 2.0):
                    # 前の画像を延長
                    image_clips[-1]['end_time'] = max(image_clips[-1]['end_time'], end_time)
                    last_clip_end = image_clips[-1]['end_time']
                    self.logger.debug(
                        f"No match for subtitle at {start_time:.3f}s, "
                        f"extending previous image to {last_clip_end:.3f}s"
                    )
                else:
                    # 新しいフォールバック画像を使用
                    # 使用済み画像も含めて、セクション内の画像を循環的に使用
                    available_images = [Path(img.get('file_path', '')) for img in section_images]
                    if not available_images:
                        continue
                    
                    # 使用済み画像も含めて、順番に使用（循環）
                    if used_images:
                        # 使用済み画像から選択（同じ画像を複数回使用）
                        fallback_image = list(used_images)[len(used_images) % len(available_images)]
                    else:
                        # 未使用画像から選択
                        fallback_image = available_images[0]
                    
                    display_duration = min(
                        max(end_time - start_time, self.min_duration),
                        self.max_duration
                    )
                    image_clips.append({
                        'image_path': str(fallback_image),
                        'start_time': start_time,
                        'end_time': start_time + display_duration,
                        'keyword_matched': None,
                        'confidence': 0.0,
                        'match_type': 'fallback'
                    })
                    if fallback_image not in used_images:
                        used_images.add(fallback_image)
                    last_image_path = fallback_image
                    last_clip_end = start_time + display_duration
                    self.logger.debug(
                        f"No match for subtitle at {start_time:.3f}s, "
                        f"using fallback: {Path(fallback_image).name}"
                    )
        
        # セクション終了までカバーされていない場合は最後の画像を延長
        if image_clips and image_clips[-1]['end_time'] < section_end:
            image_clips[-1]['end_time'] = section_end
            self.logger.debug(
                f"Extended last image to cover section end: {section_end:.3f}s"
            )
        
        # セクション全体がカバーされていない場合は、均等分割でフォールバック
        if image_clips:
            total_covered = sum(
                clip['end_time'] - clip['start_time']
                for clip in image_clips
            )
            section_duration = section_end - section_start
            coverage_ratio = total_covered / section_duration if section_duration > 0 else 0
            
            if coverage_ratio < 0.5:  # 50%未満しかカバーされていない場合
                self.logger.warning(
                    f"Section {section_id}: Only {coverage_ratio:.1%} covered. "
                    f"Falling back to equal split."
                )
                return self._create_fallback_clips(section_images, section_start, section_end)
        
        # 時間制約を適用
        image_clips = self._apply_time_constraints(image_clips, section_end)
        
        # ログ出力
        if image_clips:
            avg_duration = sum(
                clip['end_time'] - clip['start_time']
                for clip in image_clips
            ) / len(image_clips)
            self.logger.info(
                f"Section {section_id}: {len(image_clips)} images placed, "
                f"avg duration: {avg_duration:.1f}s"
            )
        
        return image_clips
    
    def _find_keyword_matches(
        self,
        subtitle_text: str,
        images: List[dict],
        section_id: int,
        used_images: set
    ) -> List[Dict[str, Any]]:
        """
        キーワードマッチング
        
        Args:
            subtitle_text: 字幕テキスト
            images: 画像リスト
            section_id: セクションID
            used_images: 使用済み画像のセット
            
        Returns:
            マッチ結果のリスト
        """
        matches = []
        normalized_text = self._normalize_text(subtitle_text)
        
        # デバッグ: 最初の数個の字幕のみ詳細ログ
        debug_mode = len(matches) < 5  # 最初の数個のみ
        
        for image in images:
            image_path = Path(image.get('file_path', ''))
            if image_path in used_images:
                continue
            
            image_keywords = image.get('keywords', [])
            image_section = self._get_image_section(image_path)
            
            for keyword in image_keywords:
                normalized_keyword = self._normalize_text(keyword)
                
                # 完全一致
                if normalized_keyword in normalized_text:
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
                    if debug_mode:
                        self.logger.debug(
                            f"  Exact match: '{keyword}' in '{subtitle_text[:30]}...'"
                        )
                
                # 部分一致（キーワードの一部が字幕に含まれる）
                # キーワードを単語に分割して、いずれかが含まれるかチェック
                keyword_words = normalized_keyword.split()
                for word in keyword_words:
                    if len(word) >= 2 and word in normalized_text:  # 2文字以上の単語のみ
                        match_type = 'partial'
                        confidence = 0.5 + (len(word) / len(normalized_keyword)) * 0.3  # 長い単語ほど信頼度が高い
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
                        if debug_mode:
                            self.logger.debug(
                                f"  Partial match: '{word}' (from '{keyword}') in '{subtitle_text[:30]}...'"
                            )
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
        
        # 最大表示時間を制限（ただし、セクション終了まで延長した最後のクリップは除外）
        for i, clip in enumerate(clips):
            duration = clip['end_time'] - clip['start_time']
            # 最後のクリップで、セクション終了まで延長されている場合は制限しない
            is_last_clip = (i == len(clips) - 1)
            if duration > self.max_duration and not is_last_clip:
                clip['end_time'] = clip['start_time'] + self.max_duration
        
        # セクション境界で強制切り替え
        if self.section_boundary_switch:
            # 最後のクリップがセクション終了を超えないように
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
        字幕が属するセクションを取得
        
        Args:
            subtitle: 字幕データ
            script_data: 台本データ
            
        Returns:
            セクションID
        """
        # 字幕の開始時間からセクションを判定
        start_time = subtitle.get('start_time', 0.0)
        
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
        テキストを正規化（全角/半角統一、スペース除去）
        
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
        
        # スペースと記号を除去
        text = re.sub(r'[\s\.,;:!?()\[\]""\'\']+', '', text)
        
        return text.lower()
    
    def _get_fallback_image(
        self,
        images: List[dict],
        used_images: set
    ) -> Optional[Path]:
        """
        フォールバック画像を取得（未使用画像からランダム選択）
        
        Args:
            images: 画像リスト
            used_images: 使用済み画像のセット
            
        Returns:
            画像パス（見つからない場合はNone）
        """
        unused_images = [
            Path(img.get('file_path', ''))
            for img in images
            if Path(img.get('file_path', '')) not in used_images
        ]
        
        if unused_images:
            return unused_images[0]  # 最初の未使用画像を返す
        
        # 全て使用済みの場合は最初の画像を返す
        if images:
            return Path(images[0].get('file_path', ''))
        
        return None
    
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

