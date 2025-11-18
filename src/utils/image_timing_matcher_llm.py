"""
画像タイミングマッチャー（LLM駆動型）

Claude 3 Haikuを使用して、文脈を理解した自然な画像切り替えを実現する。
LLMが指定しなかった隙間時間には「未使用画像」を自動的に埋めるハイブリッドな挙動を提供。
"""

import json
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class ImageTimingMatcherLLM:
    """
    LLM駆動型画像タイミングマッチャー
    
    機能:
    - Claude 3 Haikuを使用した文脈理解に基づく画像配置
    - セクション単位でのAPI問い合わせ（出力トークン制限回避）
    - キャッシュ機能によるコスト削減
    - ハイブリッド配置（LLM指定 + 隙間埋め）
    """
    
    def __init__(
        self,
        working_dir: Path,
        api_key: Optional[str] = None,
        model: str = "claude-3-haiku-20240307",
        cache_dir: Optional[Path] = None,
        min_duration: float = 3.0,
        max_duration: float = 15.0,
        gap_threshold: float = 2.0,
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化
        
        Args:
            working_dir: 作業ディレクトリ
            api_key: Anthropic APIキー（Noneの場合は環境変数から取得）
            model: 使用するClaudeモデル
            cache_dir: キャッシュ保存先（デフォルト: working_dir/07_composition）
            min_duration: 最小表示時間（秒）
            max_duration: 最大表示時間（秒）
            gap_threshold: 隙間埋めの閾値（秒）
            logger: ロガー
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "anthropic package is required. Install with: pip install anthropic"
            )
        
        self.working_dir = Path(working_dir)
        self.model = model
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.gap_threshold = gap_threshold
        self.logger = logger or logging.getLogger(__name__)
        
        # APIキーの取得
        if api_key is None:
            import os
            api_key = os.getenv("CLAUDE_API_KEY")
            if not api_key:
                raise ValueError(
                    "CLAUDE_API_KEY environment variable is required. "
                    "Set it or pass api_key parameter."
                )
        
        self.api_client = Anthropic(api_key=api_key)
        
        # キャッシュディレクトリの設定（Phase 07の出力ディレクトリに保存）
        if cache_dir is None:
            # working_dir/07_composition/ に保存
            cache_dir = self.working_dir / "07_composition"
        else:
            cache_dir = Path(cache_dir)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "llm_allocation_cache.json"
        
        # キャッシュの読み込み
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict[str, Any]:
        """キャッシュファイルを読み込む"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load cache: {e}")
                return {}
        return {}
    
    def _save_cache(self):
        """キャッシュファイルに保存"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.warning(f"Failed to save cache: {e}")
    
    def _get_cache_key(
        self,
        section_id: int,
        section_subtitles: List[Dict[str, Any]],
        section_images: List[Dict[str, Any]]
    ) -> str:
        """
        キャッシュキーを生成
        
        Args:
            section_id: セクションID
            section_subtitles: セクション内の字幕リスト
            section_images: セクション内の画像リスト
            
        Returns:
            キャッシュキー（文字列）
        """
        # 字幕と画像のハッシュを計算
        subtitle_hash = hashlib.md5(
            json.dumps(section_subtitles, sort_keys=True).encode('utf-8')
        ).hexdigest()[:8]
        
        image_hash = hashlib.md5(
            json.dumps(
                [(img.get('file_path', ''), img.get('keywords', [])) 
                 for img in section_images],
                sort_keys=True
            ).encode('utf-8')
        ).hexdigest()[:8]
        
        return f"{section_id}_{subtitle_hash}_{image_hash}"
    
    def match_images_to_subtitles(
        self,
        script_data: dict,
        classified_images: dict,
        subtitle_timing: List[dict],
        section_id: int
    ) -> List[Dict[str, Any]]:
        """
        字幕タイミングに基づいて画像をマッチング（LLM駆動）
        
        Args:
            script_data: 台本データ（script.json）
            classified_images: 分類済み画像データ（classified.json）
            subtitle_timing: 字幕タイミングデータ（subtitle_timing.json）
            section_id: セクションID
            
        Returns:
            画像クリップのリスト
        """
        self.logger.info(f"🤖 LLM Image Timing Matcher initialized for Section {section_id}")
        
        # セクション境界を取得（audio_timing.jsonから）
        section_boundaries = self._load_section_boundaries()
        if section_id not in section_boundaries:
            self.logger.warning(
                f"Section {section_id} boundaries not found. "
                "Falling back to subtitle-based calculation."
            )
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
        else:
            section_start, section_end = section_boundaries[section_id]
        
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
        
        if not section_subtitles:
            self.logger.warning(f"No subtitles found for Section {section_id}")
            return self._create_fallback_clips(section_images, section_start, section_end)
        
        if not section_images:
            self.logger.warning(f"No images found for Section {section_id}")
            return []
        
        # LLMに問い合わせて画像配置を取得
        try:
            llm_allocations = self._get_allocations_from_llm(
                section_id,
                section_subtitles,
                section_images
            )
        except Exception as e:
            self.logger.error(f"LLM allocation failed: {e}. Falling back to equal split.")
            return self._create_fallback_clips(section_images, section_start, section_end)
        
        # ハイブリッド配置ロジックを適用
        image_clips = self._apply_allocations_and_fill_gaps(
            llm_allocations,
            section_subtitles,
            section_images,
            section_start,
            section_end
        )
        
        # ログ出力
        if image_clips:
            avg_duration = sum(
                clip['end_time'] - clip['start_time']
                for clip in image_clips
            ) / len(image_clips)
            self.logger.info(
                f"Section {section_id}: {len(image_clips)} image clips, "
                f"avg duration: {avg_duration:.1f}s"
            )
        
        return image_clips
    
    def _get_allocations_from_llm(
        self,
        section_id: int,
        section_subtitles: List[Dict[str, Any]],
        section_images: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        LLMに問い合わせて画像配置を取得
        
        Args:
            section_id: セクションID
            section_subtitles: セクション内の字幕リスト
            section_images: セクション内の画像リスト
            
        Returns:
            LLMが返した配置リスト: [{"subtitle_id": 5, "image": "A.png"}, ...]
        """
        # キャッシュキーを生成
        cache_key = self._get_cache_key(section_id, section_subtitles, section_images)
        
        # キャッシュを確認
        if cache_key in self.cache:
            self.logger.info(f"✓ Using cached allocation for Section {section_id}")
            return self.cache[cache_key]
        
        # プロンプトを構築
        prompt = self._build_prompt(section_subtitles, section_images)
        
        # LLMに問い合わせ
        self.logger.info(f"🤖 Querying LLM for Section {section_id}...")
        try:
            response = self.api_client.messages.create(
                model=self.model,
                max_tokens=4096,
                system="You are a video director. Output valid JSON only. Do not include any explanatory text.",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # レスポンスからテキストを取得
            response_text = response.content[0].text.strip()
            
            # JSONをパース
            # レスポンスがコードブロックで囲まれている場合を考慮
            if response_text.startswith("```"):
                # コードブロックを除去
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text
            
            allocations = json.loads(response_text)
            
            # キャッシュに保存
            self.cache[cache_key] = allocations
            self._save_cache()
            
            self.logger.info(f"✓ LLM allocation received: {len(allocations)} assignments")
            return allocations
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM response as JSON: {e}")
            self.logger.debug(f"Response text: {response_text[:500]}")
            raise
        except Exception as e:
            self.logger.error(f"LLM API error: {e}")
            raise
    
    def _build_prompt(
        self,
        subtitles: List[Dict[str, Any]],
        images: List[Dict[str, Any]]
    ) -> str:
        """
        プロンプトを構築
        
        Args:
            subtitles: 字幕リスト
            images: 画像リスト
            
        Returns:
            プロンプト文字列
        """
        # 字幕リストを構築
        subtitle_lines = []
        for i, sub in enumerate(subtitles):
            text_line1 = sub.get('text_line1', '').strip()
            text_line2 = sub.get('text_line2', '').strip()
            text = f"{text_line1} {text_line2}".strip()
            start_time = sub.get('start_time', 0.0)
            subtitle_lines.append(
                f"{i}. ID: {sub.get('index', i)}, Time: {start_time:.2f}s, Text: {text}"
            )
        
        # 画像リストを構築
        image_lines = []
        for i, img in enumerate(images):
            file_path = Path(img.get('file_path', ''))
            filename = file_path.name
            keywords = img.get('keywords', [])
            source = img.get('source', 'unknown')
            image_lines.append(
                f"{i+1}. File: {filename} | Keywords: {keywords} | Source: {source}"
            )
        
        prompt = f"""You are a video director selecting images for a video section.

[Subtitle List]
{chr(10).join(subtitle_lines)}

[Image List]
{chr(10).join(image_lines)}

Task: Select the most appropriate image for each subtitle based on context and keywords.

Output format (JSON array):
[
  {{"subtitle_id": <subtitle_index>, "image": "<filename>"}},
  ...
]

Rules:
1. Match images to subtitles based on semantic relevance and keywords
2. You don't need to assign an image to every subtitle
3. Prioritize images that match the content of the subtitle text
4. Output only valid JSON, no explanations"""
        
        return prompt
    
    def _apply_allocations_and_fill_gaps(
        self,
        llm_allocations: List[Dict[str, Any]],
        section_subtitles: List[Dict[str, Any]],
        section_images: List[Dict[str, Any]],
        section_start: float,
        section_end: float
    ) -> List[Dict[str, Any]]:
        """
        ハイブリッド配置ロジック: LLM指定 + 隙間埋め
        
        Args:
            llm_allocations: LLMが返した配置リスト
            section_subtitles: セクション内の字幕リスト
            section_images: セクション内の画像リスト
            section_start: セクション開始時間
            section_end: セクション終了時間
            
        Returns:
            画像クリップのリスト
        """
        # Step 1: LLM指定の配置
        image_clips = []
        used_images = set()
        
        # 字幕ID -> 字幕データのマッピング
        subtitle_map = {sub.get('index', i): sub for i, sub in enumerate(section_subtitles)}
        
        # LLM指定を処理
        for allocation in llm_allocations:
            subtitle_id = allocation.get('subtitle_id')
            image_filename = allocation.get('image')
            
            if subtitle_id not in subtitle_map:
                self.logger.warning(f"Subtitle ID {subtitle_id} not found, skipping")
                continue
            
            subtitle = subtitle_map[subtitle_id]
            start_time = subtitle.get('start_time', 0.0)
            end_time = subtitle.get('end_time', start_time + 3.0)
            
            # 画像ファイルを検索
            image_data = None
            for img in section_images:
                if Path(img.get('file_path', '')).name == image_filename:
                    image_data = img
                    used_images.add(image_filename)
                    break
            
            if image_data is None:
                self.logger.warning(f"Image {image_filename} not found, skipping")
                continue
            
            # クリップを作成
            image_clips.append({
                'image_path': str(Path(image_data.get('file_path', ''))),
                'start_time': start_time,
                'end_time': end_time,
                'keyword_matched': None,  # LLM選択なのでキーワードマッチはなし
                'confidence': 1.0,
                'match_type': 'llm'
            })
        
        # クリップを開始時間でソート
        image_clips.sort(key=lambda x: x['start_time'])
        
        # Step 2: 未使用画像の特定
        unused_images = [
            img for img in section_images
            if Path(img.get('file_path', '')).name not in used_images
        ]
        
        # Step 3: 隙間（Gaps）の特定
        gaps = []
        
        # セクション開始から最初の画像まで
        if image_clips:
            first_clip_start = image_clips[0]['start_time']
            if first_clip_start - section_start >= self.gap_threshold:
                gaps.append((section_start, first_clip_start))
        else:
            # LLM指定が1つもない場合は全体を隙間として扱う
            gaps.append((section_start, section_end))
        
        # 画像間の隙間
        for i in range(len(image_clips) - 1):
            current_end = image_clips[i]['end_time']
            next_start = image_clips[i + 1]['start_time']
            gap_duration = next_start - current_end
            if gap_duration >= self.gap_threshold:
                gaps.append((current_end, next_start))
        
        # 最後の画像からセクション終了まで
        if image_clips:
            last_clip_end = image_clips[-1]['end_time']
            if section_end - last_clip_end >= self.gap_threshold:
                gaps.append((last_clip_end, section_end))
        
        # Step 4: 隙間埋め（長い隙間のみ、微細な隙間は後で前の画像を延長して埋める）
        unused_image_index = 0
        for gap_start, gap_end in gaps:
            gap_duration = gap_end - gap_start
            
            # 微細な隙間（gap_threshold未満）は後で前の画像を延長して埋めるため、ここではスキップ
            if gap_duration < self.gap_threshold:
                self.logger.debug(
                    f"Skipping small gap ({gap_duration:.3f}s < {self.gap_threshold}s). "
                    "Will be filled by extending previous image."
                )
                continue
            
            # 最小表示時間未満の隙間もスキップ（後で前の画像を延長）
            if gap_duration < self.min_duration:
                self.logger.debug(
                    f"Skipping gap ({gap_duration:.3f}s < min_duration {self.min_duration}s). "
                    "Will be filled by extending previous image."
                )
                continue
            
            # 長い隙間（gap_threshold以上）は新しい画像で埋める
            # 未使用画像があれば使用、なければ既出画像を再利用
            if unused_image_index < len(unused_images):
                image_data = unused_images[unused_image_index]
                unused_image_index += 1
            elif image_clips:
                # 最後に使用した画像以外を選択
                last_image = image_clips[-1]['image_path']
                for img in section_images:
                    if str(Path(img.get('file_path', ''))) != last_image:
                        image_data = img
                        break
                else:
                    # 見つからない場合は最後の画像を再利用
                    image_data = section_images[0]
            else:
                # 画像がない場合はスキップ（後で前の画像を延長）
                continue
            
            # 隙間を埋めるクリップを作成
            image_clips.append({
                'image_path': str(Path(image_data.get('file_path', ''))),
                'start_time': gap_start,
                'end_time': gap_end,
                'keyword_matched': None,
                'confidence': 0.0,
                'match_type': 'gap_fill'
            })
        
        # 再度ソート
        image_clips.sort(key=lambda x: x['start_time'])
        
        # 時間制約を適用（連続性を完全に保証）
        image_clips = self._apply_time_constraints(
            image_clips, 
            section_start, 
            section_end
        )
        
        return image_clips
    
    def _apply_time_constraints(
        self,
        clips: List[Dict[str, Any]],
        section_start: float,
        section_end: float
    ) -> List[Dict[str, Any]]:
        """
        時間制約を適用し、連続性を完全に保証（Anti-Desync Logic）
        
        Args:
            clips: 画像クリップのリスト
            section_start: セクション開始時間
            section_end: セクション終了時間
            
        Returns:
            制約適用後のクリップリスト（隙間ゼロ、完全連続）
        """
        if not clips:
            return clips
        
        # 開始時間でソート
        clips.sort(key=lambda x: x['start_time'])
        
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
        
        # 【重要】隙間の強制結合: 前の画像を延長して隙間を埋める
        result = []
        for i, clip in enumerate(clips):
            if i == 0:
                # 最初のクリップ: section_startから開始するように調整
                if clip['start_time'] > section_start:
                    # 開始時間を前に伸ばす
                    clip['start_time'] = section_start
                result.append(clip)
            else:
                prev_clip = result[-1]
                gap = clip['start_time'] - prev_clip['end_time']
                
                if gap > 0:
                    # 隙間がある場合: 前の画像を延長して埋める
                    self.logger.debug(
                        f"Filling gap of {gap:.3f}s by extending previous image "
                        f"({prev_clip['start_time']:.3f}s - {prev_clip['end_time']:.3f}s -> "
                        f"{prev_clip['start_time']:.3f}s - {clip['start_time']:.3f}s)"
                    )
                    prev_clip['end_time'] = clip['start_time']
                elif gap < 0:
                    # 重複している場合: 前のクリップを延長（後のクリップの終了時間まで）
                    if clip['end_time'] > prev_clip['end_time']:
                        prev_clip['end_time'] = clip['end_time']
                    # 重複しているクリップはスキップ
                    continue
                
                result.append(clip)
        
        # セクション全域の完全カバー
        if result:
            # 最初のクリップをsection_startから開始
            if result[0]['start_time'] > section_start:
                result[0]['start_time'] = section_start
            
            # 最後のクリップをsection_endまで延長
            last_clip = result[-1]
            if last_clip['end_time'] < section_end:
                self.logger.debug(
                    f"Extending last clip to section end: "
                    f"{last_clip['end_time']:.3f}s -> {section_end:.3f}s"
                )
                last_clip['end_time'] = section_end
            elif last_clip['end_time'] > section_end:
                last_clip['end_time'] = section_end
        
        # 最終チェック: 連続性の検証
        for i in range(len(result) - 1):
            current_end = result[i]['end_time']
            next_start = result[i + 1]['start_time']
            gap = next_start - current_end
            if abs(gap) > 0.001:  # 1ミリ秒以上の隙間は許容しない
                self.logger.warning(
                    f"Warning: Gap detected between clips {i} and {i+1}: {gap:.6f}s. "
                    f"Extending previous clip to fill."
                )
                result[i]['end_time'] = next_start
        
        # セクション全域のカバー確認
        if result:
            first_start = result[0]['start_time']
            last_end = result[-1]['end_time']
            if abs(first_start - section_start) > 0.001:
                self.logger.warning(
                    f"First clip does not start at section_start: "
                    f"{first_start:.6f}s != {section_start:.6f}s"
                )
                result[0]['start_time'] = section_start
            if abs(last_end - section_end) > 0.001:
                self.logger.warning(
                    f"Last clip does not end at section_end: "
                    f"{last_end:.6f}s != {section_end:.6f}s"
                )
                result[-1]['end_time'] = section_end
        
        return result
    
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
                    cumulative_time += section_duration
            
        except Exception as e:
            self.logger.error(f"Failed to load section boundaries: {e}", exc_info=True)
        
        return boundaries
    
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
        start_time = subtitle.get('start_time', 0.0)
        boundaries = self._load_section_boundaries()
        
        for section_id, (section_start, section_end) in boundaries.items():
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
        import re
        filename = image_path.name
        match = re.search(r'section_(\d+)', filename)
        if match:
            return int(match.group(1))
        return 1  # デフォルト
    
    def _create_fallback_clips(
        self,
        section_images: List[dict],
        section_start: float,
        section_end: float
    ) -> List[Dict[str, Any]]:
        """
        フォールバッククリップを作成（均等分割）
        
        Args:
            section_images: セクション内の画像リスト
            section_start: セクション開始時間
            section_end: セクション終了時間
            
        Returns:
            画像クリップのリスト
        """
        if not section_images:
            return []
        
        num_images = len(section_images)
        duration_per_image = (section_end - section_start) / num_images
        fallback_clips = []
        current_time = section_start
        
        for image_data in section_images:
            fallback_clips.append({
                'image_path': str(Path(image_data.get('file_path', ''))),
                'start_time': current_time,
                'end_time': current_time + duration_per_image,
                'keyword_matched': None,
                'confidence': 0.0,
                'match_type': 'fallback_equal_split'
            })
            current_time += duration_per_image
        
        return fallback_clips

