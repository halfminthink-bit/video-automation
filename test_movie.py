"""
ズームを滑らかにする改善版
- fps を 60 に上げる
- リサイズの精度を上げる
- イージング関数を使う
"""

import sys
from pathlib import Path
import numpy as np
from PIL import Image
import math

print("=" * 60)
print("滑らかなズームアニメーション - 改善版")
print("=" * 60)

# インポート
try:
    from moviepy import VideoClip
    import moviepy
    print(f"✓ MoviePy version: {moviepy.__version__}")
except ImportError as e:
    print(f"✗ MoviePy import failed: {e}")
    sys.exit(1)

# テスト画像
test_images_dir = Path("data/working/織田信長/03_images/generated")
if not test_images_dir.exists():
    print(f"✗ 画像ディレクトリが見つかりません")
    sys.exit(1)

images = list(test_images_dir.glob("*.png"))
if not images:
    print(f"✗ 画像が見つかりません")
    sys.exit(1)

test_img = images[0]
print(f"\n使用する画像: {test_img.name}")

output_dir = Path("test_output/smooth")
output_dir.mkdir(parents=True, exist_ok=True)

# 元画像読み込み
img = Image.open(test_img)
img_array = np.array(img)
h, w = img_array.shape[:2]

print(f"画像サイズ: {w}x{h}")

# ========================================
# イージング関数
# ========================================

def ease_in_out(t):
    """
    イージング関数（滑らかな加減速）
    t: 0.0 ~ 1.0
    """
    return t * t * (3 - 2 * t)  # Smoothstep

def ease_out(t):
    """
    イーズアウト（最初速く、後からゆっくり）
    """
    return 1 - (1 - t) * (1 - t)

def ease_in(t):
    """
    イーズイン（最初ゆっくり、後から速く）
    """
    return t * t

# ========================================
# パターン1: 標準ズームイン（30fps・線形）
# ========================================
print("\n[1] 標準ズームイン - 30fps・線形")
print("    比較用: 元の実装")

try:
    duration = 8
    fps = 30
    
    def make_frame_1(t):
        zoom = 1.0 + 0.03 * (t / duration)
        new_w, new_h = int(w * zoom), int(h * zoom)
        resized = Image.fromarray(img_array).resize((new_w, new_h), Image.LANCZOS)
        resized_array = np.array(resized)
        start_x, start_y = (new_w - w) // 2, (new_h - h) // 2
        return resized_array[start_y:start_y+h, start_x:start_x+w]
    
    clip = VideoClip(make_frame_1, duration=duration).with_fps(fps)
    output = output_dir / "01_zoom_30fps_linear.mp4"
    clip.write_videofile(str(output), fps=fps, codec='libx264', audio=False, logger=None)
    print(f"✓ 完了: {output.name}")
except Exception as e:
    print(f"✗ 失敗: {e}")

# ========================================
# パターン2: 60fps（高フレームレート）
# ========================================
print("\n[2] 標準ズームイン - 60fps・線形")
print("    改善: フレームレートを2倍に")

try:
    duration = 8
    fps = 60
    
    def make_frame_2(t):
        zoom = 1.0 + 0.03 * (t / duration)
        new_w, new_h = int(w * zoom), int(h * zoom)
        resized = Image.fromarray(img_array).resize((new_w, new_h), Image.LANCZOS)
        resized_array = np.array(resized)
        start_x, start_y = (new_w - w) // 2, (new_h - h) // 2
        return resized_array[start_y:start_y+h, start_x:start_x+w]
    
    clip = VideoClip(make_frame_2, duration=duration).with_fps(fps)
    output = output_dir / "02_zoom_60fps_linear.mp4"
    clip.write_videofile(str(output), fps=fps, codec='libx264', audio=False, logger=None)
    print(f"✓ 完了: {output.name}")
except Exception as e:
    print(f"✗ 失敗: {e}")

# ========================================
# パターン3: 60fps + イーズインアウト
# ========================================
print("\n[3] ズームイン - 60fps・イーズインアウト")
print("    改善: 滑らかな加減速")

try:
    duration = 8
    fps = 60
    
    def make_frame_3(t):
        progress = ease_in_out(t / duration)  # 0.0 ~ 1.0
        zoom = 1.0 + 0.03 * progress
        new_w, new_h = int(w * zoom), int(h * zoom)
        resized = Image.fromarray(img_array).resize((new_w, new_h), Image.LANCZOS)
        resized_array = np.array(resized)
        start_x, start_y = (new_w - w) // 2, (new_h - h) // 2
        return resized_array[start_y:start_y+h, start_x:start_x+w]
    
    clip = VideoClip(make_frame_3, duration=duration).with_fps(fps)
    output = output_dir / "03_zoom_60fps_ease_in_out.mp4"
    clip.write_videofile(str(output), fps=fps, codec='libx264', audio=False, logger=None)
    print(f"✓ 完了: {output.name}")
except Exception as e:
    print(f"✗ 失敗: {e}")

# ========================================
# パターン4: 60fps + float精度のリサイズ
# ========================================
print("\n[4] ズームイン - 60fps・float精度")
print("    改善: ピクセル単位ではなくfloat精度でズーム")

