"""
ffmpeg concat問題の診断スクリプト

このスクリプトは、ffmpegの結合処理をデバッグします。
"""

import subprocess
from pathlib import Path

def check_audio_files():
    """音声ファイルの存在確認"""
    print("=" * 80)
    print("1. 音声ファイルの確認")
    print("=" * 80)

    audio_dir = Path("data/working/織田信長/02_audio/sections")

    if not audio_dir.exists():
        print(f"❌ ディレクトリが存在しません: {audio_dir}")
        return False

    mp3_files = list(audio_dir.glob("section_*.mp3"))
    print(f"✓ {len(mp3_files)} 個のMP3ファイルが見つかりました")

    for mp3_file in sorted(mp3_files):
        size_mb = mp3_file.stat().st_size / 1024 / 1024
        print(f"  - {mp3_file.name}: {size_mb:.2f} MB")

        # ffprobeでファイルを確認
        try:
            cmd = ['ffprobe', '-v', 'error', '-show_format', '-show_streams', str(mp3_file)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"    ✓ ffprobeで読み込み可能")
            else:
                print(f"    ❌ ffprobeエラー: {result.stderr}")
        except Exception as e:
            print(f"    ❌ ffprobe実行エラー: {e}")

    return True


def test_ffmpeg_concat():
    """ffmpeg concatのテスト"""
    print("\n" + "=" * 80)
    print("2. ffmpeg concat テスト")
    print("=" * 80)

    audio_dir = Path("data/working/織田信長/02_audio/sections")
    mp3_files = sorted(list(audio_dir.glob("section_*.mp3")))

    if not mp3_files:
        print("❌ MP3ファイルが見つかりません")
        return

    # concat listファイルを作成
    concat_list = Path("debug_concat_list.txt")
    with open(concat_list, 'w', encoding='utf-8') as f:
        for mp3_file in mp3_files:
            # Windowsパスを/に変換
            path_str = str(mp3_file.absolute()).replace('\\', '/')
            f.write(f"file '{path_str}'\n")

    print(f"✓ concat listファイルを作成: {concat_list}")
    print("\n内容:")
    with open(concat_list, 'r', encoding='utf-8') as f:
        print(f.read())

    # ffmpegコマンドを実行
    output_file = Path("debug_output.mp3")

    print("\n実行するffmpegコマンド:")
    cmd = [
        'ffmpeg',
        '-f', 'concat',
        '-safe', '0',
        '-i', str(concat_list),
        '-c:a', 'libmp3lame',
        '-b:a', '128k',
        '-ar', '44100',
        '-y',
        str(output_file)
    ]
    print(' '.join(cmd))

    print("\nffmpegを実行中...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            print(f"✓ 成功！出力ファイル: {output_file}")
            size_mb = output_file.stat().st_size / 1024 / 1024
            print(f"  ファイルサイズ: {size_mb:.2f} MB")
        else:
            print(f"❌ ffmpegがエラーコード {result.returncode} で失敗")
            print(f"\nSTDOUT:\n{result.stdout}")
            print(f"\nSTDERR:\n{result.stderr}")
    except subprocess.TimeoutExpired:
        print("❌ タイムアウト（30秒）")
    except Exception as e:
        print(f"❌ 実行エラー: {e}")

    # クリーンアップ
    if concat_list.exists():
        concat_list.unlink()


def main():
    print("ffmpeg concat 診断スクリプト")
    print("=" * 80)

    if check_audio_files():
        test_ffmpeg_concat()

    print("\n" + "=" * 80)
    print("診断完了")


if __name__ == "__main__":
    main()
