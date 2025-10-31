#!/usr/bin/env python3
"""
Wikimedia画像ダウンロードテスト

実際にWikimediaから画像をダウンロードして、
正しい画像が取得できるかを確認します。

使用方法:
    python test_wikimedia_download.py "Oda Nobunaga" --max-images 5

出力:
    test_downloads/ ディレクトリに画像がダウンロードされます
"""

import sys
import requests
import json
import time
from pathlib import Path
from typing import List, Dict, Any
import argparse


class WikimediaImageCollector:
    """Wikimedia画像収集・ダウンロードクラス"""
    
    def __init__(self, output_dir: str = "test_downloads"):
        self.base_url = "https://commons.wikimedia.org/w/api.php"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'VideoAutomation/1.0 Test (test@example.com)'
        })
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def search_images_by_category(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        カテゴリベースで画像を検索
        
        Args:
            query: 検索キーワード（例: "Oda Nobunaga"）
            limit: 取得する画像の最大数
            
        Returns:
            画像情報のリスト
        """
        print(f"\n{'='*60}")
        print(f"カテゴリベース検索: '{query}'")
        print(f"{'='*60}")
        
        # ステップ1: カテゴリを検索
        print("\n1. カテゴリを検索中...")
        category_params = {
            'action': 'query',
            'list': 'search',
            'srsearch': f'Category:{query}',
            'srnamespace': 14,  # Category namespace
            'srlimit': 5,
            'format': 'json'
        }
        
        try:
            response = self.session.get(self.base_url, params=category_params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            categories = []
            if 'query' in data and 'search' in data['query']:
                categories = [item['title'] for item in data['query']['search']]
                print(f"✓ {len(categories)}件のカテゴリが見つかりました:")
                for cat in categories[:3]:
                    print(f"  - {cat}")
            
            if not categories:
                print("✗ カテゴリが見つかりませんでした")
                return []
            
            # ステップ2: カテゴリからファイルを取得
            print(f"\n2. カテゴリ '{categories[0]}' からファイルを取得中...")
            time.sleep(0.5)  # APIレート制限を考慮
            
            files_params = {
                'action': 'query',
                'list': 'categorymembers',
                'cmtitle': categories[0],
                'cmtype': 'file',
                'cmlimit': limit,
                'format': 'json'
            }
            
            response = self.session.get(self.base_url, params=files_params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            file_titles = []
            if 'query' in data and 'categorymembers' in data['query']:
                file_titles = [item['title'] for item in data['query']['categorymembers']]
                print(f"✓ {len(file_titles)}件のファイルが見つかりました")
            else:
                print("✗ ファイルが見つかりませんでした")
                return []
            
            # ステップ3: 各ファイルの詳細情報を取得
            print(f"\n3. ファイルの詳細情報を取得中...")
            images = []
            
            for title in file_titles:
                time.sleep(0.3)  # APIレート制限
                image_info = self.get_image_info(title)
                if image_info:
                    images.append(image_info)
                    print(f"  ✓ {title}")
                    print(f"    URL: {image_info.get('url', 'N/A')[:80]}...")
                    print(f"    サイズ: {image_info.get('width', 0)}x{image_info.get('height', 0)}")
            
            return images
            
        except requests.exceptions.RequestException as e:
            print(f"✗ ネットワークエラー: {e}")
            return []
        except Exception as e:
            print(f"✗ エラー: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_image_info(self, title: str) -> Dict[str, Any]:
        """
        画像の詳細情報を取得
        
        Args:
            title: ファイルタイトル（例: "File:Oda Nobunaga.jpg"）
            
        Returns:
            画像情報の辞書
        """
        params = {
            'action': 'query',
            'titles': title,
            'prop': 'imageinfo',
            'iiprop': 'url|size|mime|extmetadata',
            'format': 'json'
        }
        
        try:
            response = self.session.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if 'query' in data and 'pages' in data['query']:
                page_data = list(data['query']['pages'].values())[0]
                
                if 'imageinfo' in page_data and page_data['imageinfo']:
                    img_info = page_data['imageinfo'][0]
                    
                    # メタデータから説明を取得
                    description = ""
                    if 'extmetadata' in img_info:
                        metadata = img_info['extmetadata']
                        if 'ImageDescription' in metadata:
                            desc_value = metadata['ImageDescription'].get('value', '')
                            # HTMLタグを除去
                            import re
                            description = re.sub(r'<[^>]+>', '', desc_value)
                    
                    return {
                        'title': title,
                        'url': img_info.get('url', ''),
                        'width': img_info.get('width', 0),
                        'height': img_info.get('height', 0),
                        'size': img_info.get('size', 0),
                        'mime': img_info.get('mime', ''),
                        'description': description
                    }
            
        except Exception as e:
            print(f"    ✗ 情報取得エラー ({title}): {e}")
        
        return {}
    
    def download_image(self, image_info: Dict[str, Any], index: int) -> bool:
        """
        画像をダウンロード
        
        Args:
            image_info: get_image_info()が返した画像情報
            index: ファイル名に使うインデックス
            
        Returns:
            成功したらTrue
        """
        url = image_info.get('url')
        if not url:
            return False
        
        # ファイル名を生成（元のファイル名から拡張子を取得）
        title = image_info.get('title', '')
        ext = Path(title).suffix if '.' in title else '.jpg'
        filename = f"{index:03d}_{title.replace('File:', '').replace('/', '_')[:50]}{ext}"
        filepath = self.output_dir / filename
        
        try:
            print(f"\nダウンロード中: {filename}")
            response = self.session.get(url, timeout=60, stream=True)
            response.raise_for_status()
            
            # ファイルに保存
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size_mb = filepath.stat().st_size / (1024 * 1024)
            print(f"  ✓ 保存しました: {filepath} ({file_size_mb:.2f} MB)")
            
            # メタデータをJSONで保存
            meta_filepath = filepath.with_suffix('.json')
            with open(meta_filepath, 'w', encoding='utf-8') as f:
                json.dump(image_info, f, indent=2, ensure_ascii=False)
            
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"  ✗ ダウンロード失敗: {e}")
            return False
        except Exception as e:
            print(f"  ✗ エラー: {e}")
            return False
    
    def collect_and_download(self, query: str, max_images: int = 5) -> Dict[str, Any]:
        """
        画像を検索してダウンロード
        
        Args:
            query: 検索キーワード
            max_images: ダウンロードする画像の最大数
            
        Returns:
            実行結果のサマリー
        """
        print(f"\n🎯 '{query}' の画像を収集します")
        print(f"最大{max_images}枚の画像をダウンロードします")
        print(f"保存先: {self.output_dir}")
        
        # 画像を検索
        images = self.search_images_by_category(query, limit=max_images * 2)
        
        if not images:
            print("\n⚠ 画像が見つかりませんでした")
            return {
                'success': False,
                'downloaded': 0,
                'total_found': 0
            }
        
        # 品質フィルタリング（最低解像度）
        print(f"\n4. 品質フィルタリング中...")
        MIN_WIDTH = 800
        MIN_HEIGHT = 600
        
        filtered_images = []
        for img in images:
            width = img.get('width', 0)
            height = img.get('height', 0)
            
            if width >= MIN_WIDTH and height >= MIN_HEIGHT:
                filtered_images.append(img)
            else:
                print(f"  ✗ スキップ: {img.get('title', '')} (サイズ不足: {width}x{height})")
        
        print(f"✓ {len(filtered_images)}件がフィルタを通過しました")
        
        # ダウンロード
        print(f"\n5. 画像をダウンロード中...")
        downloaded_count = 0
        
        for i, img in enumerate(filtered_images[:max_images], 1):
            time.sleep(0.5)  # レート制限
            if self.download_image(img, i):
                downloaded_count += 1
        
        # サマリー
        result = {
            'success': downloaded_count > 0,
            'downloaded': downloaded_count,
            'total_found': len(images),
            'filtered': len(filtered_images),
            'output_dir': str(self.output_dir)
        }
        
        print(f"\n{'='*60}")
        print("ダウンロード完了")
        print(f"{'='*60}")
        print(f"検索結果: {len(images)}件")
        print(f"フィルタ通過: {len(filtered_images)}件")
        print(f"ダウンロード成功: {downloaded_count}件")
        print(f"保存先: {self.output_dir.absolute()}")
        
        return result


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description='Wikimediaから画像をダウンロードしてテストします'
    )
    parser.add_argument(
        'query',
        help='検索キーワード（例: "Oda Nobunaga"）'
    )
    parser.add_argument(
        '--max-images',
        type=int,
        default=5,
        help='ダウンロードする画像の最大数（デフォルト: 5）'
    )
    parser.add_argument(
        '--output-dir',
        default='test_downloads',
        help='画像の保存先ディレクトリ（デフォルト: test_downloads）'
    )
    
    args = parser.parse_args()
    
    print("\n" + "🚀 "*20)
    print("Wikimedia 画像ダウンロードテスト")
    print("🚀 "*20)
    
    # 画像を収集・ダウンロード
    collector = WikimediaImageCollector(output_dir=args.output_dir)
    result = collector.collect_and_download(
        query=args.query,
        max_images=args.max_images
    )
    
    # 結果に応じてメッセージ表示
    if result['success']:
        print("\n✅ テスト成功！")
        print(f"\n{args.output_dir}/ ディレクトリを確認してください。")
        print("正しい画像がダウンロードされているか確認してください。")
    else:
        print("\n❌ テスト失敗")
        print("画像をダウンロードできませんでした。")
        print("\n対策:")
        print("1. 検索キーワードを変更してみてください")
        print("2. 英語名で試してください（例: 'Oda Nobunaga'）")
        print("3. ネットワーク接続を確認してください")
    
    return 0 if result['success'] else 1


if __name__ == "__main__":
    sys.exit(main())