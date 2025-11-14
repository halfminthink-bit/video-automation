"""
Phase Orchestrator - 全フェーズを順次実行する司令塔

Phase 1-9 を順番に実行し、エラーハンドリングや
進捗管理を一元的に行う。
"""

from pathlib import Path
from typing import List, Optional
import logging
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.console import Console

from src.core.config_manager import ConfigManager
from src.core.models import PhaseExecution, PhaseStatus, ProjectStatus
from src.utils.logger import setup_logger

# 各Phaseをインポート
from src.phases.phase_01_script import Phase01Script
from src.phases.phase_02_audio import Phase02Audio
from src.phases.phase_03_images import Phase03Images
from src.phases.phase_04_animation import Phase04Animation
from src.phases.phase_05_bgm import Phase05BGM
from src.phases.phase_06_subtitles import Phase06Subtitles
from src.phases.phase_07_composition import Phase07Composition
from src.phases.phase_08_thumbnail import Phase08Thumbnail
from src.phases.phase_09_youtube import Phase09YouTube


class PhaseOrchestrator:
    """
    全フェーズを順次実行するオーケストレーター
    """

    def __init__(
        self,
        config: ConfigManager,
        logger: Optional[logging.Logger] = None,
        genre: Optional[str] = None,
        audio_var: Optional[str] = None,
        text_layout: Optional[str] = None,
        thumbnail_style: Optional[str] = None
    ):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.console = Console()
        self.genre = genre
        self.audio_var = audio_var
        self.text_layout = text_layout
        self.thumbnail_style = thumbnail_style

    def run_all_phases(
        self,
        subject: str,
        skip_if_exists: bool = True,
        from_phase: int = 1,
        until_phase: int = 9
    ) -> ProjectStatus:
        """
        全フェーズを順次実行

        Args:
            subject: 偉人名
            skip_if_exists: 既存出力があればスキップ
            from_phase: 開始フェーズ（1-9）
            until_phase: 終了フェーズ（1-9）

        Returns:
            ProjectStatus: プロジェクト全体の実行結果
        """
        self.logger.info(f"Starting video generation for: {subject}")
        self.logger.info(f"Phase range: {from_phase}-{until_phase}")

        # プロジェクトステータスを初期化
        project_status = ProjectStatus(
            subject=subject,
            overall_status=PhaseStatus.RUNNING,
            phases=[]
        )

        # 各Phaseのインスタンスを作成
        phases = self._initialize_phases(subject)

        # 指定範囲のフェーズのみ実行
        phases_to_run = [p for p in phases if from_phase <= p.get_phase_number() <= until_phase]

        # 進捗バーを表示
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=self.console
        ) as progress:

            # 全体タスク
            total_task = progress.add_task(
                f"[cyan]Generating video: {subject}",
                total=len(phases_to_run)
            )

            # 各フェーズを実行
            for phase in phases_to_run:
                phase_num = phase.get_phase_number()
                phase_name = phase.get_phase_name()

                # フェーズタスク
                phase_task = progress.add_task(
                    f"[yellow]Phase {phase_num}: {phase_name}",
                    total=100
                )

                # フェーズ実行
                execution = phase.run(skip_if_exists=skip_if_exists)
                project_status.phases.append(execution)

                # 進捗更新
                progress.update(phase_task, completed=100)
                progress.update(total_task, advance=1)

                # エラーチェック
                if execution.status == PhaseStatus.FAILED:
                    project_status.overall_status = PhaseStatus.FAILED
                    self.logger.error(f"Phase {phase_num} failed: {execution.error_message}")
                    self._print_error_summary(project_status)
                    return project_status

                # 成功ログ
                status_emoji = {
                    PhaseStatus.COMPLETED: "✅",
                    PhaseStatus.SKIPPED: "⏭️",
                    PhaseStatus.FAILED: "❌"
                }
                emoji = status_emoji.get(execution.status, "")

                # duration_secondsがNoneの場合は0.0にフォールバック
                duration = execution.duration_seconds if execution.duration_seconds is not None else 0.0

                self.console.print(
                    f"{emoji} Phase {phase_num}: {phase_name} "
                    f"({execution.status.value}, {duration:.1f}s)"
                )

        # 全フェーズ完了
        project_status.overall_status = PhaseStatus.COMPLETED
        self._print_success_summary(project_status)

        return project_status

    def _initialize_phases(self, subject: str) -> List:
        """
        全フェーズのインスタンスを作成

        Args:
            subject: 偉人名

        Returns:
            Phaseインスタンスのリスト
        """
        working_dir = self.config.get_path("working_dir") / subject

        return [
            Phase01Script(subject=subject, config=self.config, logger=self.logger, genre=self.genre),
            Phase02Audio(subject=subject, config=self.config, logger=self.logger, audio_var=self.audio_var),
            Phase03Images(subject=subject, config=self.config, logger=self.logger, genre=self.genre),
            Phase04Animation(subject=subject, config=self.config, logger=self.logger),
            Phase05BGM(subject=subject, config=self.config, logger=self.logger),
            Phase06Subtitles(subject=subject, config=self.config, logger=self.logger),
            Phase07Composition(subject=subject, config=self.config, logger=self.logger),
            Phase08Thumbnail(subject=subject, config=self.config, logger=self.logger, genre=self.genre, text_layout=self.text_layout, style=self.thumbnail_style),
            Phase09YouTube(subject=subject, config=self.config, logger=self.logger),
        ]

    def _print_success_summary(self, status: ProjectStatus):
        """成功サマリーを表示"""
        self.console.print("\n" + "="*60)
        self.console.print("[bold green]✅ 動画生成完了[/bold green]")
        self.console.print("="*60)

        self.console.print(f"\n[bold]偉人:[/bold] {status.subject}")

        # 各フェーズの状態
        self.console.print("\n[bold]Phase 実行状況:[/bold]")
        for phase in status.phases:
            status_emoji = {
                PhaseStatus.COMPLETED: "✅",
                PhaseStatus.SKIPPED: "⏭️",
                PhaseStatus.FAILED: "❌"
            }
            emoji = status_emoji.get(phase.status, "")
            duration = phase.duration_seconds if phase.duration_seconds else 0.0
            self.console.print(
                f"  {emoji} Phase {phase.phase_number}: {phase.phase_name} "
                f"({duration:.1f}s)"
            )

        # 出力ファイル
        self.console.print("\n[bold]出力ファイル:[/bold]")
        output_dir = self.config.get_path("output_dir")
        video_path = output_dir / "videos" / f"{status.subject}.mp4"

        # Phase 8のAI生成サムネイルをチェック（優先）
        working_dir = self.config.get_working_dir(status.subject)
        phase8_thumbnail_dir = working_dir / "08_thumbnail" / "thumbnails"
        phase8_thumbnails = list(phase8_thumbnail_dir.glob("*.png")) if phase8_thumbnail_dir.exists() else []

        # Phase 7の簡易サムネイルをチェック（フォールバック）
        phase7_thumbnail = working_dir / "07_composition" / f"{status.subject}_thumbnail.jpg"

        if video_path.exists():
            self.console.print(f"  📹 動画: {video_path}")

        if phase8_thumbnails:
            self.console.print(f"  🖼️  サムネイル (Phase 8): {phase8_thumbnail_dir} ({len(phase8_thumbnails)} files)")
        elif phase7_thumbnail.exists():
            self.console.print(f"  🖼️  サムネイル (Phase 7): {phase7_thumbnail}")

        self.console.print()

    def _print_error_summary(self, status: ProjectStatus):
        """エラーサマリーを表示"""
        self.console.print("\n" + "="*60)
        self.console.print("[bold red]❌ 動画生成失敗[/bold red]")
        self.console.print("="*60)

        # 失敗したフェーズを特定
        failed_phase = next(
            (p for p in status.phases if p.status == PhaseStatus.FAILED),
            None
        )

        if failed_phase:
            self.console.print(f"\n[bold]失敗したフェーズ:[/bold]")
            self.console.print(f"  Phase {failed_phase.phase_number}: {failed_phase.phase_name}")
            self.console.print(f"\n[bold]エラー内容:[/bold]")
            self.console.print(f"  {failed_phase.error_message}")

        self.console.print()
