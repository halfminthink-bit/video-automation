"""ASSアニメーションタグの生成"""

from typing import List, Dict


class AnimationTagBuilder:
    """ASS字幕のアニメーションタグを生成"""
    
    def build_zoom_in(self, duration_ms: int, scale_from: int, scale_to: int) -> str:
        """
        ズームインアニメーションタグを生成
        
        Args:
            duration_ms: アニメーション時間（ミリ秒）
            scale_from: 開始スケール（%）
            scale_to: 終了スケール（%）
        
        Returns:
            ASS形式のアニメーションタグ
            例: \t(0,300,\fscx150\fscy150)
        """
        # シンプルな実装：開始スケールから終了スケールへ1つのタグで遷移
        # ASS形式では、\t(start,end,params)で時間範囲内でパラメータを変更
        return f"\\t(0,{duration_ms},\\fscx{scale_from}\\fscy{scale_from})"
    
    def build_fade_in(self, duration_ms: int) -> str:
        """
        フェードインタグを生成
        
        Args:
            duration_ms: フェード時間（ミリ秒）
        
        Returns:
            ASS形式のフェードタグ
            例: \fad(200,0)
        """
        return f"\\fad({duration_ms},0)"
    
    def build_all_tags(self, animations: List[Dict]) -> str:
        """
        全アニメーションタグを結合
        
        Args:
            animations: アニメーション設定のリスト
        
        Returns:
            結合されたタグ文字列
        """
        if not animations:
            return ""
        
        tags = []
        for anim in animations:
            anim_type = anim.get('type')
            
            if anim_type == 'zoom_in':
                tags.append(self.build_zoom_in(
                    anim.get('duration_ms', 300),
                    anim.get('scale_from', 150),
                    anim.get('scale_to', 100)
                ))
            elif anim_type == 'fade_in':
                tags.append(self.build_fade_in(
                    anim.get('duration_ms', 200)
                ))
        
        return ''.join(tags)

