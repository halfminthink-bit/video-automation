"""
Phase 3: AI画像生成（Stable Diffusion専用）- 修正版

台本のキーワードに基づいて、Stable Diffusionで画像を生成する。
各セクションごとに適切な枚数の画像を生成。

修正点:
- get_phase_directory()を実装
- config.get_phase_dir()の代わりにworking_dirを直接使用
"""

import json
import logging
from pathlib import Path
from typing import List, Dict
from datetime import datetime

from src.core.phase_base import PhaseBase
from src.core.models import (
    ImageCollection,
    CollectedImage,
    ImageClassification,
    VideoScript
)
from src.core.config_manager import ConfigManager
from src.generators.image_generator import ImageGenerator
from src.utils.image_resizer import resize_images_to_1920x1080


class Phase03Images(PhaseBase):
    """
    Phase 3: AI画像生成（Stable Diffusion）
    
    処理フロー:
    1. 台本を読み込み
    2. セクションごとにキーワードを抽出
    3. キーワードごとにSD画像を生成
       - Claudeでプロンプト最適化
       - スタイル自動選択
    4. 生成結果を保存
    """
    
    def __init__(
        self,
        subject: str,
        config: ConfigManager,
        logger: logging.Logger,
        genre: str = None
    ):
        # PhaseBaseの初期化（working_dir, phase_dirなどを自動設定）
        super().__init__(subject, config, logger)

        # ジャンル設定
        self.genre = genre

        # Phase設定を読み込み
        self.phase_config = self._load_phase_config()

        # KeywordGenerator（遅延初期化）
        self.keyword_generator = None
    
    def get_phase_number(self) -> int:
        return 3
    
    def get_phase_name(self) -> str:
        return "AI Image Generation"
    
    def _load_phase_config(self) -> dict:
        """Phase 3の設定を読み込み"""
        try:
            return self.config.get_phase_config(self.get_phase_number())
        except Exception as e:
            self.logger.warning(f"Failed to load phase config: {e}")
            # デフォルト設定
            return {
                "images_per_section": 3,
                "ai_generation": {
                    "enabled": True,
                    "service": "stable-diffusion",
                    "stability_api_key_env": "STABILITY_API_KEY",
                    "claude_api_key_env": "CLAUDE_API_KEY",
                    "optimize_prompts": True
                },
                "validation": {
                    "min_images": 10
                }
            }
    
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
            self.phase_dir / "generation_log.json"
        ]
    
    def execute_phase(self) -> ImageCollection:
        """Phase 3の実行"""
        self.logger.info(f"Starting AI image generation for {self.subject}")
        
        # 1. 台本を読み込み
        script = self._load_script()
        self.logger.info(f"Loaded script with {len(script.sections)} sections")
        
        # 2. 画像生成の準備
        generated_dir = self.phase_dir / "generated"
        generated_dir.mkdir(parents=True, exist_ok=True)
        
        # 3. AI画像生成器を初期化
        generator = self._create_generator(generated_dir)
        
        # 4. セクションごとに画像を生成
        all_images = []
        total_cost = 0.0
        
        images_per_section = self.phase_config.get("images_per_section", 3)
        
        # 画像枚数の動的調整設定
        dynamic_count_config = self.phase_config.get("dynamic_image_count", {})
        dynamic_count_enabled = dynamic_count_config.get("enabled", False)
        
        for section_idx, section in enumerate(script.sections):
            # section.section_idを使う（1-based indexing from JSON）
            self.logger.info(f"Generating images for Section {section.section_id}: {section.title}")
            
            # セクションの長さに応じて画像枚数を調整
            target_count = images_per_section
            if dynamic_count_enabled:
                thresholds = dynamic_count_config.get("thresholds", {})
                long_threshold = thresholds.get("long", 500)
                medium_threshold = thresholds.get("medium", 300)
                
                narration_length = len(section.narration)
                if narration_length > long_threshold:
                    target_count = 5
                elif narration_length > medium_threshold:
                    target_count = 4
                else:
                    target_count = 3
                
                self.logger.info(
                    f"Dynamic image count: {target_count} images "
                    f"(narration length: {narration_length} chars)"
                )
            
            # セクションの画像を生成
            # 最初のセクションの最初の画像には is_first_image=True を渡す
            is_first_section = (section_idx == 0 and len(all_images) == 0)
            section_images = self._generate_section_images(
                generator=generator,
                section=section,
                section_id=section.section_id,  # Use 1-based section_id for filename
                target_count=target_count,
                is_first_section=is_first_section
            )
            
            all_images.extend(section_images)
            total_cost = generator.get_total_cost()
            
            self.logger.info(
                f"Section {section_idx + 1} complete: "
                f"{len(section_images)} images, "
                f"total cost: ${total_cost:.2f}"
            )
        
        self.logger.info(
            f"Total: {len(all_images)} images generated, "
            f"cost: ${total_cost:.2f}"
        )
        
        # 5. 結果を保存
        result = ImageCollection(
            subject=self.subject,
            images=all_images,
            collected_at=datetime.now()
        )

        self._save_results(result, total_cost)

        # 6. 生成した画像を1920x1080にリサイズ（PNG形式）
        self.logger.info("=" * 60)
        self.logger.info("🔄 Phase 3: Starting image resize to 1920x1080 (PNG)")
        self.logger.info("=" * 60)
        generated_dir = self.phase_dir / "generated"

        # ディレクトリ存在確認
        if not generated_dir.exists():
            self.logger.error(f"❌ Generated directory not found: {generated_dir}")
            raise FileNotFoundError(f"Directory not found: {generated_dir}")

        # リサイズ前のファイル一覧と詳細情報
        image_files = list(generated_dir.glob("*.jpg")) + list(generated_dir.glob("*.png"))
        self.logger.info(f"📁 Found {len(image_files)} images in {generated_dir}")

        # 各ファイルのサイズを確認
        from PIL import Image
        for img_file in image_files[:3]:  # 最初の3ファイルのみログ出力
            try:
                with Image.open(img_file) as img:
                    self.logger.info(f"  📐 Before resize: {img_file.name} = {img.size[0]}x{img.size[1]}")
            except Exception as e:
                self.logger.warning(f"  ⚠️  Could not read {img_file.name}: {e}")

        # リサイズ実行
        resized_files = resize_images_to_1920x1080(
            generated_dir,
            logger=self.logger,
            output_format="PNG"  # Phase 3は動画本編用にPNG形式
        )

        # リサイズ後のファイルサイズを確認
        self.logger.info("📐 Verifying resized files:")
        for resized_file in resized_files[:3]:  # 最初の3ファイルのみログ出力
            try:
                with Image.open(resized_file) as img:
                    self.logger.info(f"  ✅ After resize: {resized_file.name} = {img.size[0]}x{img.size[1]}")
            except Exception as e:
                self.logger.warning(f"  ⚠️  Could not verify {resized_file.name}: {e}")

        # リサイズ後、ImageCollectionのfile_pathを.pngに更新
        self.logger.info("=" * 60)
        self.logger.info("📝 Updating file paths to PNG in metadata...")
        self.logger.info("=" * 60)

        updated_count = 0
        for img in all_images:
            old_path = Path(img.file_path)
            if old_path.suffix.lower() == '.jpg':
                # .jpg → .png に変更
                new_path = old_path.with_suffix('.png')
                if new_path.exists():
                    img.file_path = str(new_path)
                    img.resolution = (1920, 1080)  # リサイズ後の解像度に更新
                    img.aspect_ratio = 1920 / 1080
                    updated_count += 1
                    self.logger.debug(f"  Updated: {old_path.name} → {new_path.name}")
                else:
                    self.logger.warning(f"  ⚠️  PNG not found: {new_path}")

        self.logger.info(f"✓ Updated {updated_count} file paths to PNG")

        # 更新されたImageCollectionを再作成して保存
        result = ImageCollection(
            subject=self.subject,
            images=all_images,
            collected_at=datetime.now()
        )
        self._save_results(result, total_cost)
        self.logger.info("✓ Metadata re-saved with updated PNG paths")
        self.logger.info("=" * 60)

        # リサイズ後、元のJPEGファイルを削除（PNG形式に変換されたため）
        jpeg_files = list(generated_dir.glob("*.jpg"))
        if jpeg_files:
            self.logger.info(f"🗑️  Removing {len(jpeg_files)} original JPEG files...")
            for jpeg_file in jpeg_files:
                try:
                    jpeg_file.unlink()
                    self.logger.debug(f"   Deleted: {jpeg_file.name}")
                except Exception as e:
                    self.logger.warning(f"   Failed to delete {jpeg_file.name}: {e}")
            self.logger.info(f"✓ Removed {len(jpeg_files)} original JPEG files")
        else:
            self.logger.info("ℹ️  No JPEG files to remove (all files are already PNG)")

        self.logger.info("=" * 60)
        self.logger.info(f"✅ Phase 3: Image resizing complete ({len(resized_files)} PNG files)")
        self.logger.info("=" * 60)

        # 7. 統計情報をログ出力
        self._log_statistics(result, total_cost)

        return result
    
    def validate_output(self, output: ImageCollection) -> bool:
        """出力のバリデーション"""
        if not isinstance(output, ImageCollection):
            return False
        
        if len(output.images) == 0:
            self.logger.warning("No images generated!")
            return False
        
        # 最低限の画像数チェック
        min_images = self.phase_config.get("validation", {}).get("min_images", 10)
        if len(output.images) < min_images:
            self.logger.warning(
                f"Only {len(output.images)} images generated "
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
    
    def _create_generator(self, output_dir: Path) -> ImageGenerator:
        """AI画像生成器を作成"""
        ai_config = self.phase_config.get("ai_generation", {})
        
        if not ai_config.get("enabled", True):
            raise Exception("AI generation is disabled in config")
        
        service = ai_config.get("service", "stable-diffusion")
        
        # APIキーを取得
        if service == "stable-diffusion":
            api_key_env = ai_config.get("stability_api_key_env", "STABILITY_API_KEY")
        else:
            api_key_env = ai_config.get("openai_api_key_env", "OPENAI_API_KEY")
        
        try:
            api_key = self.config.get_api_key(api_key_env)
        except Exception as e:
            raise Exception(f"API key not found: {api_key_env}") from e
        
        # Claudeキー（プロンプト最適化用、オプション）
        claude_key = None
        if ai_config.get("optimize_prompts", True):
            claude_key_env = ai_config.get("claude_api_key_env", "CLAUDE_API_KEY")
            try:
                claude_key = self.config.get_api_key(claude_key_env)
                self.logger.info("Prompt optimization enabled")
            except Exception:
                self.logger.warning("Claude API key not found, using simple prompts")
        
        # キャッシュディレクトリ
        cache_dir = Path(self.config.get("paths.cache_dir", "data/cache")) / "generated_images"

        # ジャンル設定に基づくプロンプトテンプレート
        prompt_template = None
        if self.genre:
            try:
                genre_config = self.config.get_genre_config(self.genre)
                template_path = genre_config["prompts"]["image"]
                prompt_template = self.config.load_prompt_template(template_path)
                self.logger.info(f"Using genre-specific image prompt template: {template_path}")
            except Exception as e:
                self.logger.warning(f"Failed to load genre template: {e}, using default")

        generator = ImageGenerator(
            api_key=api_key,
            service=service,
            claude_api_key=claude_key,
            output_dir=output_dir,
            cache_dir=cache_dir,
            logger=self.logger
        )

        # プロンプトテンプレートをgeneratorに渡す（あれば）
        if prompt_template:
            generator.prompt_template = prompt_template
            generator.template_subject = self.subject

        return generator
    
    def _generate_section_images(
        self,
        generator: ImageGenerator,
        section,
        section_id: int,
        target_count: int,
        is_first_section: bool = False
    ) -> List[CollectedImage]:
        """
        セクションの画像を生成

        Args:
            generator: ImageGenerator
            section: ScriptSection
            section_id: セクションID
            target_count: 生成する画像数
            is_first_section: 最初のセクションかどうか

        Returns:
            生成された画像のリスト
        """
        images = []

        # キーワードを安全に取得（存在しない、None、空リストの全てに対応）
        image_keywords = getattr(section, 'image_keywords', None) or []
        keywords = image_keywords[:target_count]

        # 🔥 キーワードが不足している場合、Claude APIで自動生成
        if len(keywords) < target_count:
            self.logger.warning(
                f"Section {section_id} has insufficient keywords "
                f"({len(keywords)}/{target_count}). "
                f"Generating additional keywords via Claude API..."
            )

            # 不足分を計算
            needed_count = target_count - len(keywords)

            # Claude APIでキーワード生成
            generated_keywords = self._generate_keywords_for_section(
                section=section,
                count=needed_count
            )

            # 既存のキーワードに追加
            keywords.extend(generated_keywords)

            # target_count分だけ取得
            keywords = keywords[:target_count]

            self.logger.info(
                f"Final keywords for Section {section_id}: {keywords}"
            )

        # Phase 03専用: SD生成サイズを設定ファイルから取得
        sd_config = self.phase_config.get("ai_generation", {}).get("stable_diffusion", {})
        width = sd_config.get("width", 1344)
        height = sd_config.get("height", 768)

        self.logger.info(f"🔧 Phase 03 SD generation size: {width}x{height} (from config)")

        # 各キーワードで画像生成
        for idx, keyword in enumerate(keywords):
            try:
                # 画像タイプを推測
                image_type = self._infer_image_type(keyword)
                
                # スタイルを決定
                style = self._select_style(image_type, section.atmosphere)
                
                self.logger.info(
                    f"  [{idx+1}/{len(keywords)}] Generating: {keyword} "
                    f"(type={image_type}, style={style})"
                )
                
                # デバッグモード: セクション情報をログ出力
                debug_config = self.phase_config.get("debug", {})
                if debug_config.get("enabled", False):
                    if debug_config.get("log_section_context", False):
                        self.logger.debug(f"Section context: {section.title}")
                        self.logger.debug(f"Narration: {section.narration[:100]}...")
                        self.logger.debug(f"Keywords: {section.image_keywords}")
                        self.logger.debug(f"Atmosphere: {section.atmosphere}")
                
                # セクションの本文も文脈として使用（最初の200文字）
                section_context_with_narration = f"{section.title}: {section.narration[:200]}"
                
                # 画像生成（最初の画像のみ is_first_image=True）
                # Phase 03専用: 設定ファイルから取得したサイズを指定
                is_first_image = is_first_section and idx == 0
                image = generator.generate_image(
                    keyword=keyword,
                    atmosphere=section.atmosphere,
                    section_context=section_context_with_narration,
                    image_type=image_type,
                    style=style,
                    section_id=section_id,
                    is_first_image=is_first_image,
                    width=width,
                    height=height
                )
                
                images.append(image)
                
            except Exception as e:
                self.logger.error(f"Failed to generate image for '{keyword}': {e}")
                # エラーが起きても続行
                continue
        
        return images
    
    def _infer_image_type(self, keyword: str) -> str:
        """キーワードから画像タイプを推測"""
        keyword_lower = keyword.lower()
        
        if any(word in keyword_lower for word in [
            "portrait", "warlord", "samurai", "shogun", 
            "人物", "肖像", "武将", "person"
        ]):
            return "portrait"
        
        if any(word in keyword_lower for word in [
            "battle", "war", "fight", "combat", "siege",
            "戦い", "合戦", "決戦", "戦闘"
        ]):
            return "battle"
        
        if any(word in keyword_lower for word in [
            "castle", "temple", "shrine", "palace", "architecture",
            "城", "寺", "神社", "建築"
        ]):
            return "architecture"
        
        if any(word in keyword_lower for word in [
            "landscape", "mountain", "river", "nature", "scenery",
            "風景", "山", "川", "自然"
        ]):
            return "landscape"
        
        if any(word in keyword_lower for word in [
            "document", "manuscript", "scroll", "text",
            "古文書", "文書", "巻物"
        ]):
            return "document"
        
        return "general"
    
    def _select_style(self, image_type: str, atmosphere: str) -> str:
        """画像タイプと雰囲気からスタイルを選択"""
        sd_config = self.phase_config.get("ai_generation", {}).get("stable_diffusion", {})
        style_mapping = sd_config.get("style_mapping", {})
        
        if image_type in style_mapping:
            return style_mapping[image_type]
        
        return sd_config.get("default_style", "photorealistic")
    
    def _save_results(self, result: ImageCollection, total_cost: float):
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
        
        # generation_log.json
        log_data = {
            "subject": self.subject,
            "generated_at": result.collected_at.isoformat(),
            "total_images": len(result.images),
            "total_cost_usd": round(total_cost, 2),
            "service": "stable-diffusion",
            "classifications": self._count_by_classification(result.images)
        }
        
        log_path = self.phase_dir / "generation_log.json"
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
    
    def _log_statistics(self, result: ImageCollection, total_cost: float):
        """統計情報をログ出力"""
        total = len(result.images)
        
        self.logger.info("=" * 60)
        self.logger.info("AI Image Generation Statistics")
        self.logger.info("=" * 60)
        self.logger.info(f"Total images: {total}")
        self.logger.info(f"Total cost: ${total_cost:.2f} USD")
        if total > 0:
            self.logger.info(f"Average cost: ${total_cost/total:.4f} per image")
        
        # 分類別
        by_classification = self._count_by_classification(result.images)
        self.logger.info(f"\nBy classification:")
        for classification, count in by_classification.items():
            percentage = (count / total * 100) if total > 0 else 0
            self.logger.info(f"  {classification}: {count} ({percentage:.1f}%)")
        
        self.logger.info("=" * 60)
    
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

    def _generate_keywords_for_section(
        self,
        section,
        count: int
    ) -> List[str]:
        """
        Claude APIを使ってセクション用のキーワードを生成

        Args:
            section: ScriptSection
            count: 生成するキーワード数

        Returns:
            生成されたキーワードのリスト
        """
        # KeywordGeneratorが未初期化なら初期化
        if not hasattr(self, 'keyword_generator') or self.keyword_generator is None:
            try:
                api_key = self.config.get_api_key("CLAUDE_API_KEY")
            except Exception as e:
                self.logger.error(f"CLAUDE_API_KEY not found: {e}. Cannot generate keywords.")
                # フォールバック
                return [self.subject] * count

            from src.generators.keyword_generator import KeywordGenerator
            self.keyword_generator = KeywordGenerator(
                api_key=api_key,
                logger=self.logger
            )

        # キーワード生成
        keywords = self.keyword_generator.generate_keywords(
            section_title=section.title,
            narration=section.narration,
            atmosphere=section.atmosphere,
            subject=self.subject,
            target_count=count
        )

        return keywords