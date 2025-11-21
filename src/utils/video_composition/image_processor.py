"""画像を処理するユーティリティ"""

from pathlib import Path
from typing import List


class ImageProcessor:
    """
    画像の処理を担当
    
    機能:
    - concatファイル作成
    - セクションごとの画像取得
    """
    
    def __init__(self, project_root: Path, logger):
        """
        Args:
            project_root: プロジェクトのルートパス
            logger: ロガー
        """
        self.project_root = project_root
        self.logger = logger
    
    def create_concat_file(
        self,
        images: List[Path],
        total_duration: float,
        output_dir: Path
    ) -> Path:
        """
        画像のconcatファイルを作成
        
        Args:
            images: 画像ファイルのリスト
            total_duration: 合計時間（音声の長さ）
            output_dir: 出力ディレクトリ
        
        Returns:
            concatファイルのパス
        """
        concat_file = output_dir / "image_concat.txt"
        
        # 各画像の表示時間を計算（均等分割）
        duration_per_image = total_duration / len(images)
        
        with open(concat_file, 'w', encoding='utf-8') as f:
            for img in images:
                # パスを絶対パスに変換
                img_path = Path(img)
                if not img_path.is_absolute():
                    img_path = img_path.resolve()
                # Windowsパス対応
                img_path_str = str(img_path).replace('\\', '/')
                f.write(f"file '{img_path_str}'\n")
                f.write(f"duration {duration_per_image}\n")
            
            # 最後のファイルをもう一度（ffmpeg仕様）
            last_img = Path(images[-1])
            if not last_img.is_absolute():
                last_img = last_img.resolve()
            last_img_str = str(last_img).replace('\\', '/')
            f.write(f"file '{last_img_str}'\n")
        
        self.logger.info(f"Image concat file created: {concat_file}")
        return concat_file
    
    def get_images_for_sections(
        self,
        script: dict,
        working_dir: Path
    ) -> List[Path]:
        """
        セクションごとの画像を取得
        
        Args:
            script: 台本データ
            working_dir: 作業ディレクトリ
        
        Returns:
            画像ファイルのリスト
        """
        images_dir = working_dir / "03_images" / "generated"
        
        if not images_dir.exists():
            raise FileNotFoundError(f"Images directory not found: {images_dir}")
        
        # 画像ファイルを取得（セクション順）
        images = sorted(images_dir.glob("section_*.png"))
        
        if not images:
            raise FileNotFoundError(f"No images found in: {images_dir}")
        
        return images

