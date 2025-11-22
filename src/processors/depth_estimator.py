"""
深度マップ推定
Hugging Face Transformersを使用した深度推定処理
"""

import torch
from pathlib import Path
from typing import Optional, Dict, Any
from PIL import Image
import logging

try:
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


class DepthEstimator:
    """
    深度マップ推定クラス
    
    Hugging FaceのTransformersを使用して、
    画像から深度マップ（Depth Map）を生成します。
    """
    
    def __init__(
        self,
        model_name: str = "LiheYoung/depth-anything-small-hf",
        use_gpu: bool = True,
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化
        
        Args:
            model_name: 使用するモデル名
            use_gpu: GPU使用フラグ（利用可能な場合）
            logger: ロガー
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "transformers library is not installed. "
                "Install with: pip install transformers torch"
            )
        
        self.logger = logger or logging.getLogger(__name__)
        
        # デバイス選択
        if use_gpu and torch.cuda.is_available():
            self.device = "cuda"
            self.logger.info(f"Using GPU for depth estimation: {torch.cuda.get_device_name(0)}")
        else:
            self.device = "cpu"
            self.logger.info("Using CPU for depth estimation")
        
        # パイプライン初期化
        try:
            self.pipe = pipeline(
                task="depth-estimation",
                model=model_name,
                device=self.device
            )
            self.model_name = model_name
            self.logger.info(f"Depth estimation model loaded: {model_name}")
        except Exception as e:
            self.logger.error(f"Failed to load depth estimation model: {e}")
            raise
    
    def estimate(self, image_path: Path, output_path: Path, normalize: bool = True) -> Path:
        """
        深度マップを推定して保存
        
        Args:
            image_path: 入力画像パス
            output_path: 出力パス
            normalize: 深度マップを0-255に正規化するか
        
        Returns:
            保存された深度マップのパス
        """
        # 画像を読み込み
        try:
            image = Image.open(image_path).convert('RGB')
        except Exception as e:
            raise ValueError(f"Failed to load image: {image_path}") from e
        
        self.logger.debug(f"Estimating depth for: {image_path.name} (size: {image.size})")
        
        # 深度推定
        try:
            result = self.pipe(image)
            depth = result["depth"]  # PIL Image
            
            # 正規化（0-255のグレースケール）
            if normalize:
                # 深度マップをnumpy配列に変換
                import numpy as np
                depth_array = np.array(depth)
                
                # 最小値を0、最大値を255に正規化
                if depth_array.max() > depth_array.min():
                    depth_normalized = (
                        (depth_array - depth_array.min()) /
                        (depth_array.max() - depth_array.min()) * 255
                    ).astype(np.uint8)
                else:
                    depth_normalized = depth_array.astype(np.uint8)
                
                depth = Image.fromarray(depth_normalized)
            
            # 保存
            output_path.parent.mkdir(parents=True, exist_ok=True)
            depth.save(output_path, 'PNG')
            
            self.logger.debug(f"Depth map saved: {output_path}")
            
            return output_path
            
        except Exception as e:
            self.logger.error(f"Depth estimation failed for {image_path.name}: {e}")
            raise
    
    def is_available(self) -> bool:
        """
        深度推定が利用可能かチェック
        
        Returns:
            利用可能な場合True
        """
        return TRANSFORMERS_AVAILABLE and hasattr(self, 'pipe')

