"""
Phase 4: シネマティック画像加工
Phase 3で生成された画像を加工し、動画の雰囲気に合わせた素材に変換する
"""

import json
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from ..core.phase_base import PhaseBase
from ..core.config_manager import ConfigManager
from ..processors.image_filter import CinematicFilter
from ..processors.depth_estimator import DepthEstimator


class Phase04ImageProcessing(PhaseBase):
    """
    Phase 4: シネマティック画像加工
    
    処理フロー:
    1. Phase 3の出力（画像ファイル + メタデータ）を読み込む
    2. 台本データを読み込んで、セクション情報を取得
    3. 各画像に対して加工処理を適用
       - ジャンルに応じた色調補正
       - フィルムノイズ
       - ビネット
    4. 深度マップ（Depth Map）を生成
    5. 加工後の画像とメタデータを保存
    """
    
    def __init__(
        self,
        subject: str,
        config: ConfigManager,
        logger: Optional[logging.Logger] = None,
        genre: Optional[str] = None
    ):
        """
        初期化
        
        Args:
            subject: 偉人名
            config: 設定マネージャー
            logger: ロガー
            genre: ジャンル（ijin, urban等）
        """
        super().__init__(subject, config, logger)
        
        # ジャンル設定（デフォルトはijin）
        self.genre = genre or "ijin"
        
        # Phase設定を読み込み
        # Phase 4には複数の実装があるため、image_processingの設定を優先的に読み込む
        try:
            # まず04_image_processingの設定を試す
            if "04_image_processing" in self.config.phase_configs:
                self.phase_config = self.config.phase_configs["04_image_processing"]
                self.logger.debug("Loaded phase config from '04_image_processing'")
            else:
                # フォールバック: 設定ファイルを直接読み込む
                config_path = self.config.project_root / "config" / "phases" / "image_processing.yaml"
                if config_path.exists():
                    import yaml
                    with open(config_path, 'r', encoding='utf-8') as f:
                        self.phase_config = yaml.safe_load(f) or {}
                    self.logger.debug(f"Loaded phase config directly from {config_path}")
                else:
                    # 最後のフォールバック: 通常のget_phase_configを使用
                    self.phase_config = self.config.get_phase_config(self.get_phase_number())
        except Exception as e:
            self.logger.warning(f"Failed to load phase config: {e}, using empty config")
            # さらにフォールバック: デフォルト設定
            self.phase_config = {}
        
        # 出力ディレクトリ設定
        self.output_dir = self.phase_dir / "processed"
        self.depth_dir = self.phase_dir / "depth"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.depth_dir.mkdir(parents=True, exist_ok=True)
    
    def get_phase_number(self) -> int:
        """フェーズ番号を返す"""
        return 4
    
    def get_phase_name(self) -> str:
        """フェーズ名を返す"""
        return "Image Processing"
    
    def get_phase_directory(self) -> Path:
        """フェーズディレクトリパスを返す"""
        return self.working_dir / "04_processed"
    
    def check_inputs_exist(self) -> bool:
        """Phase 3の出力が存在するかチェック"""
        # classified.jsonの存在確認
        classified_path = self.working_dir / "03_images" / "classified.json"
        if not classified_path.exists():
            self.logger.error(f"classified.json not found: {classified_path}")
            return False
        
        # 画像ファイルディレクトリの存在確認
        images_dir = self.working_dir / "03_images" / "generated"
        if not images_dir.exists() or not any(images_dir.glob("*.png")):
            self.logger.error(f"No images found in: {images_dir}")
            return False
        
        return True
    
    def check_outputs_exist(self) -> bool:
        """Phase 4の出力が既に存在するかチェック"""
        processed_json = self.phase_dir / "processed_images.json"
        if not processed_json.exists():
            return False
        
        # メタデータを確認
        try:
            with open(processed_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            images = data.get('images', [])
            if len(images) == 0:
                return False
            
            # 最初の数枚のファイルが実際に存在するか確認
            for img in images[:3]:
                processed_path = Path(img.get('processed_file_path', ''))
                if not processed_path.exists():
                    return False
            
            return True
            
        except Exception:
            return False
    
    def execute_phase(self) -> Dict[str, Any]:
        """Phase 4を実行"""
        self.logger.info("=" * 60)
        self.logger.info(f"Phase 4: Image Processing for {self.subject}")
        self.logger.info(f"Genre: {self.genre}")
        self.logger.info("=" * 60)
        
        start_time = time.time()
        
        # 1. 入力ファイルを読み込む
        self.logger.info("Loading input files...")
        classified_data = self._load_classified_images()
        script_data = self._load_script()
        
        total_images = len(classified_data.get('images', []))
        self.logger.info(f"Found {total_images} images to process")
        
        # 2. 設定を取得
        genre_config = self._get_genre_config()
        filter_config = genre_config.get('filters', {})
        depth_config = genre_config.get('depth_map', {})
        depth_enabled = depth_config.get('enabled', True)
        
        # 3. プロセッサーを初期化
        self.logger.info("Initializing processors...")
        cinematic_filter = CinematicFilter(filter_config, self.logger)
        
        depth_estimator = None
        if depth_enabled:
            try:
                model_name = depth_config.get('model_type', 'LiheYoung/depth-anything-small-hf')
                use_gpu = self.phase_config.get('depth_estimation', {}).get('use_gpu', True)
                depth_estimator = DepthEstimator(
                    model_name=model_name,
                    use_gpu=use_gpu,
                    logger=self.logger
                )
                self.logger.info(f"Depth estimator initialized: {model_name}")
            except Exception as e:
                self.logger.warning(f"Failed to initialize depth estimator: {e}")
                self.logger.warning("Continuing without depth estimation")
                depth_enabled = False
        
        # 4. 各画像に対して加工処理を適用
        processed_images = []
        processing_stats = {
            'total_images': total_images,
            'success_count': 0,
            'failed_count': 0,
            'processing_times': []
        }
        
        self.logger.info("=" * 60)
        self.logger.info("Processing images...")
        self.logger.info("=" * 60)
        
        for idx, img_data in enumerate(classified_data.get('images', []), 1):
            try:
                self.logger.info(f"[{idx}/{total_images}] Processing: {Path(img_data['file_path']).name}")
                
                processing_start = time.time()
                
                # 画像を加工
                processed_img_data = self._process_image(
                    img_data,
                    script_data,
                    cinematic_filter,
                    depth_estimator,
                    depth_enabled
                )
                
                processed_images.append(processed_img_data)
                
                processing_time = time.time() - processing_start
                processing_stats['processing_times'].append(processing_time)
                processing_stats['success_count'] += 1
                
                self.logger.info(f"  ✓ Completed in {processing_time:.2f}s")
                
            except Exception as e:
                self.logger.error(f"  ✗ Failed: {e}", exc_info=True)
                processing_stats['failed_count'] += 1
                
                if not self.phase_config.get('processing', {}).get('continue_on_error', True):
                    raise
        
        # 5. メタデータを保存
        self.logger.info("=" * 60)
        self.logger.info("Saving metadata...")
        self.logger.info("=" * 60)
        
        total_time = time.time() - start_time
        avg_time = (
            sum(processing_stats['processing_times']) / len(processing_stats['processing_times'])
            if processing_stats['processing_times'] else 0
        )
        
        processing_stats['total_processing_time_seconds'] = total_time
        processing_stats['average_processing_time_seconds'] = avg_time
        
        self._save_processed_metadata(processed_images, processing_stats)
        self._save_processing_log(processing_stats)
        
        # 6. 統計情報をログ出力
        self._log_statistics(processing_stats)
        
        self.logger.info("=" * 60)
        self.logger.info(f"✅ Phase 4 completed in {total_time:.2f}s")
        self.logger.info("=" * 60)
        
        return {
            'subject': self.subject,
            'processed_images': processed_images,
            'statistics': processing_stats
        }
    
    def _load_classified_images(self) -> Dict[str, Any]:
        """classified.jsonを読み込む"""
        classified_path = self.working_dir / "03_images" / "classified.json"
        
        with open(classified_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_script(self) -> Dict[str, Any]:
        """script.jsonを読み込む"""
        script_path = self.working_dir / "01_script" / "script.json"
        
        with open(script_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _get_genre_config(self) -> Dict[str, Any]:
        """ジャンル設定を取得"""
        # Phase設定ファイルを直接読み込む（04_animationの設定が混入するのを防ぐ）
        config_path = self.config.project_root / "config" / "phases" / "image_processing.yaml"
        phase_config = {}
        
        if config_path.exists():
            try:
                import yaml
                with open(config_path, 'r', encoding='utf-8') as f:
                    phase_config = yaml.safe_load(f) or {}
                self.logger.debug(f"Loaded image_processing config from {config_path}")
            except Exception as e:
                self.logger.warning(f"Failed to load image_processing config: {e}, using phase_config")
                phase_config = self.phase_config
        else:
            # フォールバック: 既存のphase_configを使用
            phase_config = self.phase_config
            self.logger.warning(f"image_processing.yaml not found at {config_path}, using phase_config")
        
        # ジャンル設定を取得
        genre_configs = phase_config.get(self.genre, {})
        
        if not genre_configs:
            self.logger.warning(f"Genre config not found for '{self.genre}' in config keys: {list(phase_config.keys())}")
            # デフォルト設定（ijin）- ハードコードされたフォールバック
            default_config = {
                'filters': {
                    'brightness': 0.05,
                    'contrast': 1.15,
                    'saturation': 0.9,
                    'temperature': 0.1,
                    'vignette_strength': 0.3,
                    'grain_intensity': 0.05,
                    'split_tone': True,
                    'split_tone_strength': 0.3,
                    'use_s_curve': True,
                    'bloom_strength': 0.15
                },
                'depth_map': {
                    'enabled': True,
                    'model_type': 'LiheYoung/depth-anything-small-hf'
                }
            }
            self.logger.info(f"Using default config for genre '{self.genre}'")
            return default_config
        
        self.logger.debug(f"Successfully loaded genre config for '{self.genre}'")
        return genre_configs
    
    def _process_image(
        self,
        img_data: Dict[str, Any],
        script_data: Dict[str, Any],
        cinematic_filter: CinematicFilter,
        depth_estimator: Optional[DepthEstimator],
        depth_enabled: bool
    ) -> Dict[str, Any]:
        """
        1つの画像を加工処理
        
        Args:
            img_data: 画像メタデータ
            script_data: 台本データ
            cinematic_filter: 画像フィルター
            depth_estimator: 深度推定器
            depth_enabled: 深度推定を有効にするか
        
        Returns:
            加工後の画像メタデータ
        """
        # 元画像のパス
        original_path = Path(img_data['file_path'])
        if not original_path.exists():
            raise FileNotFoundError(f"Image not found: {original_path}")
        
        # セクション番号を抽出
        section_id = None
        match = re.search(r'section_(\d+)', original_path.name)
        if match:
            section_id = int(match.group(1))
        
        # 加工後の画像ファイル名を生成
        original_name = original_path.stem
        output_config = self.phase_config.get('output', {})
        processed_suffix = output_config.get('processed_suffix', '_processed')
        processed_name = f"{original_name}{processed_suffix}.png"
        processed_path = self.output_dir / processed_name
        
        # 画像を加工
        processed_img = cinematic_filter.process(original_path)
        cinematic_filter.save(processed_img, processed_path)
        
        # 深度マップを生成
        depth_path = None
        if depth_enabled and depth_estimator:
            try:
                depth_suffix = output_config.get('depth_suffix', '_depth')
                depth_name = f"{original_name}{depth_suffix}.png"
                depth_path = self.depth_dir / depth_name
                
                depth_estimator.estimate(original_path, depth_path)
                self.logger.debug(f"  Depth map saved: {depth_path.name}")
            except Exception as e:
                self.logger.warning(f"  Depth estimation failed: {e}")
                depth_path = None
        
        # メタデータを構築
        from PIL import Image
        with Image.open(processed_path) as img:
            resolution = img.size  # (width, height)
        
        processed_img_data = {
            'image_id': img_data['image_id'],
            'original_file_path': str(original_path),
            'processed_file_path': str(processed_path),
            'depth_map_path': str(depth_path) if depth_path else None,
            'processing_type': 'cinematic_filter',
            'processing_params': self._get_genre_config().get('filters', {}),
            'classification': img_data.get('classification'),
            'section_id': section_id,
            'keywords': img_data.get('keywords', []),
            'resolution': list(resolution),
            'aspect_ratio': resolution[0] / resolution[1] if resolution[1] > 0 else 1.0,
            'quality_score': img_data.get('quality_score', 0.95),
            'file_size_bytes': processed_path.stat().st_size
        }
        
        return processed_img_data
    
    def _save_processed_metadata(
        self,
        processed_images: List[Dict[str, Any]],
        processing_stats: Dict[str, Any]
    ):
        """加工後のメタデータを保存"""
        metadata = {
            'subject': self.subject,
            'genre': self.genre,
            'processed_at': datetime.now().isoformat(),
            'processing_version': '1.0.0',
            'images': processed_images,
            'statistics': {
                'total_images': processing_stats['total_images'],
                'success_count': processing_stats['success_count'],
                'failed_count': processing_stats['failed_count'],
                'total_processing_time_seconds': processing_stats['total_processing_time_seconds'],
                'average_processing_time_seconds': processing_stats['average_processing_time_seconds']
            }
        }
        
        output_path = self.phase_dir / "processed_images.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(
                metadata,
                f,
                indent=2,
                ensure_ascii=False,
                default=str
            )
        
        self.logger.info(f"Metadata saved: {output_path}")
    
    def _save_processing_log(self, processing_stats: Dict[str, Any]):
        """加工ログを保存"""
        log_data = {
            'subject': self.subject,
            'genre': self.genre,
            'processed_at': datetime.now().isoformat(),
            'total_images': processing_stats['total_images'],
            'success_count': processing_stats['success_count'],
            'failed_count': processing_stats['failed_count'],
            'total_processing_time_seconds': processing_stats['total_processing_time_seconds'],
            'processing_errors': []
        }
        
        log_path = self.phase_dir / "processing_log.json"
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Processing log saved: {log_path}")
    
    def _log_statistics(self, processing_stats: Dict[str, Any]):
        """統計情報をログ出力"""
        self.logger.info("=" * 60)
        self.logger.info("Processing Statistics")
        self.logger.info("=" * 60)
        self.logger.info(f"Total images: {processing_stats['total_images']}")
        self.logger.info(f"Success: {processing_stats['success_count']}")
        self.logger.info(f"Failed: {processing_stats['failed_count']}")
        self.logger.info(f"Total time: {processing_stats['total_processing_time_seconds']:.2f}s")
        
        if processing_stats['processing_times']:
            avg_time = processing_stats['average_processing_time_seconds']
            self.logger.info(f"Average time per image: {avg_time:.2f}s")
        
        self.logger.info("=" * 60)
    
    def validate_output(self, output: Dict[str, Any]) -> bool:
        """出力のバリデーション"""
        if not isinstance(output, dict):
            return False
        
        processed_images = output.get('processed_images', [])
        if len(processed_images) == 0:
            self.logger.warning("No processed images found")
            return False
        
        # ファイルが実際に存在するかチェック
        missing_count = 0
        for img in processed_images:
            processed_path = Path(img.get('processed_file_path', ''))
            if not processed_path.exists():
                missing_count += 1
        
        if missing_count > 0:
            self.logger.error(f"{missing_count} processed image files are missing!")
            return False
        
        self.logger.info("Output validation passed")
        return True

