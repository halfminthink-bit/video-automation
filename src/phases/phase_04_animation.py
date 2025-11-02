"""
Phase 4: Image Animation & AI Video Generation
Replicate経由でKling AIを使用する正しい実装
"""

import json
import random
import time
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import numpy as np
from PIL import Image
import requests

from moviepy import VideoClip

from ..core.phase_base import PhaseBase
from ..core.config_manager import ConfigManager
from ..core.models import (
    AnimationType,
    AnimatedClip,
    ImageAnimationResult
)


class Phase04Animation(PhaseBase):
    """Phase 4: 静止画アニメーション・AI動画化（Replicate経由）"""
    
    def __init__(
        self,
        subject: str,
        config: ConfigManager,
        logger: logging.Logger
    ):
        super().__init__(subject, config, logger)
        
        # Phase 3の画像ディレクトリ
        self.images_dir = self.working_dir / "03_images" / "generated"
        self.classified_json = self.working_dir / "03_images" / "classified.json"
        
        # Phase 1の台本ファイル
        self.script_json = self.working_dir / "01_script" / "script.json"
        
        # Phase 4の出力ディレクトリ
        self.output_dir = self.phase_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 設定読み込み
        self.phase_config = config.get_phase_config(4)
        
        # AI動画生成の有効/無効
        self.use_ai_video = self.phase_config.get('ai_video_enabled', False)
        self.replicate_api_key = None
        
        if self.use_ai_video:
            try:
                self.replicate_api_key = config.get_api_key("REPLICATE_API_TOKEN")
                self.logger.info("✓ Replicate API key loaded - AI video generation enabled")
            except ValueError as e:
                self.logger.warning(f"Replicate API key not found: {e}")
                self.logger.warning("AI video generation will be disabled")
                self.use_ai_video = False
        else:
            self.logger.info("AI video generation disabled in config")
        
        # 台本データ
        self.script_data = None
    
    def get_phase_number(self) -> int:
        return 4
    
    def get_phase_name(self) -> str:
        return "Image Animation & AI Video"
    
    def get_phase_directory(self) -> Path:
        return self.working_dir / "04_animated"
    
    def check_inputs_exist(self) -> bool:
        """Phase 3の出力（画像）とPhase 1の台本が存在するかチェック"""
        if not self.classified_json.exists():
            self.logger.error(f"Classified images file not found: {self.classified_json}")
            return False
        
        if not self.images_dir.exists() or not any(self.images_dir.iterdir()):
            self.logger.error(f"No images found in: {self.images_dir}")
            return False
        
        if not self.script_json.exists():
            self.logger.error(f"Script file not found: {self.script_json}")
            return False
        
        return True
    
    def check_outputs_exist(self) -> bool:
        """Phase 4の出力が既に存在するかチェック"""
        animation_plan = self.output_dir / "animation_plan.json"
        if not animation_plan.exists():
            return False
        
        # 計画ファイルから動画数を確認
        with open(animation_plan, 'r', encoding='utf-8') as f:
            plan = json.load(f)
        
        # 全ての動画ファイルが存在するか確認
        for clip in plan.get('animated_clips', []):
            if not Path(clip['output_path']).exists():
                return False
        
        return True
    
    def execute_phase(self) -> ImageAnimationResult:
        """Phase 4を実行"""
        self.logger.info(f"Starting Phase 4: Image Animation for {self.subject}")
        self.logger.info(f"AI video generation: {'✓ Enabled' if self.use_ai_video else '✗ Disabled'}")
        
        # 台本読み込み
        with open(self.script_json, 'r', encoding='utf-8') as f:
            self.script_data = json.load(f)
        
        # 画像データ読み込み
        with open(self.classified_json, 'r', encoding='utf-8') as f:
            images_data = json.load(f)
        
        total_images = len(images_data['images'])
        self.logger.info(f"Found {total_images} images to animate")
        
        # 各画像をアニメーション化
        animated_clips = []
        
        for idx, img_data in enumerate(images_data['images'], 1):
            self.logger.info(f"\n[{idx}/{total_images}] Processing {Path(img_data['file_path']).name}...")
            
            # セクション情報を取得
            section_info = self._get_section_for_image(img_data)
            
            # AI動画を試みる（有効な場合）
            clip = None
            if self.use_ai_video and self._should_use_ai_video(img_data, section_info):
                try:
                    self.logger.info("→ Attempting AI video generation via Replicate...")
                    clip = self._create_ai_video_replicate(img_data, section_info)
                except Exception as e:
                    self.logger.warning(f"→ AI video generation failed: {e}")
                    self.logger.info("→ Falling back to simple animation")
            
            # AI動画失敗または無効な場合は簡易アニメーション
            if clip is None:
                self.logger.info("→ Creating simple pan animation...")
                clip = self._create_simple_animation(img_data, section_info)
            
            animated_clips.append(clip)
        
        # 結果を保存
        result = ImageAnimationResult(
            subject=self.subject,
            animated_clips=animated_clips,
            generated_at=self._get_current_datetime()
        )
        
        # アニメーション計画を保存
        self._save_animation_plan(result)
        
        # 統計情報
        ai_count = sum(1 for c in animated_clips if c.clip_id.startswith('ai_'))
        simple_count = len(animated_clips) - ai_count
        
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Phase 4 Completed!")
        self.logger.info("=" * 60)
        self.logger.info(f"Total clips: {len(animated_clips)}")
        self.logger.info(f"  - AI videos (Replicate): {ai_count}")
        self.logger.info(f"  - Simple animations: {simple_count}")
        
        return result
    
    def _should_use_ai_video(self, img_data: Dict[str, Any], section_info: Dict[str, Any]) -> bool:
        """AI動画を使用すべきか判定"""
        classification = img_data.get('classification', '').lower()
        atmosphere = section_info.get('atmosphere', '').lower()
        
        # 重要なシーン（battle分類）
        if classification == 'battle':
            self.logger.debug("→ Battle scene detected, using AI video")
            return True
        
        # セクションの雰囲気が劇的（日本語・英語両対応）
        dramatic_keywords = ['劇的', '悲劇的', 'dramatic', 'tragic', 'intense', 'tense']
        if any(keyword in atmosphere for keyword in dramatic_keywords):
            self.logger.debug(f"→ Dramatic atmosphere '{atmosphere}', using AI video")
            return True
        
        # ランダムで20%の確率
        use_random = random.random() < 0.2
        if use_random:
            self.logger.debug("→ Randomly selected for AI video (20% chance)")
        
        return use_random
    
    def _create_ai_video_replicate(
        self,
        img_data: Dict[str, Any],
        section_info: Dict[str, Any]
    ) -> AnimatedClip:
        """Replicate経由でKling AIを使用してAI動画を生成"""
        
        import replicate
        
        img_path = Path(img_data['file_path'])
        image_id = img_data['image_id']
        
        # 動きのプロンプトを生成
        motion_prompt = self._generate_motion_prompt(section_info, img_data.get('classification', 'general'))
        duration = self.phase_config.get('ai_video_duration', 5)
        
        self.logger.debug(f"Using prompt: {motion_prompt}")
        self.logger.debug(f"Duration: {duration}s")
        
        # Replicateクライアント初期化
        os.environ["REPLICATE_API_TOKEN"] = self.replicate_api_key
        
        # 画像ファイルを開く
        with open(img_path, 'rb') as image_file:
            # Kling v2.1 モデルで予測を作成
            prediction = replicate.predictions.create(
                model="kwaivgi/kling-v2.1",
                input={
                    "prompt": motion_prompt if motion_prompt else "cinematic motion",
                    "start_image": image_file,
                    "duration": duration,
                    "cfg_scale": 0.5,
                    "aspect_ratio": "16:9"
                }
            )
        
        prediction_id = prediction.id
        self.logger.info(f"→ Prediction created: {prediction_id}")
        
        # ポーリングで完了を待つ
        max_wait = self.phase_config.get('max_polling_attempts', 60) * self.phase_config.get('poll_interval_seconds', 10)
        check_interval = self.phase_config.get('poll_interval_seconds', 10)
        
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            
            if elapsed > max_wait:
                raise TimeoutError(f"Prediction timed out after {max_wait}s")
            
            # 予測をリロード
            prediction.reload()
            status = prediction.status
            
            if status == "succeeded":
                video_url = prediction.output
                self.logger.info(f"→ Prediction completed in {elapsed:.1f}s")
                break
            
            elif status == "failed":
                error_msg = getattr(prediction, 'error', 'Unknown error')
                raise RuntimeError(f"Prediction failed: {error_msg}")
            
            elif status in ["starting", "processing"]:
                self.logger.debug(f"→ Status: {status}, waiting... ({elapsed:.0f}s)")
                time.sleep(check_interval)
            
            else:
                self.logger.warning(f"→ Unknown status: {status}")
                time.sleep(check_interval)
        
        # 動画をダウンロード
        output_path = self.output_dir / f"ai_{image_id}.mp4"
        self._download_video(video_url, output_path)
        
        # AnimatedClipモデルを作成
        animated_clip = AnimatedClip(
            clip_id=f"ai_{image_id}",
            source_image_id=image_id,
            output_path=str(output_path),
            animation_type=AnimationType.STATIC,
            duration=duration,
            resolution=(1920, 1080)
        )
        
        self.logger.info(f"→ ✓ AI video created: {output_path.name}")
        return animated_clip
    
    def _download_video(self, url: str, output_path: Path):
        """動画をダウンロード"""
        self.logger.debug(f"→ Downloading video from {url}")
        
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        self.logger.debug(f"→ Downloaded to {output_path}")
    
    def _generate_motion_prompt(self, section_info: Dict[str, Any], classification: str) -> str:
        """画像タイプと雰囲気に応じた動きプロンプトを生成"""
        
        atmosphere = section_info.get('atmosphere', '壮大').lower()
        
        # 雰囲気に応じた動き（日本語・英語両対応）
        atmosphere_prompts = {
            # 日本語
            '壮大': 'epic cinematic camera movement',
            '劇的': 'dynamic action, intense movement',
            '悲劇的': 'slow dramatic motion, emotional depth',
            '静か': 'gentle subtle movement',
            '希望': 'uplifting camera motion',
            # 英語
            'epic': 'epic cinematic camera movement',
            'dramatic': 'dynamic action, intense movement',
            'tragic': 'slow dramatic motion, emotional depth',
            'calm': 'gentle subtle movement',
            'hopeful': 'uplifting camera motion',
            'peaceful': 'gentle subtle movement',
            'tense': 'dynamic action, intense movement'
        }
        
        # 画像分類に応じた動き
        classification_prompts = {
            'portrait': 'subtle facial expressions, slight head movement',
            'landscape': 'slow panning, atmospheric depth',
            'architecture': 'architectural reveal, slow camera movement',
            'battle': 'dynamic battle action, intense motion',
            'daily_life': '',
            'document': ''
        }
        
        motion_parts = []
        
        if atmosphere in atmosphere_prompts:
            motion_parts.append(atmosphere_prompts[atmosphere])
        
        if classification in classification_prompts and classification_prompts[classification]:
            motion_parts.append(classification_prompts[classification])
        
        return ', '.join(motion_parts) if motion_parts else 'cinematic motion'
    
    def _get_section_for_image(self, img_data: Dict[str, Any]) -> Dict[str, Any]:
        """画像が属するセクション情報を取得"""
        filename = Path(img_data['file_path']).stem
        
        if 'section_' in filename:
            parts = filename.split('_')
            for i, part in enumerate(parts):
                if part == 'section' and i + 1 < len(parts):
                    try:
                        section_id = int(parts[i + 1])
                        for section in self.script_data['sections']:
                            if section['section_id'] == section_id:
                                return section
                    except (ValueError, KeyError):
                        pass
        
        return self.script_data['sections'][0] if self.script_data['sections'] else {
            'section_id': 0,
            'title': 'Unknown',
            'atmosphere': '壮大',
            'narration': ''
        }
    
    def _create_simple_animation(
        self,
        img_data: Dict[str, Any],
        section_info: Dict[str, Any]
    ) -> AnimatedClip:
        """簡易アニメーション（パンのみ）を作成"""
        
        img_path = Path(img_data['file_path'])
        image_id = img_data['image_id']
        classification = img_data.get('classification', 'general')
        
        img = Image.open(img_path)
        img_array = np.array(img)
        
        animation_type = self._select_animation_type(classification, img_data)
        duration = self.phase_config.get('default_clip_duration', 8)
        fps = self.phase_config.get('output', {}).get('fps', 30)
        
        def make_frame(t):
            progress = t / duration
            
            if animation_type == AnimationType.PAN_RIGHT:
                return self._apply_pan_right(img_array, progress)
            elif animation_type == AnimationType.PAN_LEFT:
                return self._apply_pan_left(img_array, progress)
            elif animation_type == AnimationType.TILT_CORRECT:
                return self._apply_tilt_correct(img_array, progress)
            else:
                return img_array
        
        video_clip = VideoClip(make_frame, duration=duration)
        video_clip = video_clip.with_fps(fps)
        
        output_filename = f"simple_{image_id}.mp4"
        output_path = self.output_dir / output_filename
        
        codec = self.phase_config.get('output', {}).get('codec', 'libx264')
        
        video_clip.write_videofile(
            str(output_path),
            codec=codec,
            fps=fps,
            logger=None
        )
        
        animated_clip = AnimatedClip(
            clip_id=f"simple_{image_id}",
            source_image_id=image_id,
            output_path=str(output_path),
            animation_type=animation_type,
            duration=duration,
            resolution=tuple(img_array.shape[1::-1])
        )
        
        self.logger.info(f"→ ✓ Simple animation created: {output_filename} ({animation_type.value})")
        
        return animated_clip
    
    def _select_animation_type(self, classification: str, img_data: Dict[str, Any]) -> AnimationType:
        """アニメーションタイプを選択"""
        aspect_ratio = img_data.get('aspect_ratio', 1.0)
        
        if aspect_ratio > 1.5:
            return AnimationType.TILT_CORRECT
        
        type_mapping = {
            'portrait': AnimationType.PAN_RIGHT,
            'landscape': AnimationType.PAN_LEFT,
            'architecture': AnimationType.TILT_CORRECT,
            'battle': AnimationType.PAN_LEFT,
            'daily_life': AnimationType.PAN_LEFT,
            'document': AnimationType.STATIC
        }
        
        base_type = type_mapping.get(classification, AnimationType.PAN_LEFT)
        
        if base_type == AnimationType.PAN_LEFT and random.random() < 0.5:
            return AnimationType.PAN_RIGHT
        elif base_type == AnimationType.PAN_RIGHT and random.random() < 0.5:
            return AnimationType.PAN_LEFT
        
        return base_type
    
    def _apply_pan_right(self, img_array: np.ndarray, progress: float) -> np.ndarray:
        """右パン"""
        h, w = img_array.shape[:2]
        distance_percent = self.phase_config.get('animation_patterns', {}).get('pan_right', {}).get('distance_percent', 10)
        max_offset = int(w * (distance_percent / 100))
        offset = int(max_offset * progress)
        
        if offset > 0:
            result = np.zeros_like(img_array)
            result[:, offset:] = img_array[:, :w-offset]
            result[:, :offset] = img_array[:, :1]
            return result
        
        return img_array
    
    def _apply_pan_left(self, img_array: np.ndarray, progress: float) -> np.ndarray:
        """左パン"""
        h, w = img_array.shape[:2]
        distance_percent = self.phase_config.get('animation_patterns', {}).get('pan_left', {}).get('distance_percent', 10)
        max_offset = int(w * (distance_percent / 100))
        offset = int(max_offset * progress)
        
        if offset > 0:
            result = np.zeros_like(img_array)
            result[:, :w-offset] = img_array[:, offset:]
            result[:, w-offset:] = img_array[:, -1:]
            return result
        
        return img_array
    
    def _apply_tilt_correct(self, img_array: np.ndarray, progress: float) -> np.ndarray:
        """傾き補正風"""
        h, w = img_array.shape[:2]
        max_offset = int(h * 0.05)
        offset = int(max_offset * progress)
        
        if offset > 0:
            result = np.zeros_like(img_array)
            result[offset:, :] = img_array[:h-offset, :]
            result[:offset, :] = img_array[:1, :]
            return result
        
        return img_array
    
    def _save_animation_plan(self, result: ImageAnimationResult):
        """アニメーション計画を保存"""
        plan = {
            'subject': result.subject,
            'generated_at': result.generated_at.isoformat(),
            'total_clips': len(result.animated_clips),
            'animated_clips': [
                {
                    'clip_id': clip.clip_id,
                    'source_image_id': clip.source_image_id,
                    'output_path': clip.output_path,
                    'animation_type': clip.animation_type.value,
                    'duration': clip.duration,
                    'resolution': list(clip.resolution),
                    'start_time': clip.start_time
                }
                for clip in result.animated_clips
            ]
        }
        
        plan_path = self.output_dir / "animation_plan.json"
        with open(plan_path, 'w', encoding='utf-8') as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"\n✓ Saved animation plan to {plan_path}")
    
    def validate_output(self, output: ImageAnimationResult) -> bool:
        """出力検証"""
        if not output.animated_clips:
            self.logger.error("No animated clips generated")
            return False
        
        for clip in output.animated_clips:
            if not Path(clip.output_path).exists():
                self.logger.error(f"Output file not found: {clip.output_path}")
                return False
        
        self.logger.info(f"✓ Validation passed: {len(output.animated_clips)} clips")
        return True
    
    def _get_current_datetime(self):
        from datetime import datetime
        return datetime.now()