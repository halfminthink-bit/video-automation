"""
画像収集システム

複数のソース（Wikimedia, Pexels, Unsplash, AI生成）から
最適な画像を収集する。
"""

import requests
import hashlib
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from ..core.models import CollectedImage, ImageClassification
from ..core.exceptions import ImageAPIError, APIRateLimitError


class WikimediaCollector:
    """
    Wikimedia Commons画像コレクター
    
    特徴:
    - 歴史的な画像が豊富
    - 高解像度画像が多い
    - APIキー不要
    - パブリックドメイン/CC-BY-SA
    """
    
    def __init__(
        self,
        user_agent: str = "VideoAutomation/1.0 (https://github.com/yourproject; contact@example.com)",
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化
        
        Args:
            user_agent: User-Agentヘッダー（Wikimediaのポリシーで必須）
            logger: ロガー
        """
        self.base_url = "https://commons.wikimedia.org/w/api.php"
        self.session = requests.Session()
        self.logger = logger or logging.getLogger(__name__)
        
        # 重要: Wikimediaは適切なUser-Agentを要求
        self.session.headers.update({
            "User-Agent": user_agent
        })
    
    def search_images(
        self,
        query: str,
        limit: int = 10,
        min_width: int = 1280,
        min_height: int = 720,
        use_category: bool = True
    ) -> List[Dict]:
        """
        画像を検索
        
        Args:
            query: 検索キーワード
            limit: 取得する画像数
            min_width: 最小幅
            min_height: 最小高さ
            use_category: カテゴリ検索を試みるか
            
        Returns:
            画像情報のリスト
        """
        images = []
        
        # 変数を初期化（ログ出力で使用）
        category_images = []
        search_images = []
        fallback_images = []
        
        # 方法1: カテゴリ検索（最も正確）
        if use_category:
            category_images = self._search_by_category(query, limit * 2)
            images.extend(category_images)
        
        # 方法2: MediaSearch API（推奨）
        if len(images) < limit:
            search_images = self._search_with_mediasearch(query, limit * 2)
            images.extend(search_images)
        
        # 方法3: ImageSearch API（フォールバック）
        if len(images) < limit:
            fallback_images = self._search_with_imagesearch(query, limit)
            images.extend(fallback_images)
        
        # 重複除去（URLでユニーク化）
        unique_images = []
        seen_urls = set()
        for img in images:
            if img['url'] not in seen_urls:
                seen_urls.add(img['url'])
                unique_images.append(img)
        
        # 解像度フィルタリング
        filtered = []
        for img in unique_images:
            if img['width'] >= min_width and img['height'] >= min_height:
                filtered.append(img)
        
        self.logger.info(
            f"Wikimedia: Found {len(filtered)} images for '{query}' "
            f"(category: {len(category_images)}, "
            f"search: {len(search_images)}, fallback: {len(fallback_images)})"
        )
        
        return filtered[:limit]
    
    def _search_by_category(self, query: str, limit: int) -> List[Dict]:
        """
        カテゴリから画像を取得（最も正確な方法）
        
        例: "Oda Nobunaga" → "Category:Oda Nobunaga"
        """
        # カテゴリ名のバリエーションを試す
        category_variants = [
            query,  # そのまま
            query.replace(" ", "_"),  # スペースをアンダースコアに
            f"Category:{query}",  # Categoryプレフィックス付き
        ]
        
        all_images = []
        for category_name in category_variants:
            params = {
                "action": "query",
                "format": "json",
                "generator": "categorymembers",
                "gcmtitle": f"Category:{category_name.replace('Category:', '')}",
                "gcmtype": "file",
                "gcmlimit": limit,
                "prop": "imageinfo",
                "iiprop": "url|size|mime",
                "iiurlwidth": 2000
            }
            
            try:
                response = self.session.get(
                    self.base_url,
                    params=params,
                    timeout=30
                )
                
                if response.status_code == 429:
                    self.logger.warning("Wikimedia rate limit, waiting...")
                    time.sleep(2)
                    continue
                
                response.raise_for_status()
                data = response.json()
                
                if "query" in data and "pages" in data["query"]:
                    for page in data["query"]["pages"].values():
                        if "imageinfo" in page:
                            info = page["imageinfo"][0]
                            
                            # 画像のみ（動画やPDF除外）
                            mime = info.get("mime", "")
                            if not mime.startswith("image/"):
                                continue
                            
                            all_images.append({
                                "title": page.get("title", ""),
                                "url": info.get("url", ""),
                                "thumb_url": info.get("thumburl", info.get("url", "")),
                                "width": info.get("width", 0),
                                "height": info.get("height", 0),
                                "mime": mime,
                                "source": "wikimedia_category"
                            })
                    
                    # 画像が見つかったらループ終了
                    if all_images:
                        break
                        
            except requests.exceptions.RequestException as e:
                self.logger.debug(f"Category search '{category_name}' failed: {e}")
                continue
            
            time.sleep(0.5)  # レート制限対策
        
        return all_images[:limit]
    
    def _search_with_mediasearch(self, query: str, limit: int) -> List[Dict]:
        """
        MediaSearch APIを使用（推奨）
        """
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": f"File:{query}",
            "gsrlimit": limit,
            "gsrnamespace": 6,  # File namespace
            "prop": "imageinfo",
            "iiprop": "url|size|mime",
            "iiurlwidth": 2000
        }
        
        try:
            response = self.session.get(
                self.base_url,
                params=params,
                timeout=30
            )
            
            if response.status_code == 429:
                raise APIRateLimitError("Wikimedia", retry_after=2)
            
            response.raise_for_status()
            data = response.json()
            
            images = []
            if "query" in data and "pages" in data["query"]:
                for page in data["query"]["pages"].values():
                    if "imageinfo" in page:
                        info = page["imageinfo"][0]
                        
                        mime = info.get("mime", "")
                        if not mime.startswith("image/"):
                            continue
                        
                        images.append({
                            "title": page.get("title", ""),
                            "url": info.get("url", ""),
                            "thumb_url": info.get("thumburl", info.get("url", "")),
                            "width": info.get("width", 0),
                            "height": info.get("height", 0),
                            "mime": mime,
                            "source": "wikimedia_search"
                        })
            
            return images
            
        except APIRateLimitError:
            raise
        except Exception as e:
            self.logger.debug(f"MediaSearch failed: {e}")
            return []
    
    def _search_with_imagesearch(self, query: str, limit: int) -> List[Dict]:
        """
        従来のImageSearch APIを使用（フォールバック）
        """
        params = {
            "action": "query",
            "format": "json",
            "list": "allimages",
            "aisort": "relevance",
            "aisearch": query,
            "ailimit": limit,
            "aiprop": "url|size|mime"
        }
        
        try:
            response = self.session.get(
                self.base_url,
                params=params,
                timeout=30
            )
            
            if response.status_code == 429:
                raise APIRateLimitError("Wikimedia", retry_after=2)
            
            response.raise_for_status()
            data = response.json()
            
            images = []
            if "query" in data and "allimages" in data["query"]:
                for img in data["query"]["allimages"]:
                    mime = img.get("mime", "")
                    if not mime.startswith("image/"):
                        continue
                    
                    images.append({
                        "title": img.get("name", ""),
                        "url": img.get("url", ""),
                        "thumb_url": img.get("thumburl", img.get("url", "")),
                        "width": img.get("width", 0),
                        "height": img.get("height", 0),
                        "mime": mime,
                        "source": "wikimedia_allimages"
                    })
            
            return images
            
        except APIRateLimitError:
            raise
        except Exception as e:
            self.logger.debug(f"ImageSearch failed: {e}")
            return []
    
    def download_image(self, url: str, output_path: Path) -> bool:
        """
        画像をダウンロード
        
        Args:
            url: 画像URL
            output_path: 保存先パス
            
        Returns:
            成功したらTrue
        """
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.content)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Download failed for {url}: {e}")
            return False


class PexelsCollector:
    """Pexels画像コレクター"""
    
    def __init__(
        self,
        api_key: str,
        logger: Optional[logging.Logger] = None
    ):
        self.api_key = api_key
        self.base_url = "https://api.pexels.com/v1"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": api_key
        })
        self.logger = logger or logging.getLogger(__name__)
    
    def search_images(
        self,
        query: str,
        limit: int = 10,
        min_width: int = 1280,
        min_height: int = 720
    ) -> List[Dict]:
        """画像を検索"""
        try:
            response = self.session.get(
                f"{self.base_url}/search",
                params={
                    "query": query,
                    "per_page": limit,
                    "orientation": "landscape"
                },
                timeout=30
            )
            
            if response.status_code == 429:
                raise APIRateLimitError("Pexels", retry_after=60)
            
            response.raise_for_status()
            data = response.json()
            
            images = []
            for photo in data.get("photos", []):
                src = photo.get("src", {})
                width = photo.get("width", 0)
                height = photo.get("height", 0)
                
                if width >= min_width and height >= min_height:
                    images.append({
                        "title": f"Pexels Photo {photo.get('id')}",
                        "url": src.get("original", ""),
                        "thumb_url": src.get("large2x", src.get("large", "")),
                        "width": width,
                        "height": height,
                        "mime": "image/jpeg",
                        "source": "pexels"
                    })
            
            self.logger.info(f"Pexels: Found {len(images)} images for '{query}'")
            return images
            
        except APIRateLimitError:
            raise
        except Exception as e:
            self.logger.error(f"Pexels search failed: {e}")
            return []
    
    def download_image(self, url: str, output_path: Path) -> bool:
        """画像をダウンロード"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.content)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Download failed for {url}: {e}")
            return False


