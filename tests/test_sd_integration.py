"""
Stable Diffusion統合テストスクリプト

使用方法:
1. config/.envにAPIキーを設定:
   - STABILITY_API_KEY
   - CLAUDE_API_KEY（オプション）

2. 実行:
   python test_sd_integration.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

# config/.envを明示的に読み込み
env_path = Path(__file__).parent / "config" / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
    print(f"✅ Loaded .env from: {env_path}")
else:
    print(f"⚠️  .env not found at: {env_path}")
    print(f"   Please create config/.env with API keys")

from src.generators.prompt_optimizer import PromptOptimizer
from src.generators.stable_diffusion_generator import StableDiffusionGenerator
from src.generators.image_generator import ImageGenerator


def test_prompt_optimizer():
    """プロンプト最適化のテスト"""
    print("\n" + "="*60)
    print("TEST 1: Prompt Optimizer")
    print("="*60)
    
    claude_key = os.getenv("CLAUDE_API_KEY")
    if not claude_key:
        print("⚠️  CLAUDE_API_KEY not found, skipping")
        return
    
    optimizer = PromptOptimizer(api_key=claude_key)
    
    # テストケース
    test_cases = [
        {
            "keyword": "織田信長の肖像",
            "atmosphere": "壮大",
            "context": "尾張の大うつけ",
            "image_type": "portrait"
        },
        {
            "keyword": "本能寺の変",
            "atmosphere": "劇的",
            "context": "明智光秀の謀反",
            "image_type": "battle"
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\nCase {i}: {case['keyword']}")
        print("-" * 60)
        
        prompt = optimizer.optimize(**case)
        
        print(f"Original: {case['keyword']}")
        print(f"Optimized:\n{prompt}\n")
    
    print("✅ Prompt optimizer test completed")


def test_stable_diffusion():
    """Stable Diffusion生成のテスト"""
    print("\n" + "="*60)
    print("TEST 2: Stable Diffusion Generator")
    print("="*60)
    
    stability_key = os.getenv("STABILITY_API_KEY")
    if not stability_key:
        print("❌ STABILITY_API_KEY not found")
        return
    
    generator = StableDiffusionGenerator(
        api_key=stability_key,
        output_dir=Path("test_output/sd")
    )
    
    # テスト生成
    print("\nGenerating test image...")
    print("-" * 60)
    
    prompt = """A dramatic historical scene of samurai warlord Oda Nobunaga, 
    photorealistic, cinematic lighting, 16:9 composition, 
    masterpiece, highly detailed, Japanese Sengoku period, 
    epic and grand atmosphere"""
    
    try:
        image = generator.generate(
            prompt=prompt,
            negative_prompt="modern, text, watermark",
            style="photorealistic",
            width=1344,
            height=768,
            keyword="織田信長"
        )
        
        print(f"\n✅ Image generated successfully!")
        print(f"   Path: {image.file_path}")
        print(f"   Resolution: {image.resolution}")
        print(f"   Cost: ${generator.get_total_cost():.4f}")
        
    except Exception as e:
        print(f"\n❌ Generation failed: {e}")


def test_integrated_generator():
    """統合画像生成器のテスト"""
    print("\n" + "="*60)
    print("TEST 3: Integrated Image Generator")
    print("="*60)
    
    stability_key = os.getenv("STABILITY_API_KEY")
    claude_key = os.getenv("CLAUDE_API_KEY")
    
    if not stability_key:
        print("❌ STABILITY_API_KEY not found")
        return
    
    # プロンプト最適化あり/なしの両方をテスト
    for use_optimizer in [False, True]:
        print(f"\n{'With' if use_optimizer else 'Without'} prompt optimization:")
        print("-" * 60)
        
        generator = ImageGenerator(
            api_key=stability_key,
            service="stable-diffusion",
            claude_api_key=claude_key if use_optimizer else None,
            output_dir=Path(f"test_output/integrated_{'opt' if use_optimizer else 'noopt'}")
        )
        
        try:
            image = generator.generate_image(
                keyword="桶狭間の戦い",
                atmosphere="劇的",
                section_context="今川義元との決戦",
                image_type="battle",
                style="oil_painting"
            )
            
            print(f"✅ Image generated!")
            print(f"   Path: {image.file_path}")
            print(f"   Cost: ${generator.get_total_cost():.4f}")
            
        except Exception as e:
            print(f"❌ Failed: {e}")


def main():
    """メインテスト"""
    print("\n" + "="*60)
    print("Stable Diffusion Integration Test")
    print("="*60)
    
    # 環境変数チェック
    print("\n🔑 Checking API Keys...")
    stability_key = os.getenv("STABILITY_API_KEY")
    claude_key = os.getenv("CLAUDE_API_KEY")
    
    print(f"   STABILITY_API_KEY: {'✅ Found' if stability_key else '❌ Not found'}")
    print(f"   CLAUDE_API_KEY: {'✅ Found' if claude_key else '⚠️  Not found (optional)'}")
    
    if not stability_key:
        print("\n❌ Please set STABILITY_API_KEY in config/.env file")
        return
    
    # 出力ディレクトリ作成
    Path("test_output").mkdir(exist_ok=True)
    
    # テスト実行
    try:
        test_prompt_optimizer()
        test_stable_diffusion()
        test_integrated_generator()
        
        print("\n" + "="*60)
        print("✅ All tests completed!")
        print("="*60)
        print("\n📁 Check test_output/ for generated images")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()