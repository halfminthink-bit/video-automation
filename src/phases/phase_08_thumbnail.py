"""
Phase 8: サムネイル生成（Thumbnail Generation）

Phase 3の画像からYouTubeサムネイルを生成する
"""

import json
import sys
from pathlib import Path
from typing import List, Optional, Any, Dict
from datetime import datetime
import logging

# プロジェクトルートをパスに追加
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

from src.core.phase_base import PhaseBase
from src.core.config_manager import ConfigManager
from src.core.exceptions import (
    PhaseExecutionError,
    PhaseValidationError,
    PhaseInputMissingError
)
# 保持: 知的好奇心ジェネレーター（デフォルト）
from src.generators.intellectual_curiosity_generator import create_intellectual_curiosity_generator

# 従来の方法用（互換性のため保持）
from src.generators.thumbnail_generator import create_thumbnail_generator
from src.generators.pillow_thumbnail_generator import PillowThumbnailGenerator
from src.generators.gptimage_thumbnail_generator import GPTImageThumbnailGenerator
from src.generators.final_thumbnail_generator import FinalThumbnailGenerator
from src.generators.impact_thumbnail_generator import create_impact_thumbnail_generator

from dotenv import load_dotenv

# .envをオーバーライドで読み込み
load_dotenv(override=True)


