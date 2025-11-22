"""
シネマティック画像フィルター
OpenCVとNumPyを使用した高速画像加工処理
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any
from PIL import Image
import logging


class CinematicFilter:
    """
    シネマティック画像フィルター
    
    ジャンルに応じた色調補正、フィルムノイズ、ビネットなどの
    エフェクトを適用します。
    """
    
    def __init__(self, config: Dict[str, Any], logger: Optional[logging.Logger] = None):
        """
        初期化
        
        Args:
            config: フィルター設定（brightness, contrast, saturation等）
            logger: ロガー
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
    
    def process(self, image_path: Path) -> np.ndarray:
        """
        画像にシネマティックフィルターを適用
        
        Args:
            image_path: 入力画像パス
        
        Returns:
            加工後の画像（BGR形式、numpy配列）
        """
        # OpenCVは日本語パスを扱えないため、PILで読み込む
        # PILで読み込み（RGBAまたはRGB）
        pil_img = Image.open(image_path)
        
        # RGBAの場合はRGBに変換
        if pil_img.mode == 'RGBA':
            # アルファチャンネルを除去してRGBに変換
            rgb_img = Image.new('RGB', pil_img.size, (255, 255, 255))
            rgb_img.paste(pil_img, mask=pil_img.split()[3])  # アルファチャンネルをマスクとして使用
            pil_img = rgb_img
        elif pil_img.mode != 'RGB':
            pil_img = pil_img.convert('RGB')
        
        # PIL画像をnumpy配列に変換（RGB形式）
        img_rgb = np.array(pil_img)
        
        # RGB→BGRに変換（OpenCV形式）
        img = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        
        if img is None or img.size == 0:
            raise ValueError(f"Failed to load image: {image_path}")
        
        self.logger.debug(f"Processing image: {image_path.name} (shape: {img.shape})")
        
        # 1. カラーグレーディング（ティール＆オレンジ、S字トーンカーブ含む）
        img = self._apply_color_grade(img)
        
        # 2. コントラスト・明るさ調整（S字トーンカーブ適用）
        img = self._apply_contrast_brightness(img)
        
        # 3. グロー効果（Bloom）
        img = self._apply_bloom(img)
        
        # 4. ビネット（周辺減光）
        img = self._apply_vignette(img)
        
        # 5. フィルムノイズ（高度化版：輝度依存、カラーノイズ、オーバーレイ合成）
        img = self._apply_film_grain(img)
        
        # 値域をクリップ（0-255）
        img = np.clip(img, 0, 255).astype(np.uint8)
        
        return img
    
    def _apply_color_grade(self, img: np.ndarray) -> np.ndarray:
        """
        プロ級カラーグレーディング（ティール＆オレンジ、彩度・色温度調整）
        
        Args:
            img: BGR画像
        
        Returns:
            加工後の画像
        """
        saturation = self.config.get('saturation', 1.0)
        temperature = self.config.get('temperature', 0.0)
        split_tone_enabled = self.config.get('split_tone', True)  # ティール＆オレンジを有効化
        split_tone_strength = self.config.get('split_tone_strength', 0.3)  # ティール＆オレンジの強度
        
        img = img.astype(np.float32)
        
        # グレースケール変換（輝度計算用）
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        
        # ティール＆オレンジ（Teal & Orange）効果
        if split_tone_enabled and split_tone_strength > 0.0:
            # シャドウ（暗部）に青緑（Teal）を加算
            shadow_mask = 1.0 - gray  # 暗い部分ほど1.0に近い
            img[:, :, 0] = img[:, :, 0] + shadow_mask * split_tone_strength * 30  # Blue
            img[:, :, 1] = img[:, :, 1] + shadow_mask * split_tone_strength * 15  # Green
            
            # ハイライト（明部）にオレンジを加算
            highlight_mask = gray  # 明るい部分ほど1.0に近い
            img[:, :, 2] = img[:, :, 2] + highlight_mask * split_tone_strength * 30  # Red
            img[:, :, 1] = img[:, :, 1] + highlight_mask * split_tone_strength * 10  # Green（オレンジのため）
        
        # 色温度調整（ティール＆オレンジと組み合わせて使用）
        if abs(temperature) > 0.001:
            if temperature > 0:
                # 暖色（赤寄り）
                img[:, :, 2] = img[:, :, 2] + (temperature * 30)  # Rチャンネル増加
                img[:, :, 0] = img[:, :, 0] - (temperature * 15)  # Bチャンネル減少
            else:
                # 寒色（青寄り）
                img[:, :, 0] = img[:, :, 0] + (abs(temperature) * 30)  # Bチャンネル増加
                img[:, :, 2] = img[:, :, 2] - (abs(temperature) * 15)  # Rチャンネル減少
        
        img = np.clip(img, 0, 255).astype(np.uint8)
        
        # 彩度調整（HSV変換）
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = hsv[:, :, 1] * saturation
        hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
        img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        
        return img
    
    def _apply_contrast_brightness(self, img: np.ndarray) -> np.ndarray:
        """
        コントラスト・明るさ調整（S字トーンカーブ適用）
        
        Args:
            img: BGR画像
        
        Returns:
            加工後の画像
        """
        contrast = self.config.get('contrast', 1.0)
        brightness = self.config.get('brightness', 0.0)
        use_s_curve = self.config.get('use_s_curve', True)  # S字カーブを使用するか
        
        img = img.astype(np.float32) / 255.0  # 0.0-1.0に正規化
        
        # 明るさ調整（正規化後の値域で）
        img = img + brightness
        
        # S字トーンカーブ（シグモイド関数ベース）
        if use_s_curve and contrast != 1.0:
            # シグモイド関数でS字カーブを生成
            # contrast > 1.0: より強いS字、contrast < 1.0: より弱いS字
            s_curve_strength = (contrast - 1.0) * 0.3  # -0.3 to 0.3の範囲に調整
            
            # シグモイド関数のパラメータ
            # kが大きいほど急峻なS字
            k = 4.0 + abs(s_curve_strength) * 8.0  # 4.0-6.4の範囲
            
            # 各チャンネルにS字カーブを適用
            for c in range(3):
                channel = img[:, :, c]
                
                # シグモイド関数: 1 / (1 + exp(-k * (x - 0.5)))
                # 0.5を中心にS字変換
                s_curved = 1.0 / (1.0 + np.exp(-k * (channel - 0.5)))
                
                # 0-1の範囲に正規化（シグモイドの出力範囲を0-1にマッピング）
                # シグモイドの最小値と最大値を計算
                sig_min = 1.0 / (1.0 + np.exp(-k * -0.5))  # x=0の時の値
                sig_max = 1.0 / (1.0 + np.exp(-k * 0.5))    # x=1の時の値
                sig_range = sig_max - sig_min
                
                # 正規化
                s_curved = (s_curved - sig_min) / sig_range
                
                # コントラストの強さに応じて線形補間
                if s_curve_strength > 0:
                    # より強いS字
                    img[:, :, c] = channel * (1.0 - abs(s_curve_strength)) + s_curved * abs(s_curve_strength)
                else:
                    # より弱いS字（線形に近づける）
                    img[:, :, c] = channel * (1.0 - abs(s_curve_strength)) + s_curved * abs(s_curve_strength)
        else:
            # 従来の線形コントラスト調整
            img = (img - 0.5) * contrast + 0.5
        
        # 0-1の範囲にクリップしてから0-255に戻す
        img = np.clip(img, 0.0, 1.0) * 255.0
        
        return img.astype(np.uint8)
    
    def _apply_vignette(self, img: np.ndarray) -> np.ndarray:
        """
        ビネット効果（周辺減光）
        
        Args:
            img: BGR画像
        
        Returns:
            加工後の画像
        """
        strength = self.config.get('vignette_strength', 0.0)
        
        if strength <= 0.0:
            return img
        
        height, width = img.shape[:2]
        
        # 中心からの距離マップを生成
        center_x, center_y = width / 2, height / 2
        y, x = np.ogrid[:height, :width]
        
        # 最大距離（対角線の半分）
        max_dist = np.sqrt(center_x ** 2 + center_y ** 2)
        
        # 距離に基づく減光マスク（0.0-1.0）
        dist = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
        mask = 1.0 - (dist / max_dist) * strength
        mask = np.clip(mask, 0.0, 1.0)
        
        # 3チャンネルに拡張
        mask = np.stack([mask, mask, mask], axis=2)
        
        # マスクを適用
        img = img.astype(np.float32)
        img = img * mask
        img = np.clip(img, 0, 255)
        
        return img.astype(np.uint8)
    
    def _apply_film_grain(self, img: np.ndarray) -> np.ndarray:
        """
        高度化フィルムグレイン（輝度依存ノイズ、カラーノイズ、オーバーレイ合成）
        
        Args:
            img: BGR画像
        
        Returns:
            加工後の画像
        """
        intensity = self.config.get('grain_intensity', 0.0)
        
        if intensity <= 0.0:
            return img
        
        img = img.astype(np.float32)
        
        # グレースケール変換（輝度計算用）
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        
        # 1. 輝度依存マスク（中間調に最も強くノイズを乗せる）
        # 中間調（0.5付近）が1.0になる放物線
        midtone_mask = 1.0 - 4.0 * (gray - 0.5) ** 2
        midtone_mask = np.clip(midtone_mask, 0.0, 1.0)
        
        # 2. モノクロノイズ（Luminance Noise）
        luminance_noise = np.random.normal(
            0,
            intensity * 255 * 0.4,  # 標準偏差
            gray.shape
        ).astype(np.float32)
        
        # 輝度依存マスクを適用
        luminance_noise = luminance_noise * midtone_mask
        
        # 3. カラーノイズ（Chrominance Noise）- わずかに色付きのノイズ
        chrominance_strength = intensity * 0.3  # カラーノイズは弱め
        chrominance_noise = np.random.normal(
            0,
            chrominance_strength * 255 * 0.3,
            img.shape
        ).astype(np.float32)
        
        # カラーノイズにも輝度依存マスクを適用（弱め）
        chrominance_mask = midtone_mask * 0.7
        chrominance_noise = chrominance_noise * chrominance_mask[:, :, np.newaxis]
        
        # 4. オーバーレイ合成（Soft Light風のブレンド）
        # Soft Light: base < 0.5: 2*base*blend, base >= 0.5: 1 - 2*(1-base)*(1-blend)
        img_normalized = img / 255.0
        
        # モノクロノイズを0-1の範囲に正規化
        luminance_noise_normalized = (luminance_noise + 127.5) / 255.0
        luminance_noise_normalized = np.clip(luminance_noise_normalized, 0.0, 1.0)
        
        # Soft Lightブレンドを各チャンネルに適用
        for c in range(3):
            base = img_normalized[:, :, c]
            blend = luminance_noise_normalized
            
            # Soft Light計算
            soft_light = np.where(
                base < 0.5,
                2.0 * base * blend,
                1.0 - 2.0 * (1.0 - base) * (1.0 - blend)
            )
            
            img_normalized[:, :, c] = soft_light
        
        # カラーノイズを加算（より控えめに）
        img_normalized = img_normalized + (chrominance_noise / 255.0)
        
        # 0-1の範囲にクリップしてから0-255に戻す
        img = np.clip(img_normalized, 0.0, 1.0) * 255.0
        
        return img.astype(np.uint8)
    
    def _apply_bloom(self, img: np.ndarray) -> np.ndarray:
        """
        グロー効果（Bloom）- ハイライト部分を抽出してぼかし、加算合成
        
        Args:
            img: BGR画像
        
        Returns:
            加工後の画像
        """
        bloom_strength = self.config.get('bloom_strength', 0.0)
        
        if bloom_strength <= 0.0:
            return img
        
        img = img.astype(np.float32)
        
        # 1. ハイライト部分を抽出（閾値以上の明るい部分）
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        threshold = 200.0  # ハイライトの閾値
        
        # ハイライトマスク（0.0-1.0）
        highlight_mask = np.clip((gray - threshold) / (255.0 - threshold), 0.0, 1.0)
        
        # マスクを3チャンネルに拡張
        highlight_mask_3d = highlight_mask[:, :, np.newaxis]
        
        # ハイライト部分のみを抽出
        highlights = img * highlight_mask_3d
        
        # 2. ガウシアンブラーでぼかす（グロー効果）
        blur_kernel_size = 21  # ぼかしの強さ（奇数）
        blur_sigma = 10.0  # ガウシアンブラーの標準偏差
        
        # 各チャンネルをぼかす
        blurred_highlights = np.zeros_like(highlights)
        for c in range(3):
            blurred_highlights[:, :, c] = cv2.GaussianBlur(
                highlights[:, :, c],
                (blur_kernel_size, blur_kernel_size),
                blur_sigma
            )
        
        # 3. 元の画像に加算合成（グロー効果）
        img = img + blurred_highlights * bloom_strength
        
        # 値域をクリップ
        img = np.clip(img, 0, 255)
        
        return img.astype(np.uint8)
    
    def save(self, img: np.ndarray, output_path: Path, quality: int = 95):
        """
        加工後の画像を保存
        
        Args:
            img: 加工後の画像（BGR形式）
            output_path: 出力パス
            quality: JPEG品質（PNGの場合は無視）
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # BGR→RGBに変換（OpenCV形式からPIL形式へ）
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # numpy配列をPIL画像に変換
        pil_img = Image.fromarray(img_rgb)
        
        # PILで保存（日本語パス対応）
        if output_path.suffix.lower() in ['.png']:
            pil_img.save(output_path, 'PNG', optimize=True)
        else:
            # JPEG形式の場合
            pil_img.save(output_path, 'JPEG', quality=quality, optimize=True)
        
        self.logger.debug(f"Saved processed image: {output_path}")

