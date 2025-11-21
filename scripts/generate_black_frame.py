#!/usr/bin/env python3
"""
黒背景画像を生成するスクリプト

セクションタイトル表示時に使用する黒背景（1920x1080）を生成します。
"""

from pathlib import Path
from PIL import Image


def generate_black_frame(
    output_path: Path,
    resolution: tuple = (1920, 1080),
    color: str = "black"
) -> Path:
    """
    黒背景画像を生成

    Args:
        output_path: 出力先パス
        resolution: 解像度（幅, 高さ）
        color: 背景色（デフォルト: "black"）

    Returns:
        生成された画像のPath
    """
    # 親ディレクトリを作成
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 黒画像を生成
    img = Image.new('RGB', resolution, color=color)

    # 保存
    img.save(output_path)

    print(f"✅ 黒背景画像を生成しました: {output_path}")
    print(f"   解像度: {resolution[0]}x{resolution[1]}")
    print(f"   ファイルサイズ: {output_path.stat().st_size / 1024:.1f} KB")

    return output_path


def main():
    """メイン処理"""
    # プロジェクトルート
    project_root = Path(__file__).parent.parent

    # 出力先
    output_path = project_root / "assets" / "images" / "black_frame.png"

    # 既に存在する場合は確認
    if output_path.exists():
        print(f"⚠️  黒背景画像が既に存在します: {output_path}")
        response = input("上書きしますか？ (y/n): ")
        if response.lower() != 'y':
            print("キャンセルしました。")
            return

    # 黒画像を生成
    generate_black_frame(output_path)


if __name__ == "__main__":
    main()