class Phase08Thumbnail(PhaseBase):
    """Phase 8: サムネイル生成"""
    
    def get_phase_number(self) -> int:
        return 8
    
    def get_phase_name(self) -> str:
        return "Thumbnail Generation"
    
    def check_inputs_exist(self) -> bool:
        """Phase 1（台本）とPhase 3（画像）の出力を確認"""
        script_path = self.config.get_phase_dir(self.subject, 1) / "script.json"
        classified_path = self.config.get_phase_dir(self.subject, 3) / "classified.json"
        
        if not script_path.exists():
            self.logger.error(f"Script not found: {script_path}")
            return False
        
        if not classified_path.exists():
            self.logger.error(f"Classified images not found: {classified_path}")
            return False
        
        return True
    
    def check_outputs_exist(self) -> bool:
        """サムネイルファイルが存在するかチェック"""
        thumbnail_dir = self.phase_dir / "thumbnails"
        metadata_path = self.phase_dir / "metadata.json"
        
        if not thumbnail_dir.exists():
            return False
        
        # サムネイルファイルが存在するかチェック
        thumbnails = list(thumbnail_dir.glob("*.png"))
        
        exists = len(thumbnails) > 0 and metadata_path.exists()
        
        if exists:
            self.logger.info(f"Thumbnails already exist: {len(thumbnails)} files")
        
        return exists
    
    def get_output_paths(self) -> List[Path]:
        """出力ファイルのパスリスト"""
        thumbnail_dir = self.phase_dir / "thumbnails"
        return [
            thumbnail_dir,
            self.phase_dir / "metadata.json"
        ]
    
    def execute_phase(self) -> Dict[str, Any]:
        """
        サムネイル生成の実行

        Returns:
            生成されたサムネイルの情報

        Raises:
            PhaseExecutionError: 実行エラー
        """
        self.logger.info(f"Generating thumbnails for: {self.subject}")

        try:
            # 1. 台本を読み込み
            script_data = self._load_script()
            self.logger.info(f"Loaded script: {script_data.get('subject')}")

            # 2. サムネイル生成方法を確認
            # デフォルトは知的好奇心ジェネレーター
            use_intellectual_curiosity = self.phase_config.get("use_intellectual_curiosity", True)

            if use_intellectual_curiosity:
                # 知的好奇心サムネイル生成（デフォルト）
                return self._generate_with_intellectual_curiosity(script_data)

            # 画像リストを読み込み（従来の方法の場合のみ）
            images = self._load_classified_images()
            self.logger.info(f"Loaded {len(images)} images")

            if not images:
                raise PhaseExecutionError(
                    self.get_phase_number(),
                    "No images available for thumbnail generation"
                )

            # 従来の方法を確認
            use_dalle = self.phase_config.get("use_dalle", False)

            if use_dalle:
                # DALL-E 3を使用してサムネイルを生成
                return self._generate_with_dalle(script_data)
            else:
                # 従来の方法（Pillow）でサムネイルを生成
                return self._generate_with_pillow(script_data, images)

        except Exception as e:
            self.logger.error(f"Thumbnail generation failed: {e}", exc_info=True)
            raise PhaseExecutionError(
                self.get_phase_number(),
                f"Thumbnail generation failed: {e}"
            ) from e
    
    def validate_output(self, output: Dict[str, Any]) -> bool:
        """
        生成されたサムネイルをバリデーション
        
        Args:
            output: 出力データ
            
        Returns:
            バリデーション成功なら True
            
        Raises:
            PhaseValidationError: バリデーション失敗時
        """
        self.logger.info("Validating thumbnail output...")
        
        # サムネイル数チェック
        thumbnails = output.get("thumbnails", [])
        if len(thumbnails) == 0:
            raise PhaseValidationError(
                self.get_phase_number(),
                "No thumbnails generated"
            )
        
        # 各サムネイルファイルの存在チェック
        for thumbnail in thumbnails:
            file_path = Path(thumbnail["file_path"])
            if not file_path.exists():
                raise PhaseValidationError(
                    self.get_phase_number(),
                    f"Thumbnail file not found: {file_path}"
                )
            
            # ファイルサイズチェック
            file_size = file_path.stat().st_size
            if file_size < 1024:  # 1KB未満
                raise PhaseValidationError(
                    self.get_phase_number(),
                    f"Thumbnail file too small: {file_path} ({file_size} bytes)"
                )
        
        self.logger.info(f"Thumbnail validation passed ✓ ({len(thumbnails)} files)")
        return True
    
    # ========================================
    # 内部メソッド
    # ========================================
    
    def _load_script(self) -> Dict[str, Any]:
        """
        Phase 1の台本を読み込み
        
        Returns:
            台本データ
            
        Raises:
            PhaseInputMissingError: 台本ファイルが見つからない場合
        """
        script_path = self.config.get_phase_dir(self.subject, 1) / "script.json"
        
        if not script_path.exists():
            raise PhaseInputMissingError(
                self.get_phase_number(),
                [str(script_path)]
            )
        
        self.logger.debug(f"Loading script from: {script_path}")
        
        with open(script_path, 'r', encoding='utf-8') as f:
            script_data = json.load(f)
        
        return script_data
    
    def _load_classified_images(self) -> List[Dict[str, Any]]:
        """
        Phase 3の分類済み画像リストを読み込み
        
        Returns:
            画像情報のリスト
            
        Raises:
            PhaseInputMissingError: 画像ファイルが見つからない場合
        """
        classified_path = self.config.get_phase_dir(self.subject, 3) / "classified.json"
        
        if not classified_path.exists():
            raise PhaseInputMissingError(
                self.get_phase_number(),
                [str(classified_path)]
            )
        
        self.logger.debug(f"Loading classified images from: {classified_path}")
        
        with open(classified_path, 'r', encoding='utf-8') as f:
            classified_data = json.load(f)
        
        images = classified_data.get("images", [])
        
        return images
    
    def _generate_with_dalle(self, script_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        DALL-E 3 + FinalThumbnailGenerator(V3.0 - 赤文字上部＋白文字下部)でサムネイルを生成
        DALL-E 3 + ThreeZoneThumbnailGenerator(3ゾーンレイアウト)でサムネイルを生成

        Args:
            script_data: 台本データ

        Returns:
            生成結果
        """
        self.logger.info("🌟 Using DALL-E 3 + FinalThumbnailGenerator (V3.0 - Red Top / White Bottom)")

        # 出力ディレクトリを作成
        thumbnail_dir = self.phase_dir / "thumbnails"
        thumbnail_dir.mkdir(parents=True, exist_ok=True)

        # FinalThumbnailGeneratorを作成
        generator = FinalThumbnailGenerator(
            config=self.phase_config,
            logger=self.logger
        )

        # サムネイルを生成（内部でDALL-E 3呼び出し + インパクトテキスト生成）
        num_variations = self.phase_config.get("catchcopy", {}).get("num_candidates", 5)

        thumbnail_paths = generator.generate_thumbnails(
            subject=self.subject,
            script_data=script_data,
            output_dir=thumbnail_dir,
            num_variations=num_variations
        )

        if not thumbnail_paths:
            raise PhaseExecutionError(
                self.get_phase_number(),
                "Failed to generate any thumbnails with FinalThumbnailGenerator"
            )

        # 結果を作成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        generated_thumbnails = []

        for i, path in enumerate(thumbnail_paths, 1):
            generated_thumbnails.append({
                "pattern_index": i,
                "file_path": str(path),
                "file_name": path.name,
                "layout": "v3-red-white",
                "style": self.phase_config.get("dalle", {}).get("style", "dramatic")
            })

        result = {
            "subject": self.subject,
            "generated_at": timestamp,
            "method": "dall-e-3-v3-final",
            "thumbnails": generated_thumbnails,
            "total_count": len(generated_thumbnails)
        }

        self._save_metadata(result)

        self.logger.info(f"✓ {len(generated_thumbnails)} V3.0 thumbnails generated")

        return result

    def _generate_with_intellectual_curiosity(
        self,
        script_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        知的好奇心サムネイル生成（デフォルト）

        DALL-E 3で明るい人物写真を生成し、
        AIでキャッチコピーを自動生成

        Args:
            script_data: 台本データ

        Returns:
            生成結果
        """
        self.logger.info("🧠 Using Intellectual Curiosity Thumbnail Generator (Bright Photos)")

        # 出力ディレクトリを作成
        thumbnail_dir = self.phase_dir / "thumbnails"
        thumbnail_dir.mkdir(parents=True, exist_ok=True)

        # IntellectualCuriosityGeneratorを作成
        generator = create_intellectual_curiosity_generator(
            config=self.phase_config,
            logger=self.logger
        )

        # サムネイルを生成（AIが自動的にキャッチコピーを生成）
        num_variations = self.phase_config.get("num_variations", 5)

        thumbnail_paths = generator.generate_thumbnails(
            subject=self.subject,
            output_dir=thumbnail_dir,
            context=script_data,
            num_variations=num_variations
        )

        if not thumbnail_paths:
            raise PhaseExecutionError(
                self.get_phase_number(),
                "Failed to generate any thumbnails with IntellectualCuriosityGenerator"
            )

        # 結果を作成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        generated_thumbnails = []

        for i, path in enumerate(thumbnail_paths, 1):
            generated_thumbnails.append({
                "pattern_index": i,
                "file_path": str(path),
                "file_name": path.name,
                "layout": "intellectual-curiosity",
                "style": "bright-portrait"
            })

        result = {
            "subject": self.subject,
            "generated_at": timestamp,
            "method": "intellectual-curiosity",
            "thumbnails": generated_thumbnails,
            "total_count": len(generated_thumbnails)
        }

        self._save_metadata(result)

        self.logger.info(f"✓ {len(generated_thumbnails)} intellectual curiosity thumbnails generated")

        return result

    
    def _generate_with_pillow(
        self,
        script_data: Dict[str, Any],
        images: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Pillowを使用してサムネイルを生成(従来の方法)

        Args:
            script_data: 台本データ
            images: 画像リスト

        Returns:
            生成結果
        """
        self.logger.info("🖼️ Using Pillow for thumbnail generation")
        
        # サムネイル生成器を作成
        generator = create_thumbnail_generator(
            config=self.phase_config,
            logger=self.logger
        )
        
        # 最適な画像を選択
        best_image = generator.select_best_image(images)
        
        if not best_image:
            raise PhaseExecutionError(
                self.get_phase_number(),
                "Failed to select best image for thumbnail"
            )
        
        base_image_path = Path(best_image["file_path"])
        self.logger.info(f"Selected base image: {base_image_path.name}")
        
        # タイトルを生成
        titles = generator.generate_titles(self.subject, script_data)
        self.logger.info(f"Generated {len(titles)} title variations")
        
        # 出力ディレクトリを作成
        thumbnail_dir = self.phase_dir / "thumbnails"
        thumbnail_dir.mkdir(parents=True, exist_ok=True)
        
        # サムネイルを生成
        generated_thumbnails = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for i, title in enumerate(titles):
            output_filename = f"{self.subject}_thumbnail_{i+1}_{timestamp}.png"
            output_path = thumbnail_dir / output_filename
            
            self.logger.info(f"Generating thumbnail {i+1}/{len(titles)}: {title}")
            
            success = generator.create_thumbnail(
                base_image_path=base_image_path,
                title=title,
                output_path=output_path,
                pattern_index=i
            )
            
            if success:
                generated_thumbnails.append({
                    "pattern_index": i + 1,
                    "title": title,
                    "file_path": str(output_path),
                    "file_name": output_filename,
                    "base_image": str(base_image_path)
                })
        
        if not generated_thumbnails:
            raise PhaseExecutionError(
                self.get_phase_number(),
                "Failed to generate any thumbnails"
            )
        
        # 結果を作成
        result = {
            "subject": self.subject,
            "generated_at": timestamp,
            "method": "pillow",
            "base_image": {
                "file_path": str(base_image_path),
                "section_id": best_image.get("section_id"),
                "classification": best_image.get("classification")
            },
            "thumbnails": generated_thumbnails,
            "total_count": len(generated_thumbnails)
        }
        
        self._save_metadata(result)
        
        self.logger.info(
            f"✓ Thumbnail generation complete: "
            f"{len(generated_thumbnails)} thumbnails created"
        )
        
        return result
    
    def _save_metadata(self, result: Dict[str, Any]) -> None:
        """
        メタデータを保存
        
        Args:
            result: 生成結果
        """
        metadata_path = self.phase_dir / "metadata.json"
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Metadata saved: {metadata_path}")


def main():
    """Phase 8を単体で実行するためのエントリーポイント"""
    import argparse
    import logging
    
    parser = argparse.ArgumentParser(description="Phase 8: Thumbnail Generation")
    parser.add_argument("subject", help="Subject name")
    parser.add_argument("--force", action="store_true", help="Force regeneration")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # ロガー設定
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # 設定マネージャーを作成（.envの値で環境変数を上書き）
    config = ConfigManager(env_override=True)
    
    # Phase 8を実行
    phase = Phase08Thumbnail(
        subject=args.subject,
        config=config,
        logger=logger
    )
    
    try:
        result = phase.run()
        logger.info(f"Phase 8 completed successfully")

        # メタデータを読み込んで詳細を表示
        if result.status.value == "completed":
            try:
                metadata_path = phase.phase_dir / "metadata.json"
                if metadata_path.exists():
                    import json
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    logger.info(f"Generated {metadata.get('total_count', 0)} thumbnail(s)")
                    logger.info(f"Method: {metadata.get('method', 'unknown')}")
            except Exception as e:
                logger.debug(f"Could not read metadata: {e}")

    except Exception as e:
        logger.error(f"Phase 8 failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
