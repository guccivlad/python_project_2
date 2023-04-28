from __future__ import print_function

import logging
import os.path
import io
import google.auth
import pickle
import numpy as np
import requests

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

from dotenv import dotenv_values
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

'''
TODO:
-- add restrictions on the size of the uploaded file
-- in download func: show candidates to download(with different extension)
-- ability to upload .jpg and other(maybe)
-- BotFather: add inline help for command
'''

#last command
last_command = [' ']

#len of comand
download_comand_len = len('/download ')
upload_comand_len = len('/upload')

config = dotenv_values(".env")
allowed_extensions = ['pdf', 'jpg']
MimeTypes = ['application/pdf', 'image/jpeg']
folder_id = '1_dMZ7eMrTfECHJ3W6N4owefXNqYaGpmM'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def Create_Service(client_secret_file, api_name, api_version, *scopes):
    print(client_secret_file, api_name, api_version, scopes, sep='-')
    CLIENT_SECRET_FILE = client_secret_file
    API_SERVICE_NAME = api_name
    API_VERSION = api_version
    SCOPES = [scope for scope in scopes[0]]
    print(SCOPES)

    cred = None

    pickle_file = f'token_{API_SERVICE_NAME}_{API_VERSION}.pickle'
    # print(pickle_file)

    if os.path.exists(pickle_file):
        with open(pickle_file, 'rb') as token:
            cred = pickle.load(token)

    if not cred or not cred.valid:
        if cred and cred.expired and cred.refresh_token:
            cred.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            cred = flow.run_local_server()

        with open(pickle_file, 'wb') as token:
            pickle.dump(cred, token)

    try:
        service = build(API_SERVICE_NAME, API_VERSION, credentials=cred)
        print(API_SERVICE_NAME, 'service created successfully')
        return service
    except Exception as e:
        print('Unable to connect.')
        print(e)
        return None

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = open('./server/help_list.txt')
    help_text = file.read()
    await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    last_command[0] = text
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f'Hello {update.effective_user.first_name}, this is a bot for working with Google drive. For more information, write /help.')

async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    last_command[0] = text
    await update.message.reply_text(f'Hello {update.effective_user.first_name}')

