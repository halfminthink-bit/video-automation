"""
Phase 8: サムネイル生成（Thumbnail Generation）

Phase 3の画像からYouTubeサムネイルを生成する
"""

import json
import sys
import random
import shutil
from pathlib import Path
from typing import List, Optional, Any, Dict
from datetime import datetime
import logging
from PIL import Image, ImageDraw, ImageFont

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

    def __init__(
        self,
        subject: str,
        config: ConfigManager,
        logger: logging.Logger,
        genre: str = None,
        text_layout: str = None,
        style: str = None,
        text_only: bool = False,
        text_only_image: Optional[str] = None,
        is_batch_mode: bool = False,
        all_variations: bool = False
    ):
        super().__init__(subject, config, logger)
        self.genre = genre
        self.text_layout = text_layout
        self.style = style
        self.text_only = text_only
        self.text_only_image = text_only_image
        self.is_batch_mode = is_batch_mode
        self.all_variations = all_variations

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
        
        # サムネイルファイルが存在するかチェック（PNG/JPEG両方）
        thumbnails = list(thumbnail_dir.glob("*.png")) + \
                     list(thumbnail_dir.glob("*.jpg")) + \
                     list(thumbnail_dir.glob("*.jpeg"))

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
            # SD生成をデフォルトに設定
            use_intellectual_curiosity = self.phase_config.get("use_intellectual_curiosity", True)

            result = None

            if use_intellectual_curiosity:
                # 知的好奇心サムネイル生成（SD生成、デフォルト）
                result = self._generate_with_intellectual_curiosity(script_data)
            else:
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
                    result = self._generate_with_dalle(script_data)
                else:
                    # 従来の方法（Pillow）でサムネイルを生成
                    result = self._generate_with_pillow(script_data, images)

            # Phase 8はリサイズしない（生成されたサイズのまま保存）
            # IntellectualCuriosityGeneratorが内部で1280x720にリサイズ済み

            return result

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
            file_size_mb = file_size / (1024 * 1024)

            if file_size < 1024:  # 1KB未満
                raise PhaseValidationError(
                    self.get_phase_number(),
                    f"Thumbnail file too small: {file_path} ({file_size} bytes)"
                )

            # YouTubeの2MB制限をチェック
            if file_size > 2097152:  # 2MB = 2,097,152 bytes
                self.logger.warning(
                    f"⚠️  Thumbnail exceeds YouTube 2MB limit: {file_path.name} "
                    f"({file_size_mb:.2f} MB)"
                )
            else:
                self.logger.debug(
                    f"✓ Thumbnail size OK: {file_path.name} ({file_size_mb:.2f} MB)"
                )
        
        self.logger.info(f"Thumbnail validation passed ✓ ({len(thumbnails)} files)")
        return True
    
    # ========================================
    # 内部メソッド
    # ========================================

    def _find_layout(self, text_config: Dict[str, Any], layout_id: str) -> Dict[str, Any]:
        """
        レイアウトIDから設定を検索

        Args:
            text_config: thumbnail_text.yamlから読み込んだ設定
            layout_id: レイアウトID

        Returns:
            レイアウト設定の辞書

        Raises:
            PhaseExecutionError: レイアウトが見つからない場合
        """
        layouts = text_config.get("text_layouts", [])
        for layout in layouts:
            if layout["id"] == layout_id:
                return layout

        raise PhaseExecutionError(
            self.get_phase_number(),
            f"Text layout not found: {layout_id}"
        )

    def _find_style(self, style_config: Dict[str, Any], style_id: str) -> Dict[str, Any]:
        """
        スタイルIDから設定を検索

        Args:
            style_config: thumbnail_style.yamlから読み込んだ設定
            style_id: スタイルID

        Returns:
            スタイル設定の辞書

        Raises:
            PhaseExecutionError: スタイルが見つからない場合
        """
        styles = style_config.get("thumbnail_styles", [])
        for style in styles:
            if style["id"] == style_id:
                return style

        raise PhaseExecutionError(
            self.get_phase_number(),
            f"Thumbnail style not found: {style_id}"
        )
    
    def _merge_text_style_settings(
        self,
        layouts: List[Dict[str, Any]],
        text_style_v3: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        thumbnail_generation.yamlのtext_style_v3設定を
        thumbnail_text.yamlのレイアウト設定にマージ
        
        Args:
            layouts: レイアウト設定のリスト
            text_style_v3: thumbnail_generation.yamlのtext_style_v3設定
            
        Returns:
            マージされたレイアウト設定のリスト
        """
        main_text_style = text_style_v3.get("main_text", {})
        sub_text_style = text_style_v3.get("sub_text", {})
        
        merged_layouts = []
        for layout in layouts:
            merged_layout = layout.copy()
            
            # upper/main_textの設定をマージ
            if "upper" in merged_layout:
                upper = merged_layout["upper"].copy()
                
                # フォントサイズ範囲を適用（最大値を使用）
                if "font_size_range" in main_text_style:
                    font_size_range = main_text_style["font_size_range"]
                    if isinstance(font_size_range, list) and len(font_size_range) == 2:
                        # 範囲の最大値を使用（既存の値より大きい場合のみ）
                        max_font_size = max(font_size_range)
                        if upper.get("font_size", 0) < max_font_size:
                            upper["font_size"] = max_font_size
                            upper["font_size_range"] = font_size_range
                
                # ストローク設定をマージ
                if "stroke_black" in main_text_style:
                    upper["stroke_width"] = main_text_style["stroke_black"]
                    upper["stroke_color"] = "#000000"
                if "stroke_white" in main_text_style:
                    # 白ストロークは追加のストロークレイヤーとして保存
                    upper["stroke_white_width"] = main_text_style["stroke_white"]
                
                # シャドウ設定をマージ
                if "shadow_offset" in main_text_style:
                    shadow_offset = main_text_style["shadow_offset"]
                    shadow_blur = main_text_style.get("shadow_blur", 0)
                    if isinstance(shadow_offset, list) and len(shadow_offset) >= 2:
                        upper["shadow"] = [
                            shadow_offset[0],
                            shadow_offset[1],
                            "#000000",
                            0.8  # デフォルトの透明度
                        ]
                        upper["shadow_blur"] = shadow_blur
                
                # グラデーション設定を保存（upperテキスト用）
                if "gradient_colors" in main_text_style:
                    upper["gradient_colors"] = main_text_style["gradient_colors"]
                
                merged_layout["upper"] = upper
            
            # lower/sub_textの設定をマージ
            if "lower" in merged_layout:
                lower = merged_layout["lower"].copy()
                
                # 色を適用
                if "color" in sub_text_style:
                    lower["color"] = sub_text_style["color"]
                
                # フォントサイズを適用
                if "font_size" in sub_text_style:
                    lower["font_size"] = sub_text_style["font_size"]
                
                # ストローク設定をマージ
                if "stroke_black" in sub_text_style:
                    lower["stroke_width"] = sub_text_style["stroke_black"]
                    lower["stroke_color"] = "#000000"
                
                # 背景設定をマージ
                if "background_opacity" in sub_text_style:
                    lower["background_opacity"] = sub_text_style["background_opacity"]
                if "background_padding" in sub_text_style:
                    lower["background_padding"] = sub_text_style["background_padding"]
                if "background_blur" in sub_text_style:
                    lower["background_blur"] = sub_text_style["background_blur"]
                
                merged_layout["lower"] = lower
            
            merged_layouts.append(merged_layout)
        
        return merged_layouts

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
        
        実行モードに応じて動作を変更:
        - 一括実行時: 指定レイアウトで1枚のみ生成、variationsは生成しない
        - 単発実行時: デフォルトでリサイズ後のSD画像（テキストなし）を保存
        - text_onlyモード: 既存画像にテキストのみ追加

        Args:
            script_data: 台本データ

        Returns:
            生成結果
        """
        # text_onlyモードの処理
        if self.text_only:
            if self.all_variations:
                # text_only + all_variations: 既存画像に全レイアウトのテキストを当てる
                return self._generate_text_only_all_variations(script_data)
            else:
                # text_onlyのみ: 既存画像に指定レイアウトのテキストを当てる（1枚のみ）
                return self._generate_text_only(script_data)
        
        self.logger.info("🧠 Using Intellectual Curiosity Thumbnail Generator (Bright Photos)")

        # ジャンル別設定の読み込み
        prompt_template = None
        if self.genre:
            try:
                genre_config = self.config.get_genre_config(self.genre)
                template_path = genre_config["prompts"]["thumbnail"]
                prompt_template = self.config.load_prompt_template(template_path)
                self.logger.info(f"Using genre-specific thumbnail prompt: {template_path}")
            except Exception as e:
                self.logger.warning(f"Failed to load genre template: {e}, using default")

        # 全テキストレイアウトパターンを読み込む
        text_config = self.config.get_variation_config("thumbnail_text")
        all_layouts = text_config.get("text_layouts", [])
        
        # thumbnail_generation.yamlのtext_style_v3設定を読み込んでマージ
        # 注意: 現在は無効化。全てのテキストスタイルはthumbnail_text.yamlから選ばれる
        # phase_config = self.phase_config
        # text_style_v3 = phase_config.get("text_style_v3", {})
        # if text_style_v3:
        #     self.logger.info("Merging text_style_v3 settings from thumbnail_generation.yaml")
        #     all_layouts = self._merge_text_style_settings(all_layouts, text_style_v3)
        
        # thumbnail_text.yamlの設定をそのまま使用（text_style_v3による上書きを無効化）
        self.logger.info("Using text layouts directly from thumbnail_text.yaml (text_style_v3 merge disabled)")
        
        if not all_layouts:
            self.logger.warning("No text layouts found in thumbnail_text.yaml, using default")
            all_layouts = []

        # スタイルの読み込み
        style_config = None
        if self.style:
            try:
                style_var_config = self.config.get_variation_config("thumbnail_style")
                style_config = self._find_style(style_var_config, self.style)
                self.logger.info(f"Using thumbnail style: {self.style}")
            except Exception as e:
                self.logger.warning(f"Failed to load style: {e}, using default")

        # 出力ディレクトリを作成
        thumbnail_dir = self.phase_dir / "thumbnails"
        thumbnail_dir.mkdir(parents=True, exist_ok=True)
        
        # バリエーション保存用ディレクトリ（コードが認識しない場所）
        # thumbnails/とは別の場所に全てのバリエーションを保存
        variations_dir = self.phase_dir / "variations"
        variations_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Variations directory: {variations_dir}")

        # 全レイアウトパターンでサムネイルを生成
        all_generated_thumbnails = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 背景画像は1回だけ生成（全レイアウトで同じ背景を使用）
        phase8_config = self.phase_config.copy()
        if prompt_template:
            phase8_config["prompt_template"] = prompt_template
            phase8_config["template_subject"] = self.subject
        if style_config:
            phase8_config["thumbnail_style"] = style_config
        phase8_config["use_stable_diffusion"] = True
        phase8_config["stable_diffusion"] = {
            "width": 1344,
            "height": 768,
            "api_key_env": "STABILITY_API_KEY"
        }
        phase8_config["output"] = {
            "resolution": [1280, 720]
        }

        generator = create_intellectual_curiosity_generator(
            config=phase8_config,
            logger=self.logger
        )

        # 背景画像を1回だけ生成（一時ディレクトリに保存）
        temp_dir = self.phase_dir / "temp_background"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # SDで背景画像を生成（1344x768）
        # generator.generate_thumbnailsは内部でリサイズするので、
        # 直接SD生成を呼び出す必要がある
        from src.generators.image_generator import ImageGenerator
        import os
        
        sd_config = phase8_config.get("stable_diffusion", {})
        api_key = os.getenv(sd_config.get("api_key_env", "STABILITY_API_KEY"))
        claude_key = os.getenv("CLAUDE_API_KEY")
        
        # SDスタイルを設定から取得（デフォルト: photorealistic）
        # 有効な値: photorealistic, oil_painting, ukiyo-e, watercolor, documentary
        sd_style = sd_config.get("style", "photorealistic")
        # "dramatic"などの無効な値の場合はphotorealisticにフォールバック
        valid_styles = ["photorealistic", "oil_painting", "ukiyo-e", "watercolor", "documentary"]
        if sd_style not in valid_styles:
            self.logger.warning(
                f"Invalid SD style '{sd_style}' in config, using 'photorealistic'. "
                f"Valid styles: {', '.join(valid_styles)}"
            )
            sd_style = "photorealistic"
        
        self.logger.info(f"Using SD style: {sd_style}")
        
        sd_generator = ImageGenerator(
            api_key=api_key,
            service="stable-diffusion",
            claude_api_key=claude_key,
            output_dir=temp_dir,
            cache_dir=Path("data/cache/sd_thumbnails"),
            logger=self.logger
        )
        
        # SDで1344x768の画像を生成（リサイズ前）
        collected_image = sd_generator.generate_image(
            keyword=self.subject,
            atmosphere="dramatic",
            section_context=self._extract_key_scenes_for_thumbnail(script_data),
            image_type="portrait",
            style=sd_style,
            width=1344,
            height=768,
            is_first_image=True
        )
        
        # リサイズ前の画像（1344x768）を読み込み
        raw_background_path = Path(collected_image.file_path)
        raw_bg_image = Image.open(raw_background_path)
        self.logger.info(f"Raw background image generated: {raw_bg_image.size}")
        
        # 出力ディレクトリを作成
        thumbnail_dir = self.phase_dir / "thumbnails"
        thumbnail_dir.mkdir(parents=True, exist_ok=True)
        
        # temp_backgroundディレクトリを作成（リサイズ後のテキスト入れる前の画像用）
        temp_background_dir = self.phase_dir / "temp_background"
        temp_background_dir.mkdir(parents=True, exist_ok=True)
        
        # リサイズ後の画像（1280x720）を作成
        bg_image = raw_bg_image.resize((1280, 720), Image.Resampling.LANCZOS)
        self.logger.info(f"Background image resized to: {bg_image.size}")
        
        # リサイズ後のテキスト入れる前の画像をtemp_backgroundに保存
        resized_background_save_path = temp_background_dir / f"{self.subject}_background_resized.jpg"
        bg_image.convert('RGB').save(resized_background_save_path, "JPEG", quality=95)
        self.logger.info(f"✓ Saved resized background image (before text): {resized_background_save_path.name}")
        
        # 台本からテキストを取得
        thumbnail_data = script_data.get("thumbnail", {})
        upper_text = thumbnail_data.get("upper_text", self.subject)
        lower_text = thumbnail_data.get("lower_text", "")
        
        # 一括実行時と単発実行時で動作を分岐
        if self.is_batch_mode:
            # 一括実行時: all_variationsがTrueの場合は全レイアウトでバリエーション生成
            if self.all_variations:
                return self._generate_all_layout_variations(
                    bg_image, upper_text, lower_text, all_layouts, timestamp, thumbnail_dir, variations_dir
                )
            else:
                # 指定レイアウトで1枚のみ生成、variationsは生成しない
                return self._generate_single_layout_thumbnail(
                    bg_image, upper_text, lower_text, all_layouts, timestamp, thumbnail_dir
                )
        else:
            # 単発実行時
            if self.all_variations:
                # --all-variations指定時: 全レイアウトでバリエーション生成
                return self._generate_all_layout_variations(
                    bg_image, upper_text, lower_text, all_layouts, timestamp, thumbnail_dir, variations_dir
                )
            elif not self.text_layout:
                # テキストなしでリサイズ後の画像を保存
                resized_save_path = thumbnail_dir / f"{self.subject}_thumbnail_resized.jpg"
                bg_image.convert('RGB').save(resized_save_path, "JPEG", quality=95)
                self.logger.info(f"✓ Saved resized thumbnail (no text): {resized_save_path.name}")
                
                result = {
                    "subject": self.subject,
                    "generated_at": timestamp,
                    "method": "intellectual-curiosity-resized-only",
                    "thumbnails": [{
                        "pattern_index": 1,
                        "file_path": str(resized_save_path),
                        "file_name": resized_save_path.name,
                        "layout": None,
                        "style": "bright-portrait"
                    }],
                    "total_count": 1
                }
                self._save_metadata(result)
                return result
            else:
                # text_layout指定時: 指定レイアウトのみ生成（1枚のみ）
                return self._generate_single_layout_thumbnail(
                    bg_image, upper_text, lower_text, all_layouts, timestamp, thumbnail_dir
                )
    
    def _generate_single_layout_thumbnail(
        self,
        bg_image: Image.Image,
        upper_text: str,
        lower_text: str,
        all_layouts: List[Dict[str, Any]],
        timestamp: str,
        thumbnail_dir: Path
    ) -> Dict[str, Any]:
        """
        一括実行時: 指定レイアウトで1枚のみ生成
        
        Args:
            bg_image: 背景画像（リサイズ済み）
            upper_text: 上部テキスト
            lower_text: 下部テキスト
            all_layouts: 全レイアウト設定
            timestamp: タイムスタンプ
            thumbnail_dir: サムネイル保存ディレクトリ
            
        Returns:
            生成結果
        """
        # 指定レイアウトを検索
        target_layout = None
        if self.text_layout:
            for layout in all_layouts:
                if layout.get("id") == self.text_layout:
                    target_layout = layout
                    break
        
        if not target_layout:
            # レイアウトが見つからない場合はtwo_line_red_whiteを使用
            self.logger.warning(f"Layout '{self.text_layout}' not found, using 'two_line_red_white'")
            for layout in all_layouts:
                if layout.get("id") == "two_line_red_white":
                    target_layout = layout
                    break
        
        if not target_layout:
            raise PhaseExecutionError(
                self.get_phase_number(),
                f"Layout '{self.text_layout}' not found and default 'two_line_red_white' also not found"
            )
        
        # 指定レイアウトでサムネイルを生成
        layout_id = target_layout.get("id")
        output_path = thumbnail_dir / f"{self.subject}_thumbnail.jpg"
        
        try:
            canvas = bg_image.copy()
            final_image = self._apply_text_layout(
                canvas,
                target_layout,
                upper_text,
                lower_text
            )
            final_image.convert('RGB').save(output_path, "JPEG", quality=95)
            
            self.logger.info(f"✓ Generated thumbnail with layout {layout_id} -> {output_path.name}")
            
        except Exception as e:
            raise PhaseExecutionError(
                self.get_phase_number(),
                f"Failed to generate thumbnail with layout {layout_id}: {e}"
            ) from e
        
        result = {
            "subject": self.subject,
            "generated_at": timestamp,
            "method": "intellectual-curiosity-single-layout",
            "thumbnails": [{
                "pattern_index": 1,
                "file_path": str(output_path),
                "file_name": output_path.name,
                "layout": layout_id,
                "style": "bright-portrait"
            }],
            "total_count": 1
        }
        
        self._save_metadata(result)
        return result
    
    def _generate_all_layout_variations(
        self,
        bg_image: Image.Image,
        upper_text: str,
        lower_text: str,
        all_layouts: List[Dict[str, Any]],
        timestamp: str,
        thumbnail_dir: Path,
        variations_dir: Path
    ) -> Dict[str, Any]:
        """
        単発実行時（text_layout指定）: 全レイアウトでバリエーション生成
        
        Args:
            bg_image: 背景画像（リサイズ済み）
            upper_text: 上部テキスト
            lower_text: 下部テキスト
            all_layouts: 全レイアウト設定
            timestamp: タイムスタンプ
            thumbnail_dir: サムネイル保存ディレクトリ
            variations_dir: バリエーション保存ディレクトリ
            
        Returns:
            生成結果
        """
        # 各レイアウトパターンでサムネイルを生成
        all_generated_thumbnails = []
        
        for layout in all_layouts:
            layout_id = layout.get("id")
            layout_description = layout.get("description", layout_id)
            
            self.logger.info(f"Generating thumbnail with layout: {layout_id} ({layout_description})")
            
            # このレイアウトでサムネイルを生成
            output_filename = f"{self.subject}_thumbnail_{layout_id}_{timestamp}.jpg"
            output_path = variations_dir / output_filename
            
            try:
                # 背景画像をコピー
                canvas = bg_image.copy()
                
                # レイアウトに応じてテキストを描画
                final_image = self._apply_text_layout(
                    canvas,
                    layout,
                    upper_text,
                    lower_text
                )
                
                # 保存
                final_image.convert('RGB').save(output_path, "JPEG", quality=95)
                
                all_generated_thumbnails.append({
                    "layout_id": layout_id,
                    "layout_description": layout_description,
                    "file_path": str(output_path),
                    "file_name": output_filename
                })
                
                self.logger.info(
                    f"✓ Generated thumbnail with layout {layout_id} -> {output_filename}"
                )
                
            except Exception as e:
                self.logger.error(f"Failed to generate thumbnail with layout {layout_id}: {e}", exc_info=True)
                continue

        if not all_generated_thumbnails:
            raise PhaseExecutionError(
                self.get_phase_number(),
                "Failed to generate any thumbnails with any layout"
            )

        # 1枚をランダムで選んで正式なサムネイルとして保存
        selected_thumbnail = random.choice(all_generated_thumbnails)
        selected_source = Path(selected_thumbnail["file_path"])
        selected_dest = thumbnail_dir / f"{self.subject}_thumbnail.jpg"
        
        shutil.copy2(selected_source, selected_dest)
        self.logger.info(
            f"✓ Selected random thumbnail: {selected_thumbnail['layout_id']} "
            f"-> {selected_dest.name}"
        )

        # 結果を作成
        generated_thumbnails = [{
            "pattern_index": 1,
            "file_path": str(selected_dest),
            "file_name": selected_dest.name,
            "layout": selected_thumbnail["layout_id"],
            "style": "bright-portrait",
            "selected_from": selected_thumbnail["layout_id"]
        }]

        result = {
            "subject": self.subject,
            "generated_at": timestamp,
            "method": "intellectual-curiosity-variations",
            "thumbnails": generated_thumbnails,
            "total_count": len(generated_thumbnails),
            "variations": {
                "total_variations": len(all_generated_thumbnails),
                "variations_dir": str(variations_dir),
                "all_layouts": all_generated_thumbnails,
                "selected_layout": selected_thumbnail["layout_id"]
            }
        }

        self._save_metadata(result)

        self.logger.info(
            f"✓ Generated {len(all_generated_thumbnails)} thumbnail variations, "
            f"selected 1 as official thumbnail"
        )
        self.logger.info(
            f"📁 All variations saved to: {variations_dir}"
        )
        self.logger.info(
            f"📁 Official thumbnail saved to: {thumbnail_dir}"
        )
        self.logger.info(
            f"   You can view all {len(all_generated_thumbnails)} variations in the variations/ directory"
        )

        return result
    
    def _extract_key_scenes_for_thumbnail(self, context: Optional[Dict[str, Any]]) -> str:
        """
        台本から重要なシーン・状況を抽出（サムネイル用）
        
        Args:
            context: 台本データ
            
        Returns:
            重要なシーンの説明文
        """
        if not context or "sections" not in context:
            return "No specific context available. Create a dramatic historical scene."
        
        sections = context.get("sections", [])
        if not sections:
            return "No specific context available. Create a dramatic historical scene."
        
        # 最初の2-3セクションから重要な内容を抽出
        key_content = []
        
        for i, section in enumerate(sections[:3]):  # 最初の3セクション
            title = section.get("title", "")
            content = section.get("content", "")
            
            # 各セクションから最初の150-200文字を抽出
            content_preview = content[:200] if content else ""
            
            if title and content_preview:
                key_content.append(f"{i+1}. {title}: {content_preview}...")
            elif content_preview:
                key_content.append(f"{i+1}. {content_preview}...")
        
        if not key_content:
            return "No specific context available. Create a dramatic historical scene."
        
        # セクション内容を結合
        scenes_text = "\n".join(key_content)
        
        return f"""Based on the script:
{scenes_text}

Focus on the most DRAMATIC and VISUALLY COMPELLING moment from these scenes.
Show the ACTION, CONFLICT, or KEY TURNING POINT."""
    
    def _generate_text_only(self, script_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        text_onlyモード: 既存画像にテキストのみ追加
        
        Args:
            script_data: 台本データ
            
        Returns:
            生成結果
        """
        self.logger.info("📝 Text-only mode: Adding text to existing image")
        
        # 画像パスを取得
        if self.text_only_image:
            image_path = Path(self.text_only_image)
        else:
            # 自動検出: temp_background/{subject}_background_resized.jpg（リサイズ後のテキスト入れる前の画像）
            image_path = self.phase_dir / "temp_background" / f"{self.subject}_background_resized.jpg"
        
        if not image_path.exists():
            raise PhaseExecutionError(
                self.get_phase_number(),
                f"Image not found: {image_path}. Please specify with --text-only-image"
            )
        
        # 画像を読み込み
        bg_image = Image.open(image_path)
        self.logger.info(f"Loaded existing image: {image_path.name} ({bg_image.size})")
        
        # リサイズが必要な場合はリサイズ
        if bg_image.size != (1280, 720):
            bg_image = bg_image.resize((1280, 720), Image.Resampling.LANCZOS)
            self.logger.info(f"Resized image to: {bg_image.size}")
        
        # 台本からテキストを取得
        thumbnail_data = script_data.get("thumbnail", {})
        upper_text = thumbnail_data.get("upper_text", self.subject)
        lower_text = thumbnail_data.get("lower_text", "")
        
        # テキストレイアウトを読み込む
        text_config = self.config.get_variation_config("thumbnail_text")
        all_layouts = text_config.get("text_layouts", [])
        
        # 指定レイアウトを検索（未指定の場合はtwo_line_red_white）
        target_layout_id = self.text_layout if self.text_layout else "two_line_red_white"
        target_layout = None
        
        for layout in all_layouts:
            if layout.get("id") == target_layout_id:
                target_layout = layout
                break
        
        if not target_layout:
            raise PhaseExecutionError(
                self.get_phase_number(),
                f"Layout '{target_layout_id}' not found"
            )
        
        # サムネイルを生成
        thumbnail_dir = self.phase_dir / "thumbnails"
        thumbnail_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = thumbnail_dir / f"{self.subject}_thumbnail_text_only_{timestamp}.jpg"
        
        try:
            canvas = bg_image.copy()
            final_image = self._apply_text_layout(
                canvas,
                target_layout,
                upper_text,
                lower_text
            )
            final_image.convert('RGB').save(output_path, "JPEG", quality=95)
            
            self.logger.info(f"✓ Generated thumbnail with text-only mode: {output_path.name}")
            
        except Exception as e:
            raise PhaseExecutionError(
                self.get_phase_number(),
                f"Failed to generate thumbnail with text-only mode: {e}"
            ) from e
        
        result = {
            "subject": self.subject,
            "generated_at": timestamp,
            "method": "text-only",
            "thumbnails": [{
                "pattern_index": 1,
                "file_path": str(output_path),
                "file_name": output_path.name,
                "layout": target_layout_id,
                "style": "text-only",
                "source_image": str(image_path)
            }],
            "total_count": 1
        }
        
        self._save_metadata(result)
        return result
    
    def _generate_text_only_all_variations(self, script_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        text_only + all_variationsモード: 既存画像に全レイアウトのテキストを当てる
        
        Args:
            script_data: 台本データ
            
        Returns:
            生成結果
        """
        self.logger.info("📝 Text-only + All-variations mode: Adding all text layouts to existing image")
        
        # 画像パスを取得
        if self.text_only_image:
            image_path = Path(self.text_only_image)
        else:
            # 自動検出: temp_background/{subject}_background_resized.jpg
            image_path = self.phase_dir / "temp_background" / f"{self.subject}_background_resized.jpg"
        
        if not image_path.exists():
            raise PhaseExecutionError(
                self.get_phase_number(),
                f"Image not found: {image_path}. Please specify with --text-only-image"
            )
        
        # 画像を読み込み
        bg_image = Image.open(image_path)
        self.logger.info(f"Loaded existing image: {image_path.name} ({bg_image.size})")
        
        # リサイズが必要な場合はリサイズ
        if bg_image.size != (1280, 720):
            bg_image = bg_image.resize((1280, 720), Image.Resampling.LANCZOS)
            self.logger.info(f"Resized image to: {bg_image.size}")
        
        # 台本からテキストを取得
        thumbnail_data = script_data.get("thumbnail", {})
        upper_text = thumbnail_data.get("upper_text", self.subject)
        lower_text = thumbnail_data.get("lower_text", "")
        
        # テキストレイアウトを読み込む
        text_config = self.config.get_variation_config("thumbnail_text")
        all_layouts = text_config.get("text_layouts", [])
        
        # thumbnail_generation.yamlのtext_style_v3設定をマージ
        # 注意: 現在は無効化。全てのテキストスタイルはthumbnail_text.yamlから選ばれる
        # phase_config = self.phase_config
        # text_style_v3 = phase_config.get("text_style_v3", {})
        # if text_style_v3:
        #     self.logger.info("Merging text_style_v3 settings from thumbnail_generation.yaml")
        #     all_layouts = self._merge_text_style_settings(all_layouts, text_style_v3)
        
        # thumbnail_text.yamlの設定をそのまま使用（text_style_v3による上書きを無効化）
        self.logger.info("Using text layouts directly from thumbnail_text.yaml (text_style_v3 merge disabled)")
        
        # バリエーション保存用ディレクトリ
        variations_dir = self.phase_dir / "variations"
        variations_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        all_generated_thumbnails = []
        
        # 全レイアウトでサムネイルを生成
        for layout in all_layouts:
            layout_id = layout.get("id")
            layout_description = layout.get("description", layout_id)
            
            self.logger.info(f"Generating thumbnail with layout: {layout_id} ({layout_description})")
            
            output_filename = f"{self.subject}_thumbnail_{layout_id}_{timestamp}.jpg"
            output_path = variations_dir / output_filename
            
            try:
                canvas = bg_image.copy()
                final_image = self._apply_text_layout(
                    canvas,
                    layout,
                    upper_text,
                    lower_text
                )
                final_image.convert('RGB').save(output_path, "JPEG", quality=95)
                
                all_generated_thumbnails.append({
                    "layout_id": layout_id,
                    "layout_description": layout_description,
                    "file_path": str(output_path),
                    "file_name": output_filename
                })
                
                self.logger.info(f"✓ Generated thumbnail with layout {layout_id} -> {output_filename}")
                
            except Exception as e:
                self.logger.error(f"Failed to generate thumbnail with layout {layout_id}: {e}", exc_info=True)
                continue
        
        if not all_generated_thumbnails:
            raise PhaseExecutionError(
                self.get_phase_number(),
                "Failed to generate any thumbnails with any layout"
            )
        
        # 1枚をランダムで選んで正式なサムネイルとして保存
        thumbnail_dir = self.phase_dir / "thumbnails"
        thumbnail_dir.mkdir(parents=True, exist_ok=True)
        
        selected_thumbnail = random.choice(all_generated_thumbnails)
        selected_source = Path(selected_thumbnail["file_path"])
        selected_dest = thumbnail_dir / f"{self.subject}_thumbnail.jpg"
        
        shutil.copy2(selected_source, selected_dest)
        self.logger.info(
            f"✓ Selected random thumbnail: {selected_thumbnail['layout_id']} "
            f"-> {selected_dest.name}"
        )
        
        result = {
            "subject": self.subject,
            "generated_at": timestamp,
            "method": "text-only-all-variations",
            "thumbnails": [{
                "pattern_index": 1,
                "file_path": str(selected_dest),
                "file_name": selected_dest.name,
                "layout": selected_thumbnail["layout_id"],
                "style": "text-only",
                "source_image": str(image_path)
            }],
            "total_count": 1,
            "variations": {
                "total_variations": len(all_generated_thumbnails),
                "variations_dir": str(variations_dir),
                "all_layouts": all_generated_thumbnails,
                "selected_layout": selected_thumbnail["layout_id"]
            }
        }
        
        self._save_metadata(result)
        
        self.logger.info(
            f"✓ Generated {len(all_generated_thumbnails)} thumbnail variations from existing image, "
            f"selected 1 as official thumbnail"
        )
        self.logger.info(f"📁 All variations saved to: {variations_dir}")
        self.logger.info(f"📁 Official thumbnail saved to: {thumbnail_dir}")
        
        return result
    
    def _apply_text_layout(
        self,
        canvas: Image.Image,
        layout_config: Dict[str, Any],
        upper_text: str,
        lower_text: str
    ) -> Image.Image:
        """
        レイアウト設定に基づいてテキストを描画
        
        Args:
            canvas: 背景画像
            layout_config: レイアウト設定（thumbnail_text.yamlから）
            upper_text: 上部テキスト
            lower_text: 下部テキスト
            
        Returns:
            テキスト描画済みの画像
        """
        draw = ImageDraw.Draw(canvas)
        width, height = canvas.size
        
        # フォントパスを検索
        font_path = self._find_font()
        
        layout_id = layout_config.get("id", "")
        layout_mode = layout_config.get("mode", "horizontal")
        
        if layout_mode == "vertical":
            # 縦書きレイアウト（vertical_left_right）
            right_config = layout_config.get("right", {})
            left_config = layout_config.get("left", {})
            
            # 右側縦書きテキスト（赤文字）
            if right_config and upper_text:
                self._draw_vertical_text(
                    draw, canvas, upper_text, right_config, font_path, "right"
                )
            
            # 左側縦書きテキスト（白文字）
            if left_config and lower_text:
                self._draw_vertical_text(
                    draw, canvas, lower_text, left_config, font_path, "left"
                )
        
        else:
            # 横書きレイアウト（two_line_red_white, two_line_yellow_black, three_zone）
            upper_config = layout_config.get("upper", {})
            middle_config = layout_config.get("middle", {})
            lower_config = layout_config.get("lower", {})
            
            # 上部テキスト
            if upper_config and upper_text:
                self._draw_horizontal_text(
                    draw, canvas, upper_text, upper_config, font_path
                )
            
            # 中央テキスト（three_zoneの場合）
            if middle_config and upper_text:
                self._draw_horizontal_text(
                    draw, canvas, upper_text, middle_config, font_path
                )
            
            # 下部テキスト
            if lower_config and lower_text:
                self._draw_horizontal_text(
                    draw, canvas, lower_text, lower_config, font_path
                )
        
        return canvas
    
    def _find_font(self) -> str:
        """日本語対応のフォントを検索"""
        font_candidates = [
            Path("assets/fonts/GenEiKiwamiGothic-EB.ttf"),
            Path("assets/fonts/NotoSansJP-Bold.ttf"),
            Path("assets/fonts/NotoSansJP-VariableFont_wght.ttf"),
            Path("C:/Windows/Fonts/msgothic.ttc"),
            Path("C:/Windows/Fonts/meiryo.ttc"),
        ]
        
        for font_path in font_candidates:
            if font_path.exists():
                return str(font_path)
        
        return "arial.ttf"  # フォールバック
    
    def _draw_horizontal_text(
        self,
        draw: ImageDraw.Draw,
        canvas: Image.Image,
        text: str,
        config: Dict[str, Any],
        font_path: str
    ):
        """
        横書きテキストを描画
        
        Args:
            draw: ImageDrawオブジェクト
            canvas: キャンバス画像
            text: テキスト
            config: テキスト設定（position, font_size, color等）
            font_path: フォントパス
        """
        position = config.get("position", [640, 360])
        font_size = config.get("font_size", 60)
        color = config.get("color", "#FFFFFF")
        stroke_width = config.get("stroke_width", 0)
        stroke_color = config.get("stroke_color", "#000000")
        shadow = config.get("shadow")  # [offset_x, offset_y, color, opacity]
        
        # フォントを読み込み
        try:
            font = ImageFont.truetype(font_path, font_size)
        except:
            font = ImageFont.load_default()
        
        # テキストサイズを取得
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # 位置を計算（中央揃え）
        x = position[0] - text_width // 2
        y = position[1] - text_height // 2
        
        # 色をRGBタプルに変換
        color_rgb = self._hex_to_rgb(color)
        stroke_rgb = self._hex_to_rgb(stroke_color) if stroke_color else None
        
        # 影を描画
        if shadow:
            shadow_x, shadow_y, shadow_color, shadow_opacity = shadow
            shadow_rgb = self._hex_to_rgb(shadow_color)
            # 影の透明度を考慮した色を作成
            shadow_rgba = (*shadow_rgb, int(255 * shadow_opacity))
            shadow_layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow_layer)
            shadow_draw.text(
                (x + shadow_x, y + shadow_y),
                text,
                font=font,
                fill=shadow_rgba
            )
            canvas.paste(shadow_layer, (0, 0), shadow_layer)
        
        # ストロークを描画
        if stroke_width > 0 and stroke_rgb:
            for dx in range(-stroke_width, stroke_width + 1):
                for dy in range(-stroke_width, stroke_width + 1):
                    if dx*dx + dy*dy <= stroke_width*stroke_width:
                        draw.text(
                            (x + dx, y + dy),
                            text,
                            font=font,
                            fill=stroke_rgb
                        )
        
        # メインテキストを描画
        draw.text(
            (x, y),
            text,
            font=font,
            fill=color_rgb
        )
    
    def _draw_vertical_text(
        self,
        draw: ImageDraw.Draw,
        canvas: Image.Image,
        text: str,
        config: Dict[str, Any],
        font_path: str,
        side: str  # "left" or "right"
    ):
        """
        縦書きテキストを描画
        
        Args:
            draw: ImageDrawオブジェクト
            canvas: キャンバス画像
            text: テキスト
            config: テキスト設定
            font_path: フォントパス
            side: "left" or "right"
        """
        position_x = config.get("position_x", 100 if side == "left" else 1160)
        position_y = config.get("position_y", 100)
        font_size = config.get("font_size", 70)
        color = config.get("color", "#FFFFFF")
        stroke_width = config.get("stroke_width", 12)
        stroke_color = config.get("stroke_color", "#000000")
        char_spacing = config.get("char_spacing", 85)
        column_spacing = config.get("column_spacing", 100)
        shadow = config.get("shadow")
        
        # フォントを読み込み
        try:
            font = ImageFont.truetype(font_path, font_size)
        except:
            font = ImageFont.load_default()
        
        # テキストを列に分割（\nで区切る）
        columns = text.split("\n")
        
        current_x = position_x
        for col_idx, column_text in enumerate(columns):
            current_y = position_y
            
            for char in column_text:
                # 各文字を縦に配置
                char_bbox = draw.textbbox((0, 0), char, font=font)
                char_width = char_bbox[2] - char_bbox[0]
                char_height = char_bbox[3] - char_bbox[1]
                
                # 中央揃え（横方向）
                char_x = current_x - char_width // 2
                
                # 色をRGBタプルに変換
                color_rgb = self._hex_to_rgb(color)
                stroke_rgb = self._hex_to_rgb(stroke_color) if stroke_color else None
                
                # 影を描画
                if shadow:
                    shadow_x, shadow_y, shadow_color, shadow_opacity = shadow
                    shadow_rgb = self._hex_to_rgb(shadow_color)
                    shadow_rgba = (*shadow_rgb, int(255 * shadow_opacity))
                    shadow_layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
                    shadow_draw = ImageDraw.Draw(shadow_layer)
                    shadow_draw.text(
                        (char_x + shadow_x, current_y + shadow_y),
                        char,
                        font=font,
                        fill=shadow_rgba
                    )
                    canvas.paste(shadow_layer, (0, 0), shadow_layer)
                
                # ストロークを描画
                if stroke_width > 0 and stroke_rgb:
                    for dx in range(-stroke_width, stroke_width + 1):
                        for dy in range(-stroke_width, stroke_width + 1):
                            if dx*dx + dy*dy <= stroke_width*stroke_width:
                                draw.text(
                                    (char_x + dx, current_y + dy),
                                    char,
                                    font=font,
                                    fill=stroke_rgb
                                )
                
                # メインテキストを描画
                draw.text(
                    (char_x, current_y),
                    char,
                    font=font,
                    fill=color_rgb
                )
                
                current_y += char_spacing
            
            # 次の列へ
            if side == "right":
                current_x -= column_spacing
            else:
                current_x += column_spacing
    
    def _hex_to_rgb(self, hex_color: str) -> tuple:
        """
        16進数カラーコードをRGBタプルに変換
        
        Args:
            hex_color: #RRGGBB形式の色コード
            
        Returns:
            (R, G, B)タプル
        """
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    
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