class UnsplashCollector:
    """Unsplash画像コレクター"""
    
    def __init__(
        self,
        api_key: str,
        logger: Optional[logging.Logger] = None
    ):
        self.api_key = api_key
        self.base_url = "https://api.unsplash.com"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Client-ID {api_key}"
        })
        self.logger = logger or logging.getLogger(__name__)
    
    def search_images(
        self,
        query: str,
        limit: int = 10,
        min_width: int = 1280,
        min_height: int = 720
    ) -> List[Dict]:
        """画像を検索"""
        try:
            response = self.session.get(
                f"{self.base_url}/search/photos",
                params={
                    "query": query,
                    "per_page": limit,
                    "orientation": "landscape"
                },
                timeout=30
            )
            
            if response.status_code == 429:
                raise APIRateLimitError("Unsplash", retry_after=60)
            
            response.raise_for_status()
            data = response.json()
            
            images = []
            for photo in data.get("results", []):
                width = photo.get("width", 0)
                height = photo.get("height", 0)
                urls = photo.get("urls", {})
                
                if width >= min_width and height >= min_height:
                    images.append({
                        "title": photo.get("description") or photo.get("alt_description") or f"Unsplash {photo.get('id')}",
                        "url": urls.get("raw", ""),
                        "thumb_url": urls.get("regular", ""),
                        "width": width,
                        "height": height,
                        "mime": "image/jpeg",
                        "source": "unsplash"
                    })
            
            self.logger.info(f"Unsplash: Found {len(images)} images for '{query}'")
            return images
            
        except APIRateLimitError:
            raise
        except Exception as e:
            self.logger.error(f"Unsplash search failed: {e}")
            return []
    
    def download_image(self, url: str, output_path: Path) -> bool:
        """画像をダウンロード"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.content)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Download failed for {url}: {e}")
            return False


class ImageCollector:
    """
    統合画像コレクター
    
    複数のソースから画像を収集し、ダウンロードする。
    """
    
    def __init__(
        self,
        sources_config: List[Dict],
        output_dir: Path,
        logger: Optional[logging.Logger] = None
    ):
        """
        初期化
        
        Args:
            sources_config: ソース設定のリスト
            output_dir: 画像保存先
            logger: ロガー
        """
        self.output_dir = output_dir
        self.logger = logger or logging.getLogger(__name__)
        self.collectors = {}
        
        # 各コレクターを初期化
        for source in sources_config:
            name = source["name"]
            
            if name == "wikimedia":
                self.collectors[name] = WikimediaCollector(
                    user_agent=source.get("user_agent", "VideoAutomation/1.0"),
                    logger=self.logger
                )
            elif name == "pexels":
                api_key = source.get("api_key")
                if api_key:
                    self.collectors[name] = PexelsCollector(
                        api_key=api_key,
                        logger=self.logger
                    )
            elif name == "unsplash":
                api_key = source.get("api_key")
                if api_key:
                    self.collectors[name] = UnsplashCollector(
                        api_key=api_key,
                        logger=self.logger
                    )
        
        self.sources_config = sources_config
    
    def collect_images(
        self,
        keywords: List[str],
        target_count: int = 3,
        min_width: int = 1280,
        min_height: int = 720
    ) -> List[CollectedImage]:
        """
        キーワードリストから画像を収集
        
        Args:
            keywords: 検索キーワードのリスト
            target_count: 目標画像数
            min_width: 最小幅
            min_height: 最小高さ
            
        Returns:
            収集した画像のリスト
        """
        all_images = []
        
        # 優先度順にソースをソート
        sorted_sources = sorted(
            self.sources_config,
            key=lambda x: x.get("priority", 999)
        )
        
        for keyword in keywords:
            if len(all_images) >= target_count:
                break
            
            self.logger.info(f"Searching for '{keyword}'...")
            
            for source in sorted_sources:
                if len(all_images) >= target_count:
                    break
                
                name = source["name"]
                collector = self.collectors.get(name)
                
                if not collector:
                    continue
                
                limit = source.get("per_keyword_limit", 5)
                
                try:
                    # 検索
                    images = collector.search_images(
                        query=keyword,
                        limit=limit,
                        min_width=min_width,
                        min_height=min_height
                    )
                    
                    # ダウンロード
                    for img_data in images:
                        if len(all_images) >= target_count:
                            break
                        
                        # ファイル名生成
                        image_id = hashlib.md5(
                            f"{img_data['url']}".encode()
                        ).hexdigest()[:12]
                        
                        filename = f"{image_id}.jpg"
                        file_path = self.output_dir / filename
                        
                        # ダウンロード
                        if collector.download_image(img_data["url"], file_path):
                            # CollectedImageモデル作成
                            collected = CollectedImage(
                                image_id=image_id,
                                file_path=str(file_path),
                                source_url=img_data["url"],
                                source=img_data["source"],
                                classification=ImageClassification.LANDSCAPE,  # 後で分類
                                keywords=[keyword],
                                resolution=(img_data["width"], img_data["height"]),
                                aspect_ratio=img_data["width"] / img_data["height"],
                                quality_score=0.8
                            )
                            
                            all_images.append(collected)
                            self.logger.info(f"Downloaded: {filename}")
                    
                    time.sleep(0.5)  # レート制限対策
                    
                except APIRateLimitError as e:
                    self.logger.warning(f"{name} rate limit hit, skipping...")
                    continue
                except Exception as e:
                    self.logger.error(f"Error collecting from {name}: {e}")
                    continue
        
        self.logger.info(f"Collected {len(all_images)} images total")
        return all_images