"""
アスペクト比変換ユーティリティ

横型動画を縦型(9:16)に変換。
元動画のアスペクト比(16:9)は保持したまま、ぼかし背景の上に配置。
"""

import subprocess
import platform
from pathlib import Path
from typing import Optional, Literal
import logging


class AspectRatioConverter:
    """アスペクト比変換クラス"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    def convert_to_vertical(
        self,
        input_path: Path,
        output_path: Path,
        target_width: int = 1080,
        target_height: int = 1920,
        crop_mode: Optional[str] = None,  # 後方互換性のため残す
        mode: Literal["blur_bg", "black_bars", "crop"] = "blur_bg"
    ) -> Path:
        """
        横型を縦型に変換
        
        Args:
            input_path: 入力動画
            output_path: 出力動画
            target_width: 出力幅（デフォルト1080）
            target_height: 出力高さ（デフォルト1920）
            crop_mode: クロップモード（後方互換性のため、非推奨）
            mode: 変換モード
                - "blur_bg": ぼかし背景 + 元動画16:9維持（推奨）
                - "black_bars": 黒帯追加 + 元動画16:9維持
                - "crop": 中央クロップ（非推奨）
            
        Returns:
            変換後の動画パス
            
        【重要】blur_bgとblack_barsでは元動画のアスペクト比(16:9)を保持！
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 後方互換性: crop_modeが指定されている場合はmodeに変換
        if crop_mode:
            self.logger.warning("crop_mode parameter is deprecated, use mode='crop' instead")
            if crop_mode in ["center", "top", "bottom"]:
                mode = "crop"

        # Windowsパス対応
        input_str = str(input_path)
        output_str = str(output_path)
        if platform.system() == 'Windows':
            input_str = input_str.replace('\\', '/')
            output_str = output_str.replace('\\', '/')

        # モード別にfilter_complexを構築
        if mode == "blur_bg":
            # ぼかし背景 + 元動画16:9維持
            # 背景: 9:16に拡大してぼかす
            # 前景: アスペクト比保持（16:9のまま）で幅に合わせてスケール
            filter_complex = (
                f"[0:v]scale={target_width}:{target_height}:force_original_aspect_ratio=increase,"
                f"crop={target_width}:{target_height},"
                f"boxblur=luma_radius=min(h\\,w)/20:luma_power=1:chroma_radius=min(cw\\,ch)/20:chroma_power=1[bg];"
                f"[0:v]scale={target_width}:-1:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
            )
            
            cmd = [
                'ffmpeg', '-y',
                '-i', input_str,
                '-filter_complex', filter_complex,
                '-c:a', 'copy',
                output_str
            ]
            
        elif mode == "black_bars":
            # 黒帯 + 元動画16:9維持
            # 前景: アスペクト比保持で幅に合わせてスケール
            # パディング: 上下に黒帯を追加
            vf = f"scale={target_width}:-1:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"
            
            cmd = [
                'ffmpeg', '-y',
                '-i', input_str,
                '-vf', vf,
                '-c:a', 'copy',
                output_str
            ]
            
        else:  # crop（非推奨）
            # 中央クロップ
            vf = f"scale={target_width}:{target_height}:force_original_aspect_ratio=increase,crop={target_width}:{target_height}"
            
            cmd = [
                'ffmpeg', '-y',
                '-i', input_str,
                '-vf', vf,
                '-c:a', 'copy',
                output_str
            ]

        self.logger.info(f"Converting to vertical ({target_width}x{target_height}, mode={mode})...")
        self.logger.debug(f"Command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=False,
                encoding=None
            )

            self.logger.info(f"✓ Converted: {output_path.name}")
            return output_path

        except subprocess.CalledProcessError as e:
            try:
                stderr_msg = e.stderr.decode('utf-8', errors='ignore') if e.stderr else ''
            except:
                stderr_msg = '<decode failed>'

            self.logger.error(f"ffmpeg conversion failed: {stderr_msg}")
            raise
