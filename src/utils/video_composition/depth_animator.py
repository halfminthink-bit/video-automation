"""
2.5Dパララックスアニメーション生成ユーティリティ

深度マップを使用して、静止画に立体的な動きを付与する。
"""

import cv2
import numpy as np
from pathlib import Path
import logging
from typing import Optional


class DepthAnimator:
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    def _imread_safe(self, path: str, flags: int = cv2.IMREAD_COLOR) -> Optional[np.ndarray]:
        """日本語パス対応の画像読み込み"""
        try:
            n = np.fromfile(path, np.uint8)
            img = cv2.imdecode(n, flags)
            return img
        except Exception as e:
            self.logger.error(f"Failed to load image: {e}")
            return None

    def create_animation(
        self,
        image_path: Path,
        depth_path: Path,
        duration: float,
        output_path: Path,
        movement_type: str = "dolly_zoom"
    ) -> bool:
        """
        静止画と深度マップから2.5Dアニメーションを生成 (Dolly Zoom)
        """
        self.logger.info(f"Generating {duration}s 2.5D animation ({movement_type})...")

        # 1. 画像読み込み (日本語パス対応)
        img = self._imread_safe(str(image_path))
        depth = self._imread_safe(str(depth_path), cv2.IMREAD_GRAYSCALE)

        if img is None or depth is None:
            self.logger.error("Failed to load image or depth map")
            return False

        # リサイズ (1920x1080)
        h, w = img.shape[:2]
        if (w, h) != (1920, 1080):
            img = cv2.resize(img, (1920, 1080))
            depth = cv2.resize(depth, (1920, 1080))

        # 深度マップの平滑化 (エッジのジャギー軽減)
        depth = cv2.GaussianBlur(depth, (5, 5), 0)

        # 動画設定
        fps = 30
        total_frames = int(duration * fps)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (1920, 1080))

        # 正規化された深度 (0.0: 奥, 1.0: 手前)
        depth_norm = depth.astype(np.float32) / 255.0
        
        # メッシュグリッド作成
        x = np.arange(1920)
        y = np.arange(1080)
        x_mesh, y_mesh = np.meshgrid(x, y)
        center_x, center_y = 1920 / 2, 1080 / 2

        # フレーム生成ループ
        self.logger.info(f"Generating {total_frames} frames...")
        
        for i in range(total_frames):
            progress = i / total_frames  # 0.0 -> 1.0
            
            # Dolly Zoom: 背景が迫ってくる演出
            # 手前(1.0)は動かず、奥(0.0)が拡大する
            zoom_strength = 0.05  # 5%ズーム
            current_zoom = 1.0 + (progress * zoom_strength)
            
            # 深度に基づくスケールマップ
            # 手前ほどスケール変化を小さく (1.0に近づける)
            scale_map = 1.0 + (current_zoom - 1.0) * (1.0 - depth_norm * 0.5)
            
            # 座標変換 (Warping)
            map_x = (x_mesh - center_x) / scale_map + center_x
            map_y = (y_mesh - center_y) / scale_map + center_y
            
            # リマッピング (ニアレストネイバーではなくリニア補間で)
            warped_frame = cv2.remap(img, map_x.astype(np.float32), map_y.astype(np.float32), cv2.INTER_LINEAR)
            
            # インペインティング（欠損補間）は重すぎるため、
            # わずかな拡大で画面外にはみ出させることで黒枠回避を推奨
            # (今回は簡易的にそのまま出力)
            
            out.write(warped_frame)

        out.release()
        self.logger.info(f"✅ 2.5D animation saved: {output_path}")
        return True
