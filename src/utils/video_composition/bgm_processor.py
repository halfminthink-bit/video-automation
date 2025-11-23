"""BGMを処理するユーティリティ"""

import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class BGMProcessor:
    """
    BGMの処理を担当
    
    機能:
    - オーディオフィルタ生成
    - BGMのループ・トリミング
    - フェードイン/アウト
    - 音量調整
    """
    
    def __init__(
        self,
        project_root: Path,
        logger,
        bgm_fade_in: float = 3.0,
        bgm_fade_out: float = 3.0
    ):
        """
        Args:
            project_root: プロジェクトのルートパス
            logger: ロガー
            bgm_fade_in: フェードイン時間（秒）
            bgm_fade_out: フェードアウト時間（秒）
        """
        self.project_root = project_root
        self.logger = logger
        self.bgm_fade_in = bgm_fade_in
        self.bgm_fade_out = bgm_fade_out
    
    def get_audio_duration(self, audio_path: Path) -> float:
        """
        音声ファイルの長さを取得
        
        Args:
            audio_path: 音声ファイルのパス
        
        Returns:
            音声の長さ（秒）
        """
        try:
            # ffprobe を使用して音声ファイルの長さを取得
            cmd = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(audio_path)
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=False,  # バイナリモードで
                check=True
            )
            duration_str = result.stdout.decode('utf-8', errors='ignore').strip()
            duration = float(duration_str)
            self.logger.debug(f"Audio duration ({audio_path.name}): {duration:.2f}s")
            return duration
        except Exception as e:
            self.logger.warning(f"Failed to get audio duration: {e}")
            return 10.0  # デフォルト値
    
    def build_audio_filter(
        self, 
        bgm_segments: List[dict], 
        narration_input: int = 1,
        bgm_input_start: int = 2
    ) -> str:
        """
        BGMミックス用のffmpegフィルター生成（セグメントごとの音量対応）

        戦略:
        1. 各BGMをループ・トリミング
        2. anullsrcで前に無音を追加
        3. concatで結合
        4. 各BGMに個別の音量を適用
        5. 全BGMをamixでミックス
        6. ナレーションとミックス
        
        Args:
            bgm_segments: BGMセグメント情報のリスト
            narration_input: ナレーション音声の入力インデックス（デフォルト: 1）
            bgm_input_start: BGMの開始入力インデックス（デフォルト: 2）
        
        Returns:
            FFmpegフィルター文字列
        """
        filters = []

        self.logger.info("=" * 60)
        self.logger.info("Building audio filter:")
        self.logger.info(f"  BGM segments: {len(bgm_segments)}")
        self.logger.info(f"  Narration input: {narration_input}, BGM start: {bgm_input_start}")

        # ナレーション
        filters.append(f"[{narration_input}:a]volume=1.0[narration]")

        # 各BGMセグメントを処理
        bgm_outputs = []
        for i, segment in enumerate(bgm_segments):
            input_idx = bgm_input_start + i  # BGMの入力インデックス
            start_time = segment.get('start_time', 0)
            duration = segment.get('duration', 0)
            fade_in = segment.get('fade_in', self.bgm_fade_in)
            fade_out = segment.get('fade_out', self.bgm_fade_out)
            bgm_volume = segment.get('volume', 0.13)  # セグメントごとの音量を取得

            # BGMファイルの実際の長さを取得
            bgm_path = Path(segment.get('file_path', ''))
            if bgm_path.exists():
                bgm_actual_duration = self.get_audio_duration(bgm_path)
            else:
                bgm_actual_duration = 30.0

            self.logger.info(
                f"  BGM {i+1} ({segment.get('bgm_type')}): "
                f"start={start_time:.1f}s, duration={duration:.1f}s, "
                f"bgm_length={bgm_actual_duration:.1f}s, "
                f"volume={bgm_volume:.1%}"
            )

            # Step 1: BGMをループ・トリミング
            if duration > bgm_actual_duration:
                loop_count = int(duration / bgm_actual_duration) + 2
                bgm_part = (
                    f"[{input_idx}:a]"
                    f"aloop=loop={loop_count}:size={int(bgm_actual_duration * 48000)},"
                    f"atrim=0:{duration},"
                    f"asetpts=PTS-STARTPTS"
                    f"[bgm{i}_trimmed]"
                )
                self.logger.info(f"    Looping {loop_count} times")
            else:
                bgm_part = (
                    f"[{input_idx}:a]"
                    f"atrim=0:{min(duration, bgm_actual_duration)},"
                    f"asetpts=PTS-STARTPTS"
                    f"[bgm{i}_trimmed]"
                )

            filters.append(bgm_part)

            # Step 2: フェード適用
            fade_part = (
                f"[bgm{i}_trimmed]"
                f"afade=t=in:st=0:d={fade_in},"
                f"afade=t=out:st={duration - fade_out}:d={fade_out},"
                f"volume={bgm_volume:.3f}"
                f"[bgm{i}_faded]"
            )
            filters.append(fade_part)

            # Step 3: 前に無音を追加（anullsrc + concat）
            if start_time > 0:
                silence_part = (
                    f"anullsrc=channel_layout=stereo:sample_rate=48000:duration={start_time}"
                    f"[silence{i}];"
                    f"[silence{i}][bgm{i}_faded]concat=n=2:v=0:a=1"
                    f"[bgm{i}]"
                )
                self.logger.info(f"    Adding {start_time:.1f}s silence before BGM")
            else:
                silence_part = f"[bgm{i}_faded]acopy[bgm{i}]"

            filters.append(silence_part)
            bgm_outputs.append(f'[bgm{i}]')

        # Step 4: 全BGMをミックス
        if len(bgm_outputs) > 1:
            bgm_mix = f"{''.join(bgm_outputs)}amix=inputs={len(bgm_outputs)}:duration=longest:dropout_transition=0[bgm_all]"
            filters.append(bgm_mix)
            self.logger.info(f"  Mixing {len(bgm_outputs)} BGM tracks")

            # Step 5: ナレーションとミックス（ナレーションの長さに合わせる）
            final_mix = "[narration][bgm_all]amix=inputs=2:duration=first:dropout_transition=3[audio]"
        else:
            if len(bgm_outputs) == 1:
                # BGMが1つのみの場合
                final_mix = "[narration][bgm0]amix=inputs=2:duration=first:dropout_transition=3[audio]"
            else:
                # BGMがない場合
                final_mix = "[narration]acopy[audio]"

        filters.append(final_mix)

        # フィルターを結合
        audio_filter = ";".join(filters)
        return audio_filter
    
    def create_bgm_filter_for_background(
        self,
        bgm_data: dict,
        audio_path: Path,
        num_bg_videos: int = 0,
        sfx_inputs: List[dict] = None,
        title_segments: List[dict] = None,
        bgm_volume_multiplier: float = 1.0
    ) -> Tuple[str, List[str]]:
        """
        BGMフィルターを作成（タイムラインに基づいた切り替え対応、効果音とタイトル区間の音量調整対応）

        Args:
            bgm_data: {"segments": [...]} 形式
            audio_path: 音声ファイルのパス
            num_bg_videos: 背景動画の数（BGMファイルの入力インデックス計算用）
            sfx_inputs: 効果音の入力情報リスト
            title_segments: セクションタイトル区間のリスト
            bgm_volume_multiplier: タイトル区間でのBGM音量倍率（デフォルト: 1.0）

        Returns:
            (bgm_filter, bgm_map) タプル
        """
        if not bgm_data or not bgm_data.get('segments'):
            # 音声のインデックスを決定
            if num_bg_videos == 0:
                return "", ['-map', '2:a']  # [2] = 音声（背景動画が事前処理済み）
            else:
                return "", ['-map', '1:a']  # [1] = 音声（旧実装）
        
        bgm_segments = bgm_data.get('segments', [])
        filters = []
        
        self.logger.info("=" * 60)
        self.logger.info("Building BGM filter for background video:")
        self.logger.info(f"  BGM segments: {len(bgm_segments)}")
        self.logger.info(f"  Background videos: {num_bg_videos}")
        
        # 入力インデックス計算:
        # num_bg_videos=0 の場合（背景動画が事前処理済み）:
        #   [0] = 背景動画（concat）, [1] = 画像（concat）, [2] = 音声, [3]以降 = BGM
        # num_bg_videos>0 の場合（背景動画が個別入力）:
        #   [0] = 画像, [1] = 音声, [2]以降 = 背景動画, その後 = BGM
        
        if num_bg_videos == 0:
            # 背景動画が事前処理済みの場合
            audio_input_idx = 2  # [2] = 音声
            bgm_start_index = 3  # [3]以降 = BGM
        else:
            # 背景動画が個別入力の場合（旧実装との互換性）
            audio_input_idx = 1  # [1] = 音声
            bgm_start_index = 2 + num_bg_videos  # [2+num_bg_videos]以降 = BGM
        
        # ナレーション
        filters.append(f"[{audio_input_idx}:a]volume=1.0[narration]")
        
        # ユニークなBGMファイルを取得（同じファイルが複数セグメントで使われる可能性がある）
        bgm_files_map = {}  # {file_path: input_index}
        current_bgm_index = bgm_start_index
        
        seen_files = set()
        for segment in bgm_segments:
            file_path = segment.get('file_path')
            if file_path and file_path not in seen_files:
                bgm_files_map[file_path] = current_bgm_index
                seen_files.add(file_path)
                current_bgm_index += 1
        
        # 各BGMセグメントを処理
        bgm_outputs = []
        for i, segment in enumerate(bgm_segments):
            file_path = segment.get('file_path')
            if not file_path:
                continue
            
            # このセグメントで使用するBGMファイルの入力インデックスを取得
            bgm_input_idx = bgm_files_map.get(file_path)
            if bgm_input_idx is None:
                continue
            
            start_time = segment.get('start_time', 0)
            duration = segment.get('duration', 0)
            fade_in = segment.get('fade_in', self.bgm_fade_in)
            fade_out = segment.get('fade_out', self.bgm_fade_out)
            bgm_volume = segment.get('volume', 0.13)  # セグメントごとの音量を取得
            
            # BGMファイルの実際の長さを取得
            bgm_path = Path(file_path)
            if not bgm_path.is_absolute():
                bgm_path = self.project_root / bgm_path
            
            if bgm_path.exists():
                bgm_actual_duration = self.get_audio_duration(bgm_path)
            else:
                bgm_actual_duration = 30.0
                self.logger.warning(f"BGM file not found: {bgm_path}, using default duration")
            
            self.logger.info(
                f"  BGM {i+1} ({segment.get('bgm_type', 'unknown')}): "
                f"start={start_time:.1f}s, duration={duration:.1f}s, "
                f"bgm_length={bgm_actual_duration:.1f}s, "
                f"volume={bgm_volume:.1%}"
            )
            
            # Step 1: BGMをループ・トリミング
            if duration > bgm_actual_duration:
                loop_count = int(duration / bgm_actual_duration) + 2
                bgm_part = (
                    f"[{bgm_input_idx}:a]"
                    f"aloop=loop={loop_count}:size={int(bgm_actual_duration * 48000)},"
                    f"atrim=0:{duration},"
                    f"asetpts=PTS-STARTPTS"
                    f"[bgm{i}_trimmed]"
                )
                self.logger.info(f"    Looping {loop_count} times")
            else:
                bgm_part = (
                    f"[{bgm_input_idx}:a]"
                    f"atrim=0:{min(duration, bgm_actual_duration)},"
                    f"asetpts=PTS-STARTPTS"
                    f"[bgm{i}_trimmed]"
                )
            
            filters.append(bgm_part)

            # Step 2: フェード適用 + タイトル区間の音量調整
            # タイトル区間での音量調整式を生成
            if title_segments and bgm_volume_multiplier != 1.0:
                # 動的音量式を生成
                volume_expr = f"{bgm_volume:.3f}"

                # タイトル区間では音量を下げる
                for seg in title_segments:
                    # グローバル時間で判定（start_timeオフセットを考慮）
                    seg_start_global = start_time + seg['start']
                    seg_end_global = start_time + seg['end']

                    # このBGMセグメントとタイトル区間が重なる場合のみ適用
                    bgm_end = start_time + duration
                    if seg_start_global < bgm_end and seg_end_global > start_time:
                        # ローカル時間に変換（このBGMセグメント内での時間）
                        local_start = max(0, seg['start'] - start_time)
                        local_end = min(duration, seg['end'] - start_time)

                        if local_start < duration and local_end > 0:
                            adjusted_volume = bgm_volume * bgm_volume_multiplier
                            volume_expr = (
                                f"if(between(t,{local_start:.3f},{local_end:.3f}),"
                                f"{adjusted_volume:.3f},"
                                f"{volume_expr})"
                            )

                fade_part = (
                    f"[bgm{i}_trimmed]"
                    f"afade=t=in:st=0:d={fade_in},"
                    f"afade=t=out:st={duration - fade_out}:d={fade_out},"
                    f"volume='{volume_expr}'"
                    f"[bgm{i}_faded]"
                )
            else:
                # タイトル区間の音量調整なし
                fade_part = (
                    f"[bgm{i}_trimmed]"
                    f"afade=t=in:st=0:d={fade_in},"
                    f"afade=t=out:st={duration - fade_out}:d={fade_out},"
                    f"volume={bgm_volume:.3f}"
                    f"[bgm{i}_faded]"
                )

            filters.append(fade_part)
            
            # Step 3: 前に無音を追加（anullsrc + concat）
            if start_time > 0:
                silence_part = (
                    f"anullsrc=channel_layout=stereo:sample_rate=48000:duration={start_time}"
                    f"[silence{i}];"
                    f"[silence{i}][bgm{i}_faded]concat=n=2:v=0:a=1"
                    f"[bgm{i}]"
                )
                self.logger.info(f"    Adding {start_time:.1f}s silence before BGM")
            else:
                silence_part = f"[bgm{i}_faded]acopy[bgm{i}]"
            
            filters.append(silence_part)
            bgm_outputs.append(f'[bgm{i}]')
        
        # Step 4: 全BGMをミックス
        if len(bgm_outputs) > 1:
            bgm_mix = f"{''.join(bgm_outputs)}amix=inputs={len(bgm_outputs)}:duration=longest:dropout_transition=0[bgm_all]"
            filters.append(bgm_mix)
            self.logger.info(f"  Mixing {len(bgm_outputs)} BGM tracks")
        elif len(bgm_outputs) == 1:
            # BGMが1つのみの場合はそのまま使用
            filters.append("[bgm0]acopy[bgm_all]")

        # Step 5: 効果音を処理
        sfx_outputs = []
        if sfx_inputs:
            # 効果音の開始インデックスを計算
            sfx_start_index = bgm_start_index + len(bgm_files_map)

            for i, sfx in enumerate(sfx_inputs):
                sfx_input_idx = sfx_start_index  # すべての効果音が同じファイルを使用
                start_time = sfx['start_time']
                volume = sfx.get('volume', 0.5)
                fade_in = sfx.get('fade_in', 0.05)
                fade_out = sfx.get('fade_out', 0.1)

                # 🔍 デバッグ: 効果音の詳細情報
                self.logger.info(f"  🔊 [DEBUG] SFX {i+1}: start={start_time:.2f}s, volume={volume}, fade_in={fade_in}s, fade_out={fade_out}s")

                # 効果音の処理（フェード + 音量調整）
                sfx_filter = (
                    f"[{sfx_input_idx}:a]"
                    f"afade=t=in:st=0:d={fade_in},"
                    f"afade=t=out:st=0.5:d={fade_out},"
                    f"volume={volume}"
                    f"[sfx{i}_faded];"
                )

                # 無音を追加してタイミング調整
                sfx_filter += (
                    f"anullsrc=channel_layout=stereo:sample_rate=48000:duration={start_time}"
                    f"[silence_sfx{i}];"
                    f"[silence_sfx{i}][sfx{i}_faded]concat=n=2:v=0:a=1"
                    f"[sfx{i}]"
                )

                filters.append(sfx_filter)
                sfx_outputs.append(f'[sfx{i}]')

            self.logger.info(f"  Added {len(sfx_outputs)} sound effects")

        # Step 6: 最終ミックス（ナレーション + BGM + 効果音）
        all_inputs = ['[narration]']

        if bgm_outputs:
            all_inputs.append('[bgm_all]')

        if sfx_outputs:
            all_inputs.extend(sfx_outputs)

        if len(all_inputs) > 1:
            final_mix = f"{''.join(all_inputs)}amix=inputs={len(all_inputs)}:duration=first:dropout_transition=3[audio]"
        else:
            final_mix = "[narration]acopy[audio]"

        filters.append(final_mix)
        
        # フィルターを結合
        bgm_filter = ";" + ";".join(filters)
        bgm_map = ['-map', '[audio]']
        
        return bgm_filter, bgm_map


