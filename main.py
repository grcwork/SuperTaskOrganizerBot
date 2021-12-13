import queue
from threading import local
from telegram.ext import Updater, CallbackContext, CommandHandler, CallbackQueryHandler, ConversationHandler, Filters, JobQueue
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv, find_dotenv
import logging
import os
import firebase_admin
from firebase_admin import firestore
from zoneinfo import ZoneInfo
import json
import time
from telegram.ext.messagehandler import MessageHandler

# Variables para la conversación donde se crea una nueva tarea
LIST, TITLE, DESCRIPTION, REMINDER_TIME = range(4)

# Variables para la conversación que elimina una tarea existente
LIST_TO_SEARCH, TASK_TO_DELETE = range(2)

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

#Función para mostrar comandos y su funcionalidad
def help(update: Update, context: CallbackContext):
    context.bot.send_message(
        chat_id=update.effective_chat.id, text="Lista de comandos y sus funcionalidades: \n /lists -> permite ver las listas y tareas disponibles \n /newlist -> permite crear una lista nueva \n /newtask permite crear una tarea nueva \n /help -> permite obtener ayuda sobre el funcionamiento del bot"
    )


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

# Crear lista de tareas nueva
def create_new_list(update: Update, context: CallbackContext):
    # Datos de la nueva lista
    new_list = { "title": context.args[0], "telegram_user_id": update.effective_message.from_user.id }

    # Petición a la BD para crear la lista
    db.collection(u'lists').add(new_list)

    # Mensaje de confirmación
    context.bot.send_message(
        chat_id=update.effective_chat.id, text="¡Lista creada!")

def create_new_task(update: Update, context: CallbackContext):
    # Vamos a buscar las listas del usuario a la BD
    docs = db.collection(u'lists').where(
        u'telegram_user_id', u'==', update.effective_message.from_user.id).stream()

    # Convertimos los datos al formato [ [index, title, list_id], ... ]
    user_lists = []
    index = 1
    for doc in docs:
        data = doc.to_dict()
        user_lists.append([index, data["title"], doc.id])
        index+=1

    # Mensaje a imprimir (se imprimen las listas del usuario)
    text = "Ingresa el número de la lista a la que le quieres agregar una tarea\n\n"
    for item in user_lists:
        text += "*" + str(item[0]) + ". " + "*" + item[1] + "\n"

    # Guardamos el identificador del usuario
    context.user_data["telegram_user_id"] = update.effective_message.from_user.id

    # Guardamos las listas del usuario
    context.user_data["user_lists"] = user_lists

    context.bot.send_message(
        chat_id=update.effective_chat.id, text=text, parse_mode="Markdown")

    return LIST

def task_list(update: Update, context: CallbackContext):
    # Buscamos a qué identificador de lista pertenece el índice ingresado por el usuario
    user_lists =  context.user_data["user_lists"]
    list_id = None
    for item in user_lists:
        if item[0] == int(update.message.text):
            list_id = item[2]

    # Guardamos el índice de la lista a la cual se le quiere agregar una tarea
    context.user_data["list_id"] = list_id

    context.bot.send_message(
        chat_id=update.effective_chat.id, text="Ingresa el título de la nueva tarea")
    return TITLE

def task_title(update: Update, context: CallbackContext):
    # Guardamos el título de la nueva tarea
    context.user_data["title"] = update.message.text

    context.bot.send_message(
        chat_id=update.effective_chat.id, text="Ingresa la descripción de la nueva tarea")

    return DESCRIPTION

def task_description(update: Update, context: CallbackContext):
   # Guardamos la descripción de la nueva tarea
    context.user_data["description"] = update.message.text

    context.bot.send_message(
        chat_id=update.effective_chat.id, text="Ingresa fecha y hora del recordatorio, formato DD/MM/AAAA HH:MM (24h)")
    
    return REMINDER_TIME

def task_reminder_time(update: Update, context: CallbackContext):
    # Obtenemos el string del reminder time y lo convertimos a timestamp
    reminder_time_string = update.message.text
    # TODO: La hora debería codificarse en base al timezone del usuario, por ahora se usa el timezone America/Santiago
    reminder_time_timestamp = datetime.datetime.strptime(reminder_time_string + " -0300", "%d/%m/%Y %H:%M %z")

    # Guardamos el timestamp del recordatorio de la nueva tarea
    context.user_data["reminder_time"] = reminder_time_timestamp

    new_task = { 
        "title":  context.user_data["title"], 
        "description": context.user_data["description"],
        "reminder_time": context.user_data["reminder_time"],
        "telegram_user_id": context.user_data["telegram_user_id"],
        "list_id": context.user_data["list_id"],
    }

    # Petición a la BD para crear la tarea
    db.collection(u'tasks').add(new_task)

    return ConversationHandler.END

