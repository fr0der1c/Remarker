import datetime
import html
import json
import sys
import uuid

import logbook
from evernote.api.client import EvernoteClient
from evernote.edam.error.ttypes import EDAMNotFoundException, EDAMUserException
from evernote.edam.type.ttypes import Note
from flask import Flask, redirect, request, session, url_for
from pymongo import MongoClient
from raven.contrib.flask import Sentry
from raven.handlers.logbook import SentryHandler

from remarker.config import get_config

COL_REQUEST_TOKENS = 'evernote_request_tokens'
COL_ACCESS_TOKENS = 'evernote_access_tokens'

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
        __app.mongo = MongoClient(**__app.config['MONGODB'])
        print('Added mongo to Flask object.')
except ModuleNotFoundError:
    pass


def evernote_authorize_content():
    client = EvernoteClient(
            consumer_key=__app.config['EVERNOTE_CONSUMER_KEY'],
            consumer_secret=__app.config['EVERNOTE_CONSUMER_SECRET'],
            sandbox=True
    )
    request_token = client.get_request_token(url_for('evernote_callback', _external=True))
    auth_url = client.get_authorize_url(request_token)

    db = get_db()
    request_token.update({'create_time': datetime.datetime.now()})
    db.get_collection(COL_REQUEST_TOKENS).insert(request_token)

    content = f"""
    <script>window.parent.postMessage(
    {{status: "302", 
     content: "\\<script\\>window.open(\\"{auth_url}\\", \\"newwindow\\", \\"height=800, width=800\\"); \\</script\\>" 
    }}, "*");
    </script>
    """
    return content


def create_note(auth_token, note_store, note_title, note_body, note_tags, parentNotebook=None):
    body = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
    body += "<!DOCTYPE en-note SYSTEM \"http://xml.evernote.com/pub/enml2.dtd\">"
    body += "<en-note>%s</en-note>" % note_body

    print(body)

    # Create note object
    note = Note()
    note.title = note_title
    note.content = body
    note.tagNames = note_tags

    # parentNotebook is optional; if omitted, default notebook is used
    if parentNotebook and hasattr(parentNotebook, 'guid'):
        note.notebookGuid = parentNotebook.guid

    # Attempt to create note in Evernote account
    note = note_store.createNote(auth_token, note)
    return note


def get_db():
    return __app.mongo.get_database(__app.config['MONGODB_DB'])


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

    @app.route('/notes/sync', methods=['POST'])
    def sync():
        if not session.get('client_id', None):
            session['client_id'] = uuid.uuid4()
            return evernote_authorize_content(), 302

        # get access token from database
        db = get_db()
        record = db.get_collection(COL_ACCESS_TOKENS).find_one({'client_id': session['client_id']})

        if not record:
            return evernote_authorize_content(), 302

        note_html_content = html.unescape(request.form.get('note[content]'))
        from enml_parser import ENMLParser
        enml_parse_result = ENMLParser(note_html_content).parse().decode('utf-8')

        note_title = request.form.get('note[title]')
        if not note_title:
            note_title = "无标题文档"

        note_url = request.form.get('note[url]')
        note_tags = json.loads(request.form.get('note[tags]'))
        note_words = request.form.get('note[words]')

        evernote_client = EvernoteClient(token=record['access_token'])

        try:
            create_note(auth_token=record['access_token'],
                        note_store=evernote_client.get_note_store(),
                        note_title=note_title,
                        note_body=enml_parse_result,
                        note_tags=note_tags)
        except EDAMUserException as edue:
            # Something was wrong with the note data
            # See EDAMErrorCode enumeration for error code explanation
            # http://dev.yinxiang.com/documentation/reference/Errors.html#Enum_EDAMErrorCode
            logger.error(edue)
            err_string = str(edue).replace('"', '\\"')
            return f'<script> window.parent.postMessage({{ status: "500", content: "{err_string}" }},"*"); </script>'
        except EDAMNotFoundException as ednfe:
            # Parent Notebook GUID doesn't correspond to an actual notebook
            logger.error(ednfe)
            err_string = str(ednfe).replace('"', '\\"')
            return f'<script> window.parent.postMessage({{ status: "500", content: "{err_string}" }},"*"); </script>'
        else:
            return '<script> window.parent.postMessage({ status: "200" },"*"); </script>'  # save successfully

    @app.route('/evernote_callback')
    def evernote_callback():
        oauth_token, oauth_verifier, sandbox_lnb = map(request.args.get, ['oauth_token',
                                                                          'oauth_verifier',
                                                                          'sandbox_lnb'])
        if not oauth_token or not sandbox_lnb:
            return '无效请求'
        if not oauth_verifier:
            return '您没有同意我们访问您的 Evernote 账户，授权失败。'
        else:
            if not session.get('client_id', None):
                return 'cookie 不正确'

            db = get_db()
            request_tokens = db.get_collection(COL_REQUEST_TOKENS).find_one({'oauth_token': oauth_token})

            client = EvernoteClient(
                    consumer_key=app.config['EVERNOTE_CONSUMER_KEY'],
                    consumer_secret=app.config['EVERNOTE_CONSUMER_SECRET'],
                    sandbox=True
            )
            access_token = client.get_access_token(
                    oauth_token,
                    request_tokens['oauth_token_secret'],
                    oauth_verifier
            )

            # save access token to database
            db.get_collection(COL_ACCESS_TOKENS).update_one({'client_id': session['client_id']},
                                                            {'$set': {'auth_time'   : datetime.datetime.now(),
                                                                      'access_token': access_token,
                                                                      'sandbox_lnb' : sandbox_lnb}},
                                                            upsert=True)

            return 'Evernote 授权成功，您可以关闭此页面并再次点击保存按钮。'

    @app.route('/')
    def main_page():
        return redirect("https://github.com/fr0der1c/Remarker", code=302)

    @app.route('/clear_cookie')
    def clear_cookie():
        if session.get('client_id', None):
            del session['client_id']
            return 'Delete success'
        return 'No need to delete'

    global __app
    __app = app

    return app
