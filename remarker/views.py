import datetime
import html
import json
import uuid

from evernote.api.client import EvernoteClient
from evernote.edam.error.ttypes import EDAMNotFoundException, EDAMUserException
from evernote.edam.type.ttypes import Note
from flask import Blueprint, current_app, redirect, request, session, url_for

from remarker.db import get_connection
from remarker.server import logger

main_blueprint = Blueprint('main', __name__)

COL_REQUEST_TOKENS = 'evernote_request_tokens'
COL_ACCESS_TOKENS = 'evernote_access_tokens'


@main_blueprint.route('/notes/sync', methods=['POST'])
def sync():
    if not session.get('client_id', None):
        session['client_id'] = uuid.uuid4()
        return evernote_authorize_content(), 302

    # get access token from database
    db = get_connection()
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


@main_blueprint.route('/evernote_callback')
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

        db = get_connection()
        request_tokens = db.get_collection(COL_REQUEST_TOKENS).find_one({'oauth_token': oauth_token})

        client = EvernoteClient(
                consumer_key=current_app.config['EVERNOTE_CONSUMER_KEY'],
                consumer_secret=current_app.config['EVERNOTE_CONSUMER_SECRET'],
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


@main_blueprint.route('/')
def main_page():
    return redirect("https://github.com/fr0der1c/Remarker", code=302)


@main_blueprint.route('/clear_cookie')
def clear_cookie():
    if session.get('client_id', None):
        del session['client_id']
        return 'Delete success'
    return 'No need to delete'


def evernote_authorize_content():
    client = EvernoteClient(
            consumer_key=current_app.config['EVERNOTE_CONSUMER_KEY'],
            consumer_secret=current_app.config['EVERNOTE_CONSUMER_SECRET'],
            sandbox=True
    )
    request_token = client.get_request_token(url_for('main.evernote_callback', _external=True))
    auth_url = client.get_authorize_url(request_token)

    db = get_connection()
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

    logger.info(f"title: {note_title}")
    logger.info(f"body: {body}")

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
