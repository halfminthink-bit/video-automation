"""
DALL-E 3 デバッグスクリプト

このスクリプトは、DALL-E 3 APIの動作を確認し、エラーの詳細を表示します。
"""

import os
import sys
from pathlib import Path

# .envファイルを読み込む
try:
    from dotenv import load_dotenv, find_dotenv
    # config/.envを最優先、無ければfind_dotenvで探索
    dotenv_path = Path(__file__).parent / "config" / ".env"
    if dotenv_path.exists():
        print(f"✓ Loading .env from: {dotenv_path}")
        load_dotenv(dotenv_path, override=False)
    else:
        found = find_dotenv(usecwd=True)
        if found:
            print(f"✓ Loading .env from: {found}")
            load_dotenv(found, override=False)
        else:
            print("⚠ .env file not found")
except ImportError:
    print("⚠ python-dotenv not installed")

# 環境変数を確認
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    print(f"✓ OPENAI_API_KEY found: {api_key[:10]}...{api_key[-4:]}")
else:
    print("✗ OPENAI_API_KEY not found in environment variables")
    print("\nAvailable environment variables:")
    for key in os.environ.keys():
        if "API" in key or "KEY" in key:
            print(f"  - {key}")
    sys.exit(1)

# OpenAI SDKをインポート
try:
    from openai import OpenAI
    print("✓ OpenAI SDK imported successfully")
except ImportError as e:
    print(f"✗ Failed to import OpenAI SDK: {e}")
    print("\nPlease install OpenAI SDK:")
    print("  pip install openai")
    sys.exit(1)

# OpenAI clientを作成
try:
    client = OpenAI()
    print("✓ OpenAI client created successfully")
except Exception as e:
    print(f"✗ Failed to create OpenAI client: {e}")
    print(f"Error type: {type(e).__name__}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# テスト用のプロンプト
test_prompt = """Create a professional YouTube thumbnail image with the following specifications:

TITLE TEXT (MUST BE CLEARLY VISIBLE):
"テストサムネイル"

SUBJECT:
Test thumbnail for debugging

DESIGN REQUIREMENTS:
- The title text MUST be in large, bold Japanese characters
- Text should be prominently displayed in the center area
- Use high contrast colors for maximum readability
- Add text outline/stroke for visibility
- Dramatic lighting, high contrast
- Eye-catching and professional

The Japanese text "テストサムネイル" must be clearly readable.
"""

print("\n" + "="*60)
print("Testing DALL-E 3 API...")
print("="*60)
print(f"\nPrompt:\n{test_prompt[:200]}...\n")

# DALL-E 3で画像を生成
try:
    response = client.images.generate(
        model="dall-e-3",
        prompt=test_prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )
    print("✓ DALL-E 3 API call successful!")
    print(f"✓ Image URL: {response.data[0].url}")
    print("\n" + "="*60)
    print("SUCCESS: DALL-E 3 is working correctly!")
    print("="*60)
    
except Exception as e:
    print(f"\n✗ DALL-E 3 API call failed!")
    print(f"Error type: {type(e).__name__}")
    print(f"Error message: {str(e)}")
    print("\nFull traceback:")
    import traceback
    traceback.print_exc()
    print("\n" + "="*60)
    print("FAILED: Please check the error details above")
    print("="*60)
    sys.exit(1)
