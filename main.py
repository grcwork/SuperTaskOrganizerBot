import queue
from threading import local
from telegram.ext import Updater, CallbackContext, CommandHandler, CallbackQueryHandler, JobQueue
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv, find_dotenv
import logging
import os
import firebase_admin
from firebase_admin import firestore
from zoneinfo import ZoneInfo
import json
import pytz, datetime
#from google.api_core.datetime_helpers import DatetimeWithNanoseconds

# Se cargan todas las variables encontradas en el archivo .env como variables de ambiente,
# en específico se carga la variable TELEGRAM_TOKEN la cual contiene el token del bot
load_dotenv(find_dotenv())

# Iniciar conección con Firebase
default_app = firebase_admin.initialize_app(
    options={'storageBucket': 'gs://supertaskorganizerbot.appspot.com'})

# Crear un cliente para interactuar con la base de datos
db = firestore.client()

# Configuración básica del sistema de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Creación de un objeto Updater, se carga el token del bot desde las variables de ambiente
updater = Updater(token=os.environ.get("TELEGRAM_TOKEN"), use_context=True)

# Creación de variable para acceso más sencillo al Dispacher usado por el Updater
dispatcher = updater.dispatcher

# Función para procesar un tipo específico de update
def start(update: Update, context: CallbackContext):
    logging.info(
        f"User name: {update.effective_message.from_user.first_name}, User id: {update.effective_message.from_user.id}")
    context.bot.send_message(
        chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

# Desplegar al usuario las listas existentes
def display_lists(update: Update, context: CallbackContext):
    docs = db.collection(u'lists').where(
        u'telegram_user_id', u'==', update.effective_message.from_user.id).stream()

    keyboard = [[]]
    for doc in docs:
        data = doc.to_dict()
        keyboard[0].append(InlineKeyboardButton(
            data["title"], callback_data=doc.id))
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Your lists:', reply_markup=reply_markup)

def get_chat_id(update: Update, context: CallbackContext):
    chat_id = -1

    if update.message is not None:
        chat_id = update.message.chat.id
    elif update.callback_query is not None:
        chat_id = update.callback_query.message.chat.id
    elif update.poll is not None:
        chat_id = context.bot_data[update.poll.id]

    return chat_id

# Genera las tareas para enviar el recordatorio en la fecha adecuada
def set_up_reminders(context: CallbackContext):
    print("Generando tareas para recordatorios")

    # Revisar todas las tareas programadas
    tasks = db.collection(u'tasks').stream()
    #update.message.reply_text("Intentando crear recordatorios!")

    # Generar tareas
    for task in tasks:
        data = task.to_dict()

        # Datetime de google es con nanosegundos, quitarlos, y transformar a UTC, ya que el la jobqueue es complicado
        # con el tema de las timezones locales
        dt = datetime.datetime.fromtimestamp(data['reminder_time'].timestamp())
        dt_utc = dt.astimezone(pytz.utc)

        # Crear mensaje de recordatorio
        msg = "¡Recordatorio!\n" + data['title'] + "\n" + data['description'] + "\n\nEs ahora."
        # Crear tarea, con context [chat_id, msg]
        context.job_queue.run_once(lambda cb: send_reminder(cb), when=dt_utc, context=[int(data['telegram_user_id']), msg])

# Enviar recordatorio al chat especificado
def send_reminder(context: CallbackContext):
    context.bot.send_message(chat_id=context.job.context[0], text=context.job.context[1])
    

# Parses the CallbackQuery and updates the message text
def button(update: Update, context: CallbackContext) -> None:
    # Parses the CallbackQuery
    query = update.callback_query

    # CallbackQueries need to be answered
    query.answer()

    # Tareas asociadas a la lista seleccionada por el usuario
    docs = db.collection(u'tasks').where(
        u'list_id', u'==', query.data).stream()
    
    # Nombre de la lista
    list_doc = db.collection(u'lists').document(query.data).get()
    list_data = list_doc.to_dict()

    response = ""
    index = 1
    for doc in docs:
        data = doc.to_dict()
        # TODO: La hora debería cambiar en base al timezone del usuario, por ahora se usa el timezone America/Santiago
        time_america_santiago = data["reminder_time"].astimezone(ZoneInfo("America/Santiago"))
        if response == "":
            response = "*" + str(index) + ". " + data["title"] + "*" + " | "+ time_america_santiago.strftime("%d/%m/%Y, %H:%M") + "\n\t\t\t\t" + "_" + data["description"] + "_"
            index += 1
        else:
            response = response + "\n" + "*" + str(index) + ". " + data["title"] + "*" + " | " + time_america_santiago.strftime("%d/%m/%Y, %H:%M") + "\n\t\t\t\t" + "_" + data["description"] + "_"
            index += 1
    
    response = list_data["title"] + "\n\n" + response

    # Updates the message text
    query.edit_message_text(text=response, parse_mode="Markdown")

# Se registra un CommandHandler para el comando /start
start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

# Se registra un CommandHandler para el comando /lists
lists_handler = CommandHandler('lists', display_lists)
dispatcher.add_handler(lists_handler)

# Se registra un CallbackQueryHandler para los botones
button_handler = CallbackQueryHandler(button)
dispatcher.add_handler(button_handler)

# Se empiezan a traer updates desde Telegram
updater.start_polling()

updater.job_queue.run_once(set_up_reminders, when=1)

# Para escuchar por señales, por ejemplo CTRL + C
updater.idle()