async def show_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows basic usage of the Drive v3 API.
    Prints the names of files the user has access to.
    """
    text = update.message.text
    last_command[0] = text
    files = search_file()
    for name in files:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=name)

def download_file(real_file_id, file_name):
    """Downloads a file
    Args:
        real_file_id: ID of the file to download
        file_name: name of download file
    """

    CLIENT_SECRET_FILE = 'credentials.json'
    API_NAME = 'drive'
    API_VERSION = 'v3'
    SCOPES = ['https://www.googleapis.com/auth/drive']

    write_file_name = 'book.pdf'

    try:
        service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES)

        file_id = real_file_id

        # pylint: disable=maybe-no-member
        request = service.files().get_media(fileId=file_id)
        file = io.BytesIO()
        downloader = MediaIoBaseDownload(file, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            print(F'Download {int(status.progress() * 100)}.')

        file.seek(0)

        with open(os.path.join('./server', write_file_name), 'wb') as f:
            f.write(file.read())
            os.rename(os.path.join('./server', write_file_name), os.path.join('./server', file_name))
            f.close()

    except HttpError as error:
        print(F'An error occurred: {error}')
        file = None

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    last_command[0] = text
    input_name = text[download_comand_len : ]
    files_list = search_file()
    for name in files_list:
        if(input_name in name):
            file_id = files_list[name]
            file_name = name
            break

    download_file(file_id, file_name)
    await context.bot.send_document(chat_id=update.effective_chat.id, document=open(f'./server/{file_name}', 'rb'))

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    last_command[0] = text
    file_name = text[8 :]
    print(file_name)
    files = search_file()
    if(file_name in files):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Yep, the file exists!")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="The file does not exist.")

def upload_file(file_name, extension):
    CLIENT_SECRET_FILE = 'credentials.json'
    API_NAME = 'drive'
    API_VERSION = 'v3'
    SCOPES = ['https://www.googleapis.com/auth/drive']

    is_download = False

    try:
        service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES)

        mime_type = ''
        file_metadate = {}

        if(extension == '.pdf'):
            mime_type = 'application/pdf'
        if(extension == '.jpg'):
            mime_type = 'image/jpeg'

        file_metadate = {
                'name': file_name,
                'parents': [folder_id]
            }

        if(mime_type in MimeTypes):
            media = MediaFileUpload(os.path.join('./server/users', file_name), mimetype=mime_type)
            service.files().create(body = file_metadate, media_body = media, fields = 'id').execute()
            is_download = True

    except HttpError as error:
        print(F'An error occurred: {error}')

    return is_download

async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    last_command[0] = text
    if(last_command[0][:upload_comand_len] == '/upload' and len(last_command[0]) > upload_comand_len):
        await context.bot.send_message(chat_id=update.effective_chat.id, text='Upload your file:')
    else:
        error_text = 'Something went wrong. Perhaps you forgot to write the file name?'
        await context.bot.send_message(chat_id=update.effective_chat.id, text=error_text)

async def file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    write_file_name = 'file.pdf'

    file_id = update.message.document.file_id
    file = await context.bot.get_file(file_id)
    filename, extension = os.path.splitext(file.file_path)
    print(file)

    await file.download_to_drive('book')
    if(last_command[0][:upload_comand_len] == '/upload' and len(last_command[0]) > upload_comand_len):
        file_name = last_command[0][upload_comand_len + 1 :] + extension
        URL = file.file_path
        response = requests.get(URL)
        with open(os.path.join('./server/users', write_file_name), 'wb') as f:
            f.write(response.content)
            os.rename(os.path.join('./server/users', write_file_name), os.path.join('./server/users', file_name))
            f.close()
        is_download = upload_file(file_name, extension)
        if(is_download):
            await context.bot.send_message(chat_id=update.effective_chat.id, text='Your book is uploaded')
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text='Something went wrong!')
    
    last_command[0] = ' '

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    write_file_name = 'photo.jpg'

    photo_file = await update.message.photo[-1].get_file()
    await photo_file.download_to_drive("user_photo.jpg")
    filename, extension = os.path.splitext(photo_file.file_path)

    if(last_command[0][:upload_comand_len] == '/upload' and len(last_command[0]) > upload_comand_len):
        file_name = last_command[0][upload_comand_len + 1 :] + extension
        URL = photo_file.file_path
        response = requests.get(URL)
        with open(os.path.join('./server/users', write_file_name), 'wb') as f:
            f.write(response.content)
            os.rename(os.path.join('./server/users', write_file_name), os.path.join('./server/users', file_name))
            f.close()
        is_download = upload_file(file_name, extension)
        if(is_download):
            await context.bot.send_message(chat_id=update.effective_chat.id, text='Your photo is uploaded')
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text='Something went wrong!')
    
    last_command[0] = ' '

def search_file():
    """Search file in drive location

    Load pre-authorized user credentials from the environment.
    TODO(developer) - See https://developers.google.com/identity
    for guides on implementing OAuth2 for the application.
    """

    CLIENT_SECRET_FILE = 'credentials.json'
    API_NAME = 'drive'
    API_VERSION = 'v3'
    SCOPES = ['https://www.googleapis.com/auth/drive']

    try:
        # create drive api client
        service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES)

        files = []
        files_dict = {}
        page_token = None
        query = f"parents = '{folder_id}'"
        
        while True:
            # pylint: disable=maybe-no-member
            response = service.files().list(q=query,).execute()
            for file in response.get('files', []):
                # Process change
                files_dict[file.get('name')] = file.get('id')
            files.extend(response.get('files', []))
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break

    except HttpError as error:
        print(F'An error occurred: {error}')
        files = None

    return files_dict



if __name__ == '__main__':
    application = ApplicationBuilder().token(config['TOKEN']).build()
    
    start_handler = CommandHandler('start', start)
    hello_handler = CommandHandler('hello', hello)
    help_handler = CommandHandler('help', help)
    show_files_handler = CommandHandler('show_files', show_files)
    download_handler = CommandHandler('download', download)
    search_handler = CommandHandler('search', search)
    upload_handler = CommandHandler('upload', upload)

    application.add_handler(start_handler)
    application.add_handler(hello_handler)
    application.add_handler(help_handler)
    application.add_handler(show_files_handler)
    application.add_handler(download_handler)
    application.add_handler(search_handler)
    application.add_handler(upload_handler)
    application.add_handler(MessageHandler(filters.Document.PDF, file))
    application.add_handler(MessageHandler(filters.PHOTO, photo))
    
    application.run_polling()
