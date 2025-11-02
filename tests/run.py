from pathlib import Path
from dotenv import load_dotenv
load_dotenv('config/.env')
from src.phases.phase_03_images import Phase03Images
from src.core.config_manager import ConfigManager
from src.utils.logger import setup_logger
config = ConfigManager()
logger = setup_logger('phase_03', Path('logs'))
phase = Phase03Images('織田信長', config, logger)
result = phase.run()
print(f'結果: {result.status}')
