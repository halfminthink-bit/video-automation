"""
サムネイル生成のテスト
"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.generators.pillow_thumbnail_generator import PillowThumbnailGenerator

def test_thumbnail_generation():
    """サムネイル生成のテスト"""
    
    # ジェネレーターを作成
    generator = PillowThumbnailGenerator(width=1280, height=720)
    
    # テスト1: グラデーション背景のみ（中央配置）
    print("テスト1: グラデーション背景 + 中央配置")
    output1 = "/home/ubuntu/test_thumbnail_center.png"
    generator.generate_thumbnail(
        title="イグナーツ・ゼンメルワイス",
        subtitle="医学の父",
        layout="center",
        output_path=output1
    )
    print(f"✓ 生成完了: {output1}")
    
    # テスト2: グラデーション背景（左寄せ）
    print("\nテスト2: グラデーション背景 + 左寄せ")
    output2 = "/home/ubuntu/test_thumbnail_left.png"
    generator.generate_thumbnail(
        title="イグナーツ・ゼンメルワイス",
        subtitle="手洗いの重要性を発見",
        layout="left",
        output_path=output2
    )
    print(f"✓ 生成完了: {output2}")
    
    # テスト3: 背景画像を探す
    print("\nテスト3: 背景画像 + テキストオーバーレイ")
    images_dir = Path("/home/ubuntu/video-automation/data/working/イグナーツゼンメルワイス")
    background_image = None
    
    # Phase 3の画像を探す
    for phase_dir in images_dir.glob("03_*"):
        images = list((phase_dir / "images").glob("*.png"))
        if images:
            background_image = str(images[0])
            print(f"背景画像を発見: {images[0].name}")
            break
    
    if background_image:
        output3 = "/home/ubuntu/test_thumbnail_background.png"
        generator.generate_thumbnail(
            title="イグナーツ・ゼンメルワイス",
            background_image=background_image,
            layout="background",
            output_path=output3
        )
        print(f"✓ 生成完了: {output3}")
    else:
        print("背景画像が見つかりませんでした（スキップ）")
    
    print("\n✅ すべてのテストが完了しました")

if __name__ == "__main__":
    test_thumbnail_generation()
