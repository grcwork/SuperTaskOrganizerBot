from telegram.ext import Updater, CallbackContext, CommandHandler
from telegram import Update
from dotenv import load_dotenv, find_dotenv
import logging
import os
import firebase_admin
from firebase_admin import firestore
import json

#Se cargan todas las variables encontradas en el archivo .env como variables de ambiente,
#en específico se carga la variable TELEGRAM_TOKEN la cual contiene el token del bot
load_dotenv(find_dotenv())

#Iniciar conección con Firebase
default_app = firebase_admin.initialize_app(options={'storageBucket': 'gs://supertaskorganizerbot.appspot.com'})

#Crear un cliente para interactuar con la base de datos
db = firestore.client()

#Configuración básica del sistema de logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

#Creación de un objeto Updater, se carga el token del bot desde las variables de ambiente
updater = Updater(token=os.environ.get("TELEGRAM_TOKEN"), use_context=True)

#Creación de variable para acceso más sencillo al Dispacher usado por el Updater
dispatcher = updater.dispatcher

#Función para procesar un tipo específico de update
def start(update: Update, context: CallbackContext):
    logging.info(f"User name: {update.effective_message.from_user.first_name}, User id: {update.effective_message.from_user.id}")
    context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

#Se registra un CommandHandler para el comando /start
start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

#Se empiezan a traer updates desde Telegram
updater.start_polling()

#Para escuchar por señales, por ejemplo CTRL + C
updater.idle()