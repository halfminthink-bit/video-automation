"""
Phase 3: 画像収集・生成

台本のキーワードに基づいて、最適な画像を収集または生成する。
ハイブリッド戦略: 無料素材検索 + AI生成
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from ..core.phase_base import PhaseBase
from ..core.models import (
    ImageCollection,
    CollectedImage,
    ImageClassification,
    VideoScript
)
from ..core.config_manager import ConfigManager
from ..core.exceptions import PhaseExecutionError, MissingAPIKeyError
from ..generators.image_collector import ImageCollector
from ..utils.logger import log_progress


class Phase03Images(PhaseBase):
    """
    Phase 3: 画像収集・生成
    
    処理フロー:
    1. 台本から画像キーワードを抽出
    2. 各キーワードに対して最適な戦略を決定
       - 無料素材で検索 (Wikimedia, Pexels, Unsplash)
       - AI生成 (DALL-E 3) ※将来実装
    3. 画像をダウンロード/生成
    4. 品質フィルタリング
    5. 分類（Claude APIまたはパターンマッチ）
    """
    
    def get_phase_number(self) -> int:
        return 3
    
    def get_phase_name(self) -> str:
        return "Image Collection"
    
    def check_inputs_exist(self) -> bool:
        """Phase 1の台本が必要"""
        script_path = self.config.get_phase_dir(self.subject, 1) / "script.json"
        return script_path.exists()
    
    def check_outputs_exist(self) -> bool:
        """classified.jsonが存在すればスキップ可能"""
        classified_path = self.phase_dir / "classified.json"
        
        if not classified_path.exists():
            return False
        
        # 画像ファイルも存在するか確認
        try:
            with open(classified_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            images = data.get("images", [])
            if len(images) == 0:
                return False
            
            # 最初の数枚のファイルが実際に存在するか確認
            for img in images[:3]:
                if not Path(img["file_path"]).exists():
                    return False
            
            return True
            
        except Exception:
            return False
    
    def get_input_paths(self) -> List[Path]:
        """入力ファイルパスのリスト"""
        return [
            self.config.get_phase_dir(self.subject, 1) / "script.json"
        ]
    
    def get_output_paths(self) -> List[Path]:
        """出力ファイルパスのリスト"""
        return [
            self.phase_dir / "classified.json",
            self.phase_dir / "download_log.json"
        ]
    
    def execute_phase(self) -> ImageCollection:
        """Phase 3の実行"""
        self.logger.info(f"Starting image collection for {self.subject}")
        
        # 1. 台本を読み込み
        script = self._load_script()
        self.logger.info(f"Loaded script with {len(script.sections)} sections")
        
        # 2. キーワードを抽出
        all_keywords = self._extract_keywords(script)
        self.logger.info(f"Extracted {len(all_keywords)} unique keywords")
        
        # 3. 画像収集の準備
        collected_dir = self.phase_dir / "collected"
        collected_dir.mkdir(parents=True, exist_ok=True)
        
        # 4. 画像コレクターを初期化
        collector = self._create_collector(collected_dir)
        
        # 5. 画像を収集
        target_count = self.phase_config.get("target_count_per_section", 3) * len(script.sections)
        min_width = self.phase_config.get("quality_filters", {}).get("min_width", 1280)
        min_height = self.phase_config.get("quality_filters", {}).get("min_height", 720)
        
        self.logger.info(f"Collecting {target_count} images...")
        
        collected_images = collector.collect_images(
            keywords=all_keywords,
            target_count=target_count,
            min_width=min_width,
            min_height=min_height
        )
        
        self.logger.info(f"Collected {len(collected_images)} images")
        
        # 6. 画像を分類
        classified_images = self._classify_images(collected_images)
        
        # 7. 結果を保存
        result = ImageCollection(
            subject=self.subject,
            images=classified_images,
            collected_at=datetime.now()
        )
        
        self._save_results(result)
        
        # 8. 統計情報をログ出力
        self._log_statistics(result)
        
        return result
    
    def validate_output(self, output: ImageCollection) -> bool:
        """出力のバリデーション"""
        if not isinstance(output, ImageCollection):
            return False
        
        if len(output.images) == 0:
            self.logger.warning("No images collected!")
            return False
        
        # 最低限の画像数チェック
        min_images = self.phase_config.get("validation", {}).get("min_images", 10)
        if len(output.images) < min_images:
            self.logger.warning(
                f"Only {len(output.images)} images collected "
                f"(minimum: {min_images})"
            )
        
        # ファイルが実際に存在するかチェック
        missing_count = 0
        for img in output.images:
            if not Path(img.file_path).exists():
                missing_count += 1
        
        if missing_count > 0:
            self.logger.error(f"{missing_count} image files are missing!")
            return False
        
        return True
    
    def _load_script(self) -> VideoScript:
        """台本を読み込み"""
        script_path = self.config.get_phase_dir(self.subject, 1) / "script.json"
        
        with open(script_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return VideoScript(**data)
    
    def _extract_keywords(self, script: VideoScript) -> List[str]:
        """台本からキーワードを抽出"""
        all_keywords = []
        
        for section in script.sections:
            all_keywords.extend(section.image_keywords)
        
        # 重複を削除してユニーク化
        unique_keywords = list(set(all_keywords))
        
        # 空のキーワードを除外
        unique_keywords = [kw for kw in unique_keywords if kw.strip()]
        
        return unique_keywords
    
    def _create_collector(self, output_dir: Path) -> ImageCollector:
        """画像コレクターを作成"""
        # ソース設定を読み込み
        sources_config = self.phase_config.get("sources", [])
        
        # APIキーを環境変数から取得
        for source in sources_config:
            api_key_env = source.get("api_key_env")
            if api_key_env:
                api_key = os.getenv(api_key_env)
                if api_key:
                    source["api_key"] = api_key
                else:
                    self.logger.warning(
                        f"API key not found: {api_key_env} "
                        f"(source: {source['name']})"
                    )
        
        return ImageCollector(
            sources_config=sources_config,
            output_dir=output_dir,
            logger=self.logger
        )
    
    def _classify_images(self, images: List[CollectedImage]) -> List[CollectedImage]:
        """
        画像を分類
        
        Args:
            images: 収集した画像のリスト
            
        Returns:
            分類済み画像のリスト
        """
        classification_config = self.phase_config.get("classification", {})
        use_claude = classification_config.get("use_claude_api", False)
        
        if use_claude:
            # Claude APIで分類（高精度だが遅い）
            self.logger.info("Classifying images with Claude API...")
            return self._classify_with_claude(images)
        else:
            # パターンマッチングで分類（高速）
            self.logger.info("Classifying images with pattern matching...")
            return self._classify_with_pattern(images)
    
    def _classify_with_pattern(
        self,
        images: List[CollectedImage]
    ) -> List[CollectedImage]:
        """
        パターンマッチングで分類（高速）
        
        キーワードから推測して分類する。
        """
        for img in images:
            # キーワードを小文字に変換
            keywords_lower = [kw.lower() for kw in img.keywords]
            keywords_str = " ".join(keywords_lower)
            
            # パターンマッチング
            if any(word in keywords_str for word in ["portrait", "warlord", "samurai", "person", "man", "woman"]):
                img.classification = ImageClassification.PORTRAIT
            elif any(word in keywords_str for word in ["castle", "architecture", "building", "temple", "shrine"]):
                img.classification = ImageClassification.ARCHITECTURE
            elif any(word in keywords_str for word in ["battle", "war", "fight", "combat"]):
                img.classification = ImageClassification.BATTLE
            elif any(word in keywords_str for word in ["landscape", "mountain", "river", "nature", "scenery"]):
                img.classification = ImageClassification.LANDSCAPE
            elif any(word in keywords_str for word in ["document", "manuscript", "scroll", "text"]):
                img.classification = ImageClassification.DOCUMENT
            else:
                img.classification = ImageClassification.DAILY_LIFE
        
        return images
    
    def _classify_with_claude(
        self,
        images: List[CollectedImage]
    ) -> List[CollectedImage]:
        """
        Claude APIで分類（高精度）
        
        注: 実装は将来的に追加
        現在はパターンマッチングにフォールバック
        """
        self.logger.warning(
            "Claude API classification not implemented yet. "
            "Falling back to pattern matching."
        )
        return self._classify_with_pattern(images)
    
    def _save_results(self, result: ImageCollection):
        """結果を保存"""
        # classified.json
        classified_path = self.phase_dir / "classified.json"
        with open(classified_path, 'w', encoding='utf-8') as f:
            json.dump(
                result.model_dump(mode='json'),
                f,
                indent=2,
                ensure_ascii=False,
                default=str
            )
        
        self.logger.info(f"Results saved: {classified_path}")
        
        # download_log.json（詳細ログ）
        log_data = {
            "subject": self.subject,
            "collected_at": result.collected_at.isoformat(),
            "total_images": len(result.images),
            "sources": self._count_by_source(result.images),
            "classifications": self._count_by_classification(result.images)
        }
        
        log_path = self.phase_dir / "download_log.json"
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
    
    def _log_statistics(self, result: ImageCollection):
        """統計情報をログ出力"""
        total = len(result.images)
        
        # ソース別
        by_source = self._count_by_source(result.images)
        self.logger.info("=" * 60)
        self.logger.info("Image Collection Statistics")
        self.logger.info("=" * 60)
        self.logger.info(f"Total images: {total}")
        self.logger.info(f"\nBy source:")
        for source, count in by_source.items():
            percentage = (count / total * 100) if total > 0 else 0
            self.logger.info(f"  {source}: {count} ({percentage:.1f}%)")
        
        # 分類別
        by_classification = self._count_by_classification(result.images)
        self.logger.info(f"\nBy classification:")
        for classification, count in by_classification.items():
            percentage = (count / total * 100) if total > 0 else 0
            self.logger.info(f"  {classification}: {count} ({percentage:.1f}%)")
        
        self.logger.info("=" * 60)
    
    def _count_by_source(self, images: List[CollectedImage]) -> Dict[str, int]:
        """ソース別にカウント"""
        counts = {}
        for img in images:
            source = img.source
            counts[source] = counts.get(source, 0) + 1
        return counts
    
    def _count_by_classification(
        self,
        images: List[CollectedImage]
    ) -> Dict[str, int]:
        """分類別にカウント"""
        counts = {}
        for img in images:
            classification = img.classification.value
            counts[classification] = counts.get(classification, 0) + 1
        return counts