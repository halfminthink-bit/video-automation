#!/usr/bin/env python3
"""
背景動画を1920x1080にリサイズするスクリプト
"""
import subprocess
import json
from pathlib import Path
from typing import List, Tuple


def get_video_resolution(video_path: Path) -> Tuple[int, int]:
    """動画の解像度を取得"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'json',
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        width = data['streams'][0]['width']
        height = data['streams'][0]['height']
        return (width, height)
    except Exception as e:
        print(f"⚠️  解像度取得エラー ({video_path.name}): {e}")
        return (0, 0)


def is_already_resized(video_path: Path, target_width: int = 1920, target_height: int = 1080) -> bool:
    """既にリサイズ済みかチェック"""
    width, height = get_video_resolution(video_path)
    return width == target_width and height == target_height


def resize_video(input_path: Path, output_path: Path, target_width: int = 1920, target_height: int = 1080) -> bool:
    """動画をリサイズ"""
    try:
        # アスペクト比を維持しつつ、1920x1080にフィット（黒パディング）
        filter_complex = (
            f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
            f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"
        )
        
        cmd = [
            'ffmpeg',
            '-i', str(input_path),
            '-vf', filter_complex,
            '-c:v', 'libx264',
            '-crf', '23',
            '-preset', 'medium',
            '-c:a', 'copy',  # 音声はそのまま
            '-y',  # 上書き
            str(output_path)
        ]
        
        print(f"  📹 リサイズ中: {input_path.name} → {output_path.name}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ エラー: {e.stderr}")
        return False
    except Exception as e:
        print(f"  ❌ 予期しないエラー: {e}")
        return False


def process_folder(folder_path: Path, overwrite: bool = False) -> Tuple[int, int]:
    """フォルダ内の全mp4ファイルを処理"""
    mp4_files = list(folder_path.glob('*.mp4'))
    processed = 0
    skipped = 0
    
    for video_path in mp4_files:
        print(f"\n📁 処理中: {video_path.name}")
        
        # 解像度チェック
        width, height = get_video_resolution(video_path)
        if width == 0 or height == 0:
            print(f"  ⚠️  スキップ: 解像度を取得できませんでした")
            skipped += 1
            continue
        
        print(f"  📐 現在の解像度: {width}x{height}")
        
        # 既にリサイズ済みかチェック
        if is_already_resized(video_path):
            print(f"  ✅ スキップ: 既に1920x1080です")
            skipped += 1
            continue
        
        # 出力パス決定
        if overwrite:
            output_path = video_path
            # 一時ファイル名で処理してから置き換え
            temp_path = video_path.with_suffix('.tmp.mp4')
            if resize_video(video_path, temp_path):
                temp_path.replace(output_path)
                processed += 1
            else:
                if temp_path.exists():
                    temp_path.unlink()
                skipped += 1
        else:
            # _resized.mp4で保存
            output_path = video_path.with_stem(f"{video_path.stem}_resized")
            if resize_video(video_path, output_path):
                processed += 1
            else:
                skipped += 1
    
    return processed, skipped


def main():
    """メイン処理"""
    base_dir = Path(__file__).parent.parent
    folders = [
        base_dir / 'assets' / 'background_videos' / 'opening',
        base_dir / 'assets' / 'background_videos' / 'main',
        base_dir / 'assets' / 'background_videos' / 'ending',
    ]
    
    print("=" * 60)
    print("🎬 背景動画リサイズスクリプト")
    print("=" * 60)
    print(f"📂 対象フォルダ: {len(folders)}個")
    print(f"🎯 目標解像度: 1920x1080")
    print(f"⚙️  品質設定: CRF 23, preset medium")
    print("=" * 60)
    
    total_processed = 0
    total_skipped = 0
    
    for folder in folders:
        if not folder.exists():
            print(f"\n⚠️  フォルダが見つかりません: {folder}")
            continue
        
        print(f"\n📂 フォルダ: {folder.relative_to(base_dir)}")
        processed, skipped = process_folder(folder, overwrite=True)
        total_processed += processed
        total_skipped += skipped
    
    print("\n" + "=" * 60)
    print("📊 処理結果")
    print("=" * 60)
    print(f"✅ リサイズ完了: {total_processed}個")
    print(f"⏭️  スキップ: {total_skipped}個")
    print("=" * 60)


if __name__ == '__main__':
    main()




