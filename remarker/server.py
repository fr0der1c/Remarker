import sys

import logbook
from flask import Flask
from raven.contrib.flask import Sentry
from raven.handlers.logbook import SentryHandler

from remarker.config import get_config

LOG_FORMAT_STRING = '[{record.time:%Y-%m-%d %H:%M:%S}] [{record.module}] ' \
                    '[{record.level_name}]: {record.message}'

logger = logbook.Logger(__name__)
sentry = Sentry()
__app = None

try:
    import uwsgidecorators

    @uwsgidecorators.postfork
    def init_log_handlers():
        global __app

        # Sentry
        if __app.config['CONFIG_NAME'] in __app.config['SENTRY_AVAILABLE_IN']:
            sentry.init_app(app=__app)
            sentry_handler = SentryHandler(sentry.client, level='WARNING')  # Sentry 只处理 WARNING 以上的
            logger.handlers.append(sentry_handler)


    @uwsgidecorators.postfork
    def init_db():
        import remarker.db

        global __app
        remarker.db.init_pool(__app)
except ModuleNotFoundError:
    pass


def create_app() -> Flask:
    app = Flask(__name__)

    app.config.from_object(get_config())

    if app.config['CONFIG_NAME'] in app.config['DEBUG_LOG_AVAILABLE_IN']:
        stdout_handler = logbook.StreamHandler(stream=sys.stdout, bubble=True, filter=lambda r, h: r.level < 13)
    else:
        # ignore debug when not in debug
        stdout_handler = logbook.StreamHandler(stream=sys.stdout, bubble=True, filter=lambda r, h: 10 < r.level < 13)
    stdout_handler.format_string = LOG_FORMAT_STRING
    logger.handlers.append(stdout_handler)

    stderr_handler = logbook.StreamHandler(stream=sys.stderr, bubble=True, level='WARNING')
    stderr_handler.format_string = LOG_FORMAT_STRING
    logger.handlers.append(stderr_handler)

    print('Creating app...')

    from remarker.views import main_blueprint
    app.register_blueprint(main_blueprint)

    global __app
    __app = app

    return app
