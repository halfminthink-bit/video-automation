"""
3ゾーンレイアウトマネージャー

画面を3つのゾーンに分割し、テキストと人物画像を配置
"""

from typing import Dict, Tuple, Any
import logging
from PIL import Image, ImageDraw


class ThreeZoneLayoutManager:
    """3ゾーンレイアウト管理クラス"""

    def __init__(
        self,
        canvas_size: Tuple[int, int] = (1280, 720),
        logger: logging.Logger = None
    ):
        """
        初期化

        Args:
            canvas_size: キャンバスサイズ (width, height)
            logger: ロガー
        """
        self.width, self.height = canvas_size
        self.logger = logger or logging.getLogger(__name__)

        # ゾーン定義
        self.zones = self._define_zones()

        self.logger.info(f"ThreeZoneLayoutManager initialized: {canvas_size}")
        self.logger.debug(f"Zones: {self.zones}")

    def _define_zones(self) -> Dict[str, Dict[str, Any]]:
        """
        ゾーンを定義

        Returns:
            ゾーン定義辞書
        """
        return {
            # 上部30%: メインキャッチテキスト
            "main_text": {
                "y_start": 0,
                "y_end": int(self.height * 0.30),
                "height": int(self.height * 0.30),
                "padding_top": 20,
                "padding_bottom": 20,
                "padding_left": 60,
                "padding_right": 60,
                "description": "メインキャッチエリア"
            },
            # 中央40%: 人物画像表示エリア
            "image_area": {
                "y_start": int(self.height * 0.30),
                "y_end": int(self.height * 0.70),
                "height": int(self.height * 0.40),
                "fade_edges": True,  # 端をフェードアウト
                "preserve_brightness": True,  # 明るさを維持
                "description": "人物画像エリア"
            },
            # 下部30%: サブ説明テキスト
            "sub_text": {
                "y_start": int(self.height * 0.70),
                "y_end": self.height,
                "height": int(self.height * 0.30),
                "padding_top": 20,
                "padding_bottom": 20,
                "padding_left": 60,
                "padding_right": 60,
                "with_background_band": True,  # 半透明背景帯
                "description": "サブ説明文エリア"
            }
        }

    def get_main_text_position(
        self,
        text_size: Tuple[int, int]
    ) -> Dict[str, Any]:
        """
        メインテキストの配置位置を計算

        Args:
            text_size: テキストサイズ (width, height)

        Returns:
            配置情報 {"x": ..., "y": ..., "anchor": ...}
        """
        zone = self.zones["main_text"]
        text_width, text_height = text_size

        # 中央配置
        x = self.width // 2
        y = zone["y_start"] + (zone["height"] // 2)

        self.logger.debug(
            f"Main text position: ({x}, {y}), "
            f"size: {text_size}, zone: {zone['y_start']}-{zone['y_end']}"
        )

        return {
            "x": x,
            "y": y,
            "anchor": "mm",  # middle-middle (中央)
            "zone": "main_text"
        }

    def get_sub_text_position(
        self,
        text_size: Tuple[int, int]
    ) -> Dict[str, Any]:
        """
        サブテキストの配置位置を計算

        Args:
            text_size: テキストサイズ (width, height)

        Returns:
            配置情報 {"x": ..., "y": ..., "anchor": ...}
        """
        zone = self.zones["sub_text"]
        text_width, text_height = text_size

        # 中央配置
        x = self.width // 2
        y = zone["y_start"] + (zone["height"] // 2)

        self.logger.debug(
            f"Sub text position: ({x}, {y}), "
            f"size: {text_size}, zone: {zone['y_start']}-{zone['y_end']}"
        )

        return {
            "x": x,
            "y": y,
            "anchor": "mm",  # middle-middle (中央)
            "zone": "sub_text"
        }

    def get_image_area_bounds(self) -> Dict[str, int]:
        """
        画像エリアの境界を取得

        Returns:
            境界情報 {"y_start": ..., "y_end": ..., "height": ...}
        """
        zone = self.zones["image_area"]

        return {
            "y_start": zone["y_start"],
            "y_end": zone["y_end"],
            "height": zone["height"],
            "x_start": 0,
            "x_end": self.width,
            "width": self.width
        }

    def create_zone_gradient_mask(self) -> Image.Image:
        """
        ゾーン用のグラデーションマスクを作成
        上30%と下30%を暗くし、中央40%は明るさを維持

        Returns:
            グラデーションマスク（Lモード）
        """
        self.logger.info("Creating zone gradient mask")

        mask = Image.new("L", (self.width, self.height), 0)
        pixels = mask.load()

        # 上部ゾーン（0-30%）: 暗くする
        main_text_zone = self.zones["main_text"]
        for y in range(main_text_zone["y_start"], main_text_zone["y_end"]):
            # 上から下にかけて徐々に暗くする
            ratio = (y - main_text_zone["y_start"]) / main_text_zone["height"]
            # 最大200の暗さ（上部）から0（境界）へ
            darkness = int(200 * (1 - ratio))

            for x in range(self.width):
                pixels[x, y] = darkness

        # 中央ゾーン（30-70%）: 明るさを維持（マスク値0）
        image_area_zone = self.zones["image_area"]
        for y in range(image_area_zone["y_start"], image_area_zone["y_end"]):
            for x in range(self.width):
                pixels[x, y] = 0

        # 下部ゾーン（70-100%）: 暗くする
        sub_text_zone = self.zones["sub_text"]
        for y in range(sub_text_zone["y_start"], sub_text_zone["y_end"]):
            # 上から下にかけて徐々に暗くする
            ratio = (y - sub_text_zone["y_start"]) / sub_text_zone["height"]
            # 0（境界）から最大200の暗さ（下部）へ
            darkness = int(200 * ratio)

            for x in range(self.width):
                pixels[x, y] = darkness

        self.logger.info("Zone gradient mask created")

        return mask

    def visualize_zones(self, output_path: str = None) -> Image.Image:
        """
        ゾーンを可視化（デバッグ用）

        Args:
            output_path: 保存先パス（Noneの場合は保存しない）

        Returns:
            可視化画像
        """
        img = Image.new("RGB", (self.width, self.height), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        # 各ゾーンを色分け
        colors = {
            "main_text": (255, 200, 200),    # 薄い赤
            "image_area": (200, 255, 200),   # 薄い緑
            "sub_text": (200, 200, 255)      # 薄い青
        }

        for zone_name, zone_data in self.zones.items():
            color = colors.get(zone_name, (128, 128, 128))
            draw.rectangle(
                [0, zone_data["y_start"], self.width, zone_data["y_end"]],
                fill=color,
                outline=(0, 0, 0),
                width=2
            )

            # ゾーン名を描画
            text = f"{zone_name}\n{zone_data['description']}"
            text_y = zone_data["y_start"] + (zone_data["height"] // 2)
            draw.text(
                (self.width // 2, text_y),
                text,
                fill=(0, 0, 0),
                anchor="mm"
            )

        if output_path:
            img.save(output_path)
            self.logger.info(f"Zone visualization saved: {output_path}")

        return img
