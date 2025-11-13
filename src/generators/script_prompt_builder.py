"""
台本生成プロンプトの構築
"""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from typing import Dict, Any


class ScriptPromptBuilder:
    """台本生成プロンプトを構築"""

    def __init__(self, template_path: Path):
        """
        Args:
            template_path: Jinjaテンプレートファイルのパス
        """
        self.template_dir = template_path.parent
        self.template_name = template_path.name

        # Jinja環境を作成
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )

    def build(self, subject: str, variables: Dict[str, Any] = None) -> str:
        """
        プロンプトを構築

        Args:
            subject: 偉人名
            variables: テンプレートに渡す追加変数

        Returns:
            完成したプロンプト文字列
        """
        template = self.env.get_template(self.template_name)

        # テンプレート変数を準備
        context = {
            "subject": subject,
            **(variables or {})
        }

        # レンダリング
        prompt = template.render(**context)

        return prompt