try:
    duration = 8
    fps = 60
    
    def make_frame_4(t):
        progress = ease_in_out(t / duration)
        zoom = 1.0 + 0.03 * progress
        
        # float精度で計算（四捨五入しない）
        new_w_float = w * zoom
        new_h_float = h * zoom
        new_w = int(round(new_w_float))
        new_h = int(round(new_h_float))
        
        resized = Image.fromarray(img_array).resize((new_w, new_h), Image.LANCZOS)
        resized_array = np.array(resized)
        start_x, start_y = (new_w - w) // 2, (new_h - h) // 2
        return resized_array[start_y:start_y+h, start_x:start_x+w]
    
    clip = VideoClip(make_frame_4, duration=duration).with_fps(fps)
    output = output_dir / "04_zoom_60fps_float_precision.mp4"
    clip.write_videofile(str(output), fps=fps, codec='libx264', audio=False, logger=None)
    print(f"✓ 完了: {output.name}")
except Exception as e:
    print(f"✗ 失敗: {e}")

# ========================================
# パターン5: ズームアウト - 60fps・イーズインアウト
# ========================================
print("\n[5] ズームアウト - 60fps・イーズインアウト")
print("    1.04倍 → 1.0倍")

try:
    duration = 8
    fps = 60
    
    def make_frame_5(t):
        progress = ease_in_out(t / duration)
        zoom = 1.04 - 0.04 * progress
        new_w = int(round(w * zoom))
        new_h = int(round(h * zoom))
        
        resized = Image.fromarray(img_array).resize((new_w, new_h), Image.LANCZOS)
        resized_array = np.array(resized)
        
        if zoom < 1.0:
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            start_x = (w - new_w) // 2
            start_y = (h - new_h) // 2
            frame[start_y:start_y+new_h, start_x:start_x+new_w] = resized_array
            return frame
        else:
            start_x, start_y = (new_w - w) // 2, (new_h - h) // 2
            return resized_array[start_y:start_y+h, start_x:start_x+w]
    
    clip = VideoClip(make_frame_5, duration=duration).with_fps(fps)
    output = output_dir / "05_zoom_out_60fps_ease.mp4"
    clip.write_videofile(str(output), fps=fps, codec='libx264', audio=False, logger=None)
    print(f"✓ 完了: {output.name}")
except Exception as e:
    print(f"✗ 失敗: {e}")

# ========================================
# パターン6: 超微小ズーム - 60fps・イーズ
# ========================================
print("\n[6] 超微小ズームイン - 60fps・イーズインアウト")
print("    1.0倍 → 1.015倍（ほぼ気づかないレベル）")

try:
    duration = 8
    fps = 60
    
    def make_frame_6(t):
        progress = ease_in_out(t / duration)
        zoom = 1.0 + 0.015 * progress
        new_w = int(round(w * zoom))
        new_h = int(round(h * zoom))
        
        resized = Image.fromarray(img_array).resize((new_w, new_h), Image.LANCZOS)
        resized_array = np.array(resized)
        start_x, start_y = (new_w - w) // 2, (new_h - h) // 2
        return resized_array[start_y:start_y+h, start_x:start_x+w]
    
    clip = VideoClip(make_frame_6, duration=duration).with_fps(fps)
    output = output_dir / "06_ultra_subtle_zoom_60fps.mp4"
    clip.write_videofile(str(output), fps=fps, codec='libx264', audio=False, logger=None)
    print(f"✓ 完了: {output.name}")
except Exception as e:
    print(f"✗ 失敗: {e}")

# ========================================
# パターン7: 左パン（比較用・パンは元々滑らか）
# ========================================
print("\n[7] 左パン - 60fps（比較用）")
print("    パンは元々滑らか")

try:
    duration = 6
    fps = 60
    pan_zoom = 1.15
    pan_w, pan_h = int(w * pan_zoom), int(h * pan_zoom)
    panned_img = Image.fromarray(img_array).resize((pan_w, pan_h), Image.LANCZOS)
    panned_array = np.array(panned_img)
    
    def make_frame_7(t):
        progress = ease_in_out(t / duration)
        max_shift = pan_w - w
        shift = int(max_shift * progress)
        start_y = (pan_h - h) // 2
        return panned_array[start_y:start_y+h, shift:shift+w]
    
    clip = VideoClip(make_frame_7, duration=duration).with_fps(fps)
    output = output_dir / "07_pan_left_60fps.mp4"
    clip.write_videofile(str(output), fps=fps, codec='libx264', audio=False, logger=None)
    print(f"✓ 完了: {output.name}")
except Exception as e:
    print(f"✗ 失敗: {e}")

# まとめ
print("\n" + "=" * 60)
print("✓ 滑らかさ比較テスト完了")
print("=" * 60)
print(f"\n出力先: {output_dir.absolute()}\n")

print("比較ポイント:")
print("=" * 60)
print("1. 30fps・線形         - 元の実装（ガタつきあり）")
print("2. 60fps・線形         - fpsを上げただけ")
print("3. 60fps・イーズ       - 加減速で滑らか ★")
print("4. 60fps・float精度    - さらに精密")
print("5. ズームアウト・60fps - 縮小も滑らか")
print("6. 超微小ズーム・60fps - 気づかないレベル")
print("7. パン・60fps         - 比較用（パンは元々滑らか）")
print("\n★推奨: パターン3 or 4")
print("\n改善内容:")
print("  - fps: 30 → 60（フレーム数2倍）")
print("  - イージング: 加減速で自然な動き")
print("  - リサイズ精度: float計算でより滑らか")