"""
サムネイル生成ジェネレーター

Phase 3の画像からYouTubeサムネイルを生成する
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import logging


class ThumbnailGenerator:
    """YouTubeサムネイル生成クラス"""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Args:
            config: thumbnail_generation.yamlの設定
            logger: ロガー
        """
        self.config = config
        self.logger = logger
        
        # 設定を読み込み
        self.output_config = config.get("output", {})
        self.resolution = tuple(self.output_config.get("resolution", [1280, 720]))
        self.format = self.output_config.get("format", "png")
        self.quality = self.output_config.get("quality", 95)
        self.num_patterns = self.output_config.get("patterns", 5)
        
        self.image_selection_config = config.get("image_selection", {})
        self.text_config = config.get("text_generation", {})
        self.font_config = config.get("fonts", {})
        self.text_style_config = config.get("text_style", {})
        self.layout_config = config.get("layout", {})
        self.image_processing_config = config.get("image_processing", {})
        
        self.logger.info(f"ThumbnailGenerator initialized: {self.resolution[0]}x{self.resolution[1]}, {self.num_patterns} patterns")
    
    def select_best_image(self, images: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Phase 3の画像から最適な1枚を選択
        
        Args:
            images: classified.jsonのimagesリスト
            
        Returns:
            選択された画像の情報、またはNone
        """
        if not images:
            self.logger.warning("No images available for thumbnail")
            return None
        
        self.logger.info(f"Selecting best image from {len(images)} candidates...")
        
        # 基準に基づいてスコアリング
        scored_images = []
        
        for img in images:
            score = 0
            file_path = Path(img.get("file_path", ""))
            
            if not file_path.exists():
                continue
            
            # 画像を開いて分析
            try:
                with Image.open(file_path) as pil_img:
                    width, height = pil_img.size
                    
                    # 解像度スコア
                    if width >= 1024 and height >= 768:
                        score += 2
                    elif width >= 800 and height >= 600:
                        score += 1
                    
                    # アスペクト比スコア（16:9に近いほど高得点）
                    aspect_ratio = width / height
                    target_ratio = 16 / 9
                    ratio_diff = abs(aspect_ratio - target_ratio)
                    if ratio_diff < 0.1:
                        score += 2
                    elif ratio_diff < 0.3:
                        score += 1
                    
                    # 明度スコア（極端に暗い/明るい画像を避ける）
                    if pil_img.mode in ('RGB', 'RGBA'):
                        # 簡易的な明度チェック
                        grayscale = pil_img.convert('L')
                        histogram = grayscale.histogram()
                        # 中間の明度が多いほど良い
                        mid_brightness = sum(histogram[64:192])
                        total_pixels = sum(histogram)
                        if total_pixels > 0:
                            mid_ratio = mid_brightness / total_pixels
                            if mid_ratio > 0.5:
                                score += 2
                            elif mid_ratio > 0.3:
                                score += 1
                
                # セクションIDスコア（最初のセクションを優先）
                section_id = img.get("section_id", 999)
                if section_id == 1:
                    score += 3  # 最初のセクションは高得点
                elif section_id == 2:
                    score += 1
                
                # 分類スコア（daily_life, portrait, dramatic_sceneを優先）
                classification = img.get("classification", "")
                if classification in ["portrait", "daily_life", "dramatic_scene"]:
                    score += 2
                elif classification in ["historical_scene", "symbolic_object"]:
                    score += 1
                
                scored_images.append({
                    "image": img,
                    "score": score,
                    "file_path": file_path
                })
                
                self.logger.debug(f"Image {file_path.name}: score={score}")
                
            except Exception as e:
                self.logger.warning(f"Failed to analyze image {file_path}: {e}")
                continue
        
        if not scored_images:
            self.logger.warning("No valid images found")
            return None
        
        # スコアでソート
        scored_images.sort(key=lambda x: x["score"], reverse=True)
        
        best_image = scored_images[0]["image"]
        best_score = scored_images[0]["score"]
        
        self.logger.info(f"Selected best image: {Path(best_image['file_path']).name} (score: {best_score})")
        
        return best_image
    
    def generate_titles(self, subject: str, script_data: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        キャッチーなタイトルを生成
        
        Args:
            subject: 人物名
            script_data: 台本データ（オプション）
            
        Returns:
            タイトルのリスト
        """
        titles = []
        
        # LLMを使用する場合（今回は簡易実装）
        if self.text_config.get("llm_enabled", False) and script_data:
            # TODO: LLMを使用してタイトルを生成
            # 今回は簡易的なパターンベースで生成
            pass
        
        # パターンベースのタイトル生成
        patterns = self.text_config.get("title_patterns", [])
        
        for pattern in patterns[:self.num_patterns]:
            if pattern == "short_impactful":
                titles.append(f"{subject}の真実")
            elif pattern == "question_form":
                titles.append(f"{subject}とは何者か？")
            elif pattern == "dramatic_statement":
                titles.append(f"歴史を変えた{subject}")
            elif pattern == "number_fact":
                titles.append(f"{subject}の物語")
            elif pattern == "contrast_phrase":
                titles.append(f"知られざる{subject}")
        
        # 不足分をフォールバックで補完
        fallback_titles = self.text_config.get("fallback_titles", [])
        while len(titles) < self.num_patterns and fallback_titles:
            title_template = fallback_titles[len(titles) % len(fallback_titles)]
            titles.append(title_template.format(subject=subject))
        
        self.logger.info(f"Generated {len(titles)} title variations")
        return titles
    
    def create_thumbnail(
        self,
        base_image_path: Path,
        title: str,
        output_path: Path,
        pattern_index: int = 0
    ) -> bool:
        """
        サムネイルを生成
        
        Args:
            base_image_path: ベース画像のパス
            title: タイトルテキスト
            output_path: 出力パス
            pattern_index: パターンインデックス（0-4）
            
        Returns:
            成功したらTrue
        """
        try:
            self.logger.info(f"Creating thumbnail: {output_path.name}")
            
            # ベース画像を読み込み
            with Image.open(base_image_path) as base_img:
                # RGB変換
                if base_img.mode != 'RGB':
                    base_img = base_img.convert('RGB')
                
                # リサイズ
                base_img = base_img.resize(self.resolution, Image.Resampling.LANCZOS)
                
                # 画像処理を適用
                processed_img = self._apply_image_processing(base_img, pattern_index)
                
                # テキストを追加
                final_img = self._add_text_to_image(processed_img, title, pattern_index)
                
                # 保存
                final_img.save(output_path, format=self.format.upper(), quality=self.quality)
                
                self.logger.info(f"✓ Thumbnail saved: {output_path}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to create thumbnail: {e}", exc_info=True)
            return False
    
    def _apply_image_processing(self, img: Image.Image, pattern_index: int) -> Image.Image:
        """
        画像処理を適用（明度・コントラスト・彩度調整）
        
        Args:
            img: 元画像
            pattern_index: パターンインデックス
            
        Returns:
            処理後の画像
        """
        # 明度調整
        if self.image_processing_config.get("brightness_adjustment", True):
            brightness_range = self.image_processing_config.get("brightness_range", [0.9, 1.1])
            brightness_factor = brightness_range[0] + (brightness_range[1] - brightness_range[0]) * (pattern_index / max(1, self.num_patterns - 1))
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(brightness_factor)
        
        # コントラスト調整
        if self.image_processing_config.get("contrast_adjustment", True):
            contrast_range = self.image_processing_config.get("contrast_range", [1.0, 1.3])
            contrast_factor = contrast_range[0] + (contrast_range[1] - contrast_range[0]) * (pattern_index / max(1, self.num_patterns - 1))
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(contrast_factor)
        
        # 彩度調整
        if self.image_processing_config.get("saturation_adjustment", True):
            saturation_range = self.image_processing_config.get("saturation_range", [1.0, 1.2])
            saturation_factor = saturation_range[0] + (saturation_range[1] - saturation_range[0]) * (pattern_index / max(1, self.num_patterns - 1))
            enhancer = ImageEnhance.Color(img)
            img = enhancer.enhance(saturation_factor)
        
        # ビネット効果
        if self.image_processing_config.get("vignette", {}).get("enabled", False):
            img = self._apply_vignette(img)
        
        return img
    
    def _apply_vignette(self, img: Image.Image) -> Image.Image:
        """
        ビネット効果を適用（周辺を暗くする）
        
        Args:
            img: 元画像
            
        Returns:
            ビネット効果適用後の画像
        """
        strength = self.image_processing_config.get("vignette", {}).get("strength", 0.3)
        
        # ビネットマスクを作成
        width, height = img.size
        mask = Image.new('L', (width, height), 255)
        draw = ImageDraw.Draw(mask)
        
        # 楕円形のグラデーションを作成
        for i in range(100):
            alpha = int(255 * (1 - strength * (i / 100)))
            x0 = int(width * i / 200)
            y0 = int(height * i / 200)
            x1 = width - x0
            y1 = height - y0
            draw.ellipse([x0, y0, x1, y1], fill=alpha)
        
        # マスクをぼかす
        mask = mask.filter(ImageFilter.GaussianBlur(radius=width // 10))
        
        # 黒い画像を作成
        black = Image.new('RGB', (width, height), (0, 0, 0))
        
        # ビネットを合成
        result = Image.composite(img, black, mask)
        
        return result
    
    def _load_japanese_font(self, size: int) -> ImageFont.FreeTypeFont:
        """
        YouTubeサムネイルに最適な日本語フォントを読み込む
        
        優先順位:
        1. assets/fonts/内のフォント（源暎きわみゴ、キルゴUなど）
        2. システムフォント（Noto Sans CJK JP Bold）
        3. デフォルトフォント
        
        Args:
            size: フォントサイズ
            
        Returns:
            フォントオブジェクト
        """
        # YouTubeサムネイル向けフォントの優先順位リスト
        font_candidates = [
            # assets/fonts/内のフォント
            "assets/fonts/GenEiKiwamiGothic-EB.ttf",  # 源暎きわみゴ
            "assets/fonts/GN-KillGothic-U-KanaNB.ttf",  # キルゴU
            "assets/fonts/Corporate-Logo-ver3.otf",  # コーポレートロゴ
            "assets/fonts/DelaGothicOne-Regular.ttf",  # デラゴシック
            "assets/fonts/ReiGothic-Regular.ttf",  # 零ゴシック
            
            # システムフォント（太字を優先）
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansJP-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansJP-Bold.otf",
            
            # 通常ウェイトのフォント
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansJP-Regular.ttf",
        ]
        
        # プロジェクトルートからの相対パスを解決
        project_root = Path(__file__).parent.parent.parent
        
        for font_path_str in font_candidates:
            font_path = Path(font_path_str)
            
            # 相対パスの場合はプロジェクトルートから解決
            if not font_path.is_absolute():
                font_path = project_root / font_path
            
            if font_path.exists():
                try:
                    font = ImageFont.truetype(str(font_path), size)
                    self.logger.info(f"✓ Loaded font: {font_path.name}")
                    return font
                except Exception as e:
                    self.logger.debug(f"Failed to load font {font_path}: {e}")
                    continue
        
        # すべて失敗した場合はデフォルトフォント
        self.logger.warning("⚠ Japanese font not found, using default font. Consider installing Noto Sans CJK JP or downloading recommended fonts.")
        return ImageFont.load_default()
    
    def _add_text_to_image(self, img: Image.Image, title: str, pattern_index: int) -> Image.Image:
        """
        画像にテキストを追加
        
        Args:
            img: ベース画像
            title: タイトルテキスト
            pattern_index: パターンインデックス
            
        Returns:
            テキスト追加後の画像
        """
        # 描画オブジェクトを作成
        draw = ImageDraw.Draw(img)
        
        # フォント設定を取得
        main_font_config = self.font_config.get("main_title", {})
        font_size = main_font_config.get("size_base", 72)
        
        # フォントを読み込み（YouTubeサムネイル向けフォントを優先）
        font = self._load_japanese_font(font_size)
        
        # テキスト位置を取得
        text_positions = self.layout_config.get("text_positions", ["bottom_center"])
        position_type = text_positions[pattern_index % len(text_positions)]
        
        # テキストサイズを取得
        bbox = draw.textbbox((0, 0), title, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # 位置を計算
        width, height = img.size
        margins = self.layout_config.get("margins", {})
        
        if position_type == "top_center":
            x = (width - text_width) // 2
            y = margins.get("top", 40)
        elif position_type == "center_center":
            x = (width - text_width) // 2
            y = (height - text_height) // 2
        elif position_type == "bottom_center":
            x = (width - text_width) // 2
            y = height - text_height - margins.get("bottom", 40)
        elif position_type == "top_left":
            x = margins.get("left", 60)
            y = margins.get("top", 40)
        elif position_type == "bottom_right":
            x = width - text_width - margins.get("right", 60)
            y = height - text_height - margins.get("bottom", 40)
        else:
            x = (width - text_width) // 2
            y = height - text_height - margins.get("bottom", 40)
        
        # テキスト色を取得
        colors = self.text_style_config.get("colors", ["#FFFFFF"])
        text_color = colors[pattern_index % len(colors)]
        
        # 縁取り設定
        stroke_config = self.text_style_config.get("stroke", {})
        stroke_width = stroke_config.get("width", 3) if stroke_config.get("enabled", True) else 0
        stroke_color = stroke_config.get("color", "#000000")
        
        # 影を描画
        shadow_config = self.text_style_config.get("shadow", {})
        if shadow_config.get("enabled", True):
            shadow_offset_x = shadow_config.get("offset_x", 2)
            shadow_offset_y = shadow_config.get("offset_y", 2)
            shadow_color = shadow_config.get("color", "#000000")
            
            draw.text(
                (x + shadow_offset_x, y + shadow_offset_y),
                title,
                font=font,
                fill=shadow_color,
                stroke_width=stroke_width,
                stroke_fill=shadow_color
            )
        
        # テキストを描画
        draw.text(
            (x, y),
            title,
            font=font,
            fill=text_color,
            stroke_width=stroke_width,
            stroke_fill=stroke_color
        )
        
        self.logger.debug(f"Text added: '{title}' at ({x}, {y}), color={text_color}")
        
        return img


def create_thumbnail_generator(config: Dict[str, Any], logger: logging.Logger) -> ThumbnailGenerator:
    """
    ThumbnailGeneratorのファクトリー関数
    
    Args:
        config: 設定辞書
        logger: ロガー
        
    Returns:
        ThumbnailGenerator インスタンス
    """
    return ThumbnailGenerator(config, logger)
