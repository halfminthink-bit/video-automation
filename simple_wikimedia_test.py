#!/usr/bin/env python3
"""
Wikimedia検索テスト（シンプル版）

Wikimedia APIの各検索戦略を個別にテストできます。

使用方法:
    python scripts/simple_wikimedia_test.py "Oda Nobunaga"
"""

import sys
import requests
import json
import time
from pathlib import Path


def test_category_search(query: str):
    """カテゴリベース検索のテスト"""
    print("\n" + "="*60)
    print("テスト: カテゴリ検索")
    print("="*60)
    
    base_url = "https://commons.wikimedia.org/w/api.php"
    
    # User-Agentヘッダーを設定（必須）
    headers = {
        'User-Agent': 'VideoAutomation/1.0 (https://github.com/yourproject; test@example.com)'
    }
    
    # ステップ1: カテゴリを検索
    print(f"\n1. カテゴリを検索: '{query}'")
    params = {
        'action': 'query',
        'list': 'search',
        'srsearch': f'Category:{query}',
        'srnamespace': 14,
        'srlimit': 5,
        'format': 'json'
    }
    
    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        categories = []
        if 'query' in data and 'search' in data['query']:
            categories = [item['title'] for item in data['query']['search']]
            
            print(f"✓ {len(categories)}件のカテゴリが見つかりました:")
            for i, cat in enumerate(categories, 1):
                print(f"  {i}. {cat}")
        else:
            print("✗ カテゴリが見つかりませんでした")
            return False
        
        if not categories:
            return False
        
        # ステップ2: 最初のカテゴリからファイルを取得
        print(f"\n2. カテゴリからファイルを取得: '{categories[0]}'")
        time.sleep(0.5)
        
        params = {
            'action': 'query',
            'list': 'categorymembers',
            'cmtitle': categories[0],
            'cmtype': 'file',
            'cmlimit': 10,
            'format': 'json'
        }
        
        response = requests.get(base_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if 'query' in data and 'categorymembers' in data['query']:
            files = data['query']['categorymembers']
            
            print(f"✓ {len(files)}件のファイルが見つかりました:")
            for i, file in enumerate(files[:5], 1):  # 最初の5件のみ表示
                print(f"  {i}. {file['title']}")
            
            return len(files) > 0
        else:
            print("✗ ファイルが見つかりませんでした")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ ネットワークエラー: {e}")
        return False
    except Exception as e:
        print(f"✗ エラー: {e}")
        return False


def test_query_search(query: str):
    """クエリベース検索のテスト"""
    print("\n" + "="*60)
    print("テスト: クエリ検索")
    print("="*60)
    
    base_url = "https://commons.wikimedia.org/w/api.php"
    
    # User-Agentヘッダーを設定（必須）
    headers = {
        'User-Agent': 'VideoAutomation/1.0 (https://github.com/yourproject; test@example.com)'
    }
    
    print(f"\nクエリで検索: 'File:{query}'")
    params = {
        'action': 'query',
        'generator': 'search',
        'gsrsearch': f'File:{query}',
        'gsrnamespace': 6,
        'gsrlimit': 10,
        'prop': 'imageinfo',
        'iiprop': 'url|size',
        'format': 'json'
    }
    
    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if 'query' in data and 'pages' in data['query']:
            pages = data['query']['pages']
            
            print(f"✓ {len(pages)}件のファイルが見つかりました:")
            for i, (page_id, page) in enumerate(list(pages.items())[:5], 1):
                title = page.get('title', 'Unknown')
                print(f"  {i}. {title}")
                
                if 'imageinfo' in page:
                    info = page['imageinfo'][0]
                    width = info.get('width', 0)
                    height = info.get('height', 0)
                    print(f"     サイズ: {width}x{height}")
            
            return len(pages) > 0
        else:
            print("✗ ファイルが見つかりませんでした")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ ネットワークエラー: {e}")
        return False
    except Exception as e:
        print(f"✗ エラー: {e}")
        return False


def test_japanese_vs_english():
    """日本語と英語の検索結果を比較"""
    print("\n" + "="*60)
    print("テスト: 日本語 vs 英語")
    print("="*60)
    
    test_cases = [
        ("織田信長", "Oda Nobunaga"),
        ("徳川家康", "Tokugawa Ieyasu"),
    ]
    
    results = []
    
    for japanese, english in test_cases:
        print(f"\n\n{'─'*60}")
        print(f"比較: {japanese} vs {english}")
        print('─'*60)
        
        # 日本語で検索
        print(f"\n[日本語] {japanese}")
        jp_success = test_category_search(japanese)
        jp_count = "成功" if jp_success else "失敗"
        
        time.sleep(1)
        
        # 英語で検索
        print(f"\n[英語] {english}")
        en_success = test_category_search(english)
        en_count = "成功" if en_success else "失敗"
        
        # 結果をまとめる
        results.append({
            'japanese': japanese,
            'english': english,
            'jp_result': jp_count,
            'en_result': en_count
        })
        
        time.sleep(1)
    
    # サマリー表示
    print("\n\n" + "="*60)
    print("結果サマリー")
    print("="*60)
    
    for result in results:
        print(f"\n{result['japanese']} / {result['english']}")
        print(f"  日本語: {result['jp_result']}")
        print(f"  英語: {result['en_result']}")


def main():
    """メイン処理"""
    print("\n" + "🔍 "*20)
    print("Wikimedia検索精度テスト")
    print("🔍 "*20)
    
    # コマンドライン引数があればそれを使用
    if len(sys.argv) > 1:
        query = sys.argv[1]
        print(f"\n検索キーワード: {query}\n")
        
        # カテゴリ検索
        cat_success = test_category_search(query)
        time.sleep(1)
        
        # クエリ検索
        query_success = test_query_search(query)
        
        # 結果サマリー
        print("\n\n" + "="*60)
        print("結果")
        print("="*60)
        print(f"カテゴリ検索: {'✓ 成功' if cat_success else '✗ 失敗'}")
        print(f"クエリ検索: {'✓ 成功' if query_success else '✗ 失敗'}")
        
        if cat_success:
            print("\n推奨: カテゴリ検索を使用してください（最も正確）")
        elif query_success:
            print("\n推奨: クエリ検索を使用してください（カテゴリがありません）")
        else:
            print("\n⚠ どちらの方法でも結果が得られませんでした")
            print("  - 検索キーワードを変更してください")
            print("  - 英語名で試してください")
    
    else:
        # 日本語 vs 英語の比較テスト
        test_japanese_vs_english()
        
        print("\n\n" + "="*60)
        print("結論")
        print("="*60)
        print("✓ 英語キーワードを使用することを強く推奨します")
        print("✓ カテゴリ検索が最も正確です")
        print("\n使い方:")
        print("  python scripts/simple_wikimedia_test.py 'Oda Nobunaga'")


if __name__ == "__main__":
    main()