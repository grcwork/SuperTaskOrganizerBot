from telegram.ext import Updater, CallbackContext, CommandHandler
from telegram import Update, chat
from dotenv import load_dotenv, find_dotenv
import logging
import os

load_dotenv(find_dotenv())

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

updater = Updater(token=os.environ.get("TELEGRAM_TOKEN"), use_context=True)
dispatcher = updater.dispatcher

def start(update: Update, context: CallbackContext):
    logging.info(f"User name: {update.effective_message.from_user.first_name}, User id: {update.effective_message.from_user.id}")
    context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)
updater.start_polling()
updater.idle()