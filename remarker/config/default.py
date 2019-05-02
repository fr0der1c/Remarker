class Config:
    DEBUG = False
    SECRET_KEY = '123123'

    EVERNOTE_CONSUMER_KEY = 'test'
    EVERNOTE_CONSUMER_SECRET = 'some-secret'

    MONGODB = {
        'host'              : '127.0.0.1',
        'port'              : 27017,
        'uuidRepresentation': 'standard'
    }
    MONGODB_DB = 'remarker'

    SENTRY_CONFIG = {
        'dsn'    : '',
        'release': '',
        'tags'   : {'environment': 'default'}
    }

    PRODUCTION_SECURE_FIELDS = ['SECRET_KEY', 'EVERNOTE_CONSUMER_KEY', 'EVERNOTE_CONSUMER_SECRET']
    PRODUCTION_OVERWRITE_FIELDS = ['SECRET_KEY', 'EVERNOTE_CONSUMER_KEY', 'EVERNOTE_CONSUMER_SECRET']

    SENTRY_AVAILABLE_IN = ('production', 'staging', 'testing', 'development')
    DEBUG_LOG_AVAILABLE_IN = ('development', 'testing', 'staging')