def delete_task(update: Update, context: CallbackContext):
    # Vamos a buscar las listas del usuario a la BD
    docs = db.collection(u'lists').where(
        u'telegram_user_id', u'==', update.effective_message.from_user.id).stream()

    # Convertimos los datos al formato [ [index, title, list_id], ... ]
    user_lists = []
    index = 1
    for doc in docs:
        data = doc.to_dict()
        user_lists.append([index, data["title"], doc.id])
        index+=1

    # Mensaje a imprimir (se imprimen las listas del usuario)
    text = "Ingresa el número de la lista de la que quieres eliminar una tarea\n\n"
    for item in user_lists:
        text += "*" + str(item[0]) + ". " + "*" + item[1] + "\n"

    # Guardamos las listas del usuario
    context.user_data["user_lists"] = user_lists

    context.bot.send_message(
        chat_id=update.effective_chat.id, text=text, parse_mode="Markdown")

    return LIST_TO_SEARCH

def lists_to_search(update: Update, context: CallbackContext):
    # Buscamos a qué identificador de lista pertenece el índice ingresado por el usuario
    user_lists =  context.user_data["user_lists"]
    list_id = None
    for item in user_lists:
        if item[0] == int(update.message.text):
            list_id = item[2]

    # Buscar y desplegar las tareas asociadas a la lista seleccionada por el usuario
    docs = db.collection(u'tasks').where(
        u'list_id', u'==', list_id).stream()
    
    # Nombre de la lista
    list_doc = db.collection(u'lists').document(list_id).get()
    list_data = list_doc.to_dict()

    tasks = []
    response = ""
    index = 1
    for doc in docs:
        data = doc.to_dict()

        # Lista para posteriormente buscar el identificador de la que selecionó el usuario
        tasks.append([index, data["title"], doc.id])

        # TODO: La hora debería cambiar en base al timezone del usuario, por ahora se usa el timezone America/Santiago
        time_america_santiago = data["reminder_time"].astimezone(ZoneInfo("America/Santiago"))
        if response == "":
            response = "*" + str(index) + ". " + data["title"] + "*" + " | "+ time_america_santiago.strftime("%d/%m/%Y, %H:%M") + "\n\t\t\t\t" + "_" + data["description"] + "_"
            index += 1
        else:
            response = response + "\n" + "*" + str(index) + ". " + data["title"] + "*" + " | " + time_america_santiago.strftime("%d/%m/%Y, %H:%M") + "\n\t\t\t\t" + "_" + data["description"] + "_"
            index += 1
    
    response = "Ingresa el número de la tarea que quieres eliminar" + "\n\n" + list_data["title"] + "\n\n" + response

    # Guardamos las tareas del usuario (tareas asociadas a la lista que previamente selecionó)
    context.user_data["tasks"] = tasks

    context.bot.send_message(chat_id=update.effective_chat.id, text=response, parse_mode="Markdown")

    return TASK_TO_DELETE

def task_to_delete(update: Update, context: CallbackContext):
   # Buscamos a qué identificador de tarea pertenece el índice ingresado por el usuario
    tasks =  context.user_data["tasks"]
    task_id = None
    for item in tasks:
        if item[0] == int(update.message.text):
            task_id = item[2]
    
    # Eliminar la tarea que el usuario selecionó
    db.collection(u'tasks').document(task_id).delete()

    return ConversationHandler.END

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

# Se registra un CommandHandler para el comando /help
help_handler = CommandHandler('help', help)
dispatcher.add_handler(help_handler)

# Se registra un CommandHandler para el comando /lists
lists_handler = CommandHandler('lists', display_lists)
dispatcher.add_handler(lists_handler)

# Se registra un CallbackQueryHandler para los botones
button_handler = CallbackQueryHandler(button)
dispatcher.add_handler(button_handler)

# Se registra un CommandHandler para el comando /newlist
new_list_handler = CommandHandler('newlist', create_new_list)
dispatcher.add_handler(new_list_handler)

# Nueva conversación para agregar una nueva tarea
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('newtask', create_new_task)],
    states= {
        LIST: [MessageHandler(Filters.text & ~Filters.command, task_list)],
        TITLE: [MessageHandler(Filters.text & ~Filters.command, task_title)],
        DESCRIPTION: [MessageHandler(Filters.text & ~Filters.command, task_description)],
        REMINDER_TIME: [MessageHandler(Filters.text & ~Filters.command, task_reminder_time)]
    },
    fallbacks=[]
)
dispatcher.add_handler(conv_handler)

# Nueva conversación para eliminar una tarea existente
conv_handler2 = ConversationHandler(
    entry_points=[CommandHandler('deletetask', delete_task)],
    states={
        LIST_TO_SEARCH: [MessageHandler(Filters.text & ~Filters.command, lists_to_search)],
        TASK_TO_DELETE: [MessageHandler(Filters.text & ~Filters.command, task_to_delete)]
    },
    fallbacks=[]
)
dispatcher.add_handler(conv_handler2)

# Se empiezan a traer updates desde Telegram
updater.start_polling()

updater.job_queue.run_once(set_up_reminders, when=1)

# Para escuchar por señales, por ejemplo CTRL + C
updater.idle()
