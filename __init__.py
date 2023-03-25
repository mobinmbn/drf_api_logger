import os
from drf_api_logger.events import Events

if os.environ.get('RUN_MAIN', None) != 'true':
    default_app_config = 'logs.apps.LogsConfig'

API_LOGGER_SIGNAL = Events()
