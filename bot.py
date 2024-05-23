import json
import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from telegram.error import BadRequest, TelegramError

# Load configuration
try:
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    print("Configuration file not found.")
    exit(1)
except json.JSONDecodeError:
    print("Error decoding the configuration file.")
    exit(1)

TOKEN = config.get('TOKEN')
MIN_LENGTH = config.get('MIN_LENGTH', 10)
ON_DELETE_MESSAGE_REPLY = config.get('ON_DELETE_MESSAGE_REPLY', 'Your message was deleted because it did not meet the criteria.')
ADMIN_IDS = config.get('ADMIN_IDS', [])

# Load the list of words
def load_allowed_words():
    try:
        with open('bw_buildings.txt', 'r') as f:
            return set(word.strip().lower() for word in f.readlines() if word.strip())
    except FileNotFoundError:
        print("Words file not found.")
        exit(1)

allowed_words = load_allowed_words()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Function to notify admins
def notify_admins(context: CallbackContext, message: str) -> None:
    for admin_id in ADMIN_IDS:
        try:
            context.bot.send_message(chat_id=admin_id, text=message)
        except BadRequest as e:
            logger.error(f"Failed to send message to admin {admin_id}: {e}")
        except TelegramError as e:
            logger.error(f"Telegram error occurred: {e}")

# Define the command handler for start
def start(update: Update, context: CallbackContext) -> None:
    try:
        update.message.reply_text('Hello! I am your bot.')
    except TelegramError as e:
        logger.error(f"Error in start command: {e}")

# Define the command handler for adding a word
def add_word(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    logger.info(f"Admin IDs: {ADMIN_IDS}")
    logger.info(f"User ID: {user_id}")

    if user_id not in ADMIN_IDS:
        logger.warning(f"Unauthorized access attempt by user ID: {user_id}")
        update.message.reply_text('You are not authorized to use this command.')
        return

    try:
        word = context.args[0].strip().lower()
        if word:
            with open('bw_buildings.txt', 'a') as f:
                f.write(f"{word}\n")
            global allowed_words
            allowed_words = load_allowed_words()
            update.message.reply_text(f"The word '{word}' has been added to the list.")
            notify_admins(context, f"The word '{word}' was added by {update.message.from_user.username}.")
        else:
            update.message.reply_text('Please provide a valid word to add.')
    except IndexError:
        update.message.reply_text('Usage: /add <word>')
    except Exception as e:
        logger.error(f"Error in add_word command: {e}")
        update.message.reply_text('An error occurred while adding the word.')

# Define the command handler for listing words
def list_words(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text('You are not authorized to use this command.')
        return

    try:
        words_list = "\n".join(sorted(allowed_words))
        update.message.reply_text(f"Allowed words:\n{words_list}")
    except Exception as e:
        logger.error(f"Error in list_words command: {e}")
        update.message.reply_text('An error occurred while listing the words.')

# Define the command handler for deleting a word
def delete_word(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text('You are not authorized to use this command.')
        return

    try:
        word = context.args[0].strip().lower()
        if word in allowed_words:
            allowed_words.remove(word)
            with open('bw_buildings.txt', 'w') as f:
                for w in sorted(allowed_words):
                    f.write(f"{w}\n")
            update.message.reply_text(f"The word '{word}' has been removed from the list.")
            notify_admins(context, f"The word '{word}' was removed by {update.message.from_user.username}.")
        else:
            update.message.reply_text(f"The word '{word}' is not in the list.")
    except IndexError:
        update.message.reply_text('Usage: /delete <word>')
    except Exception as e:
        logger.error(f"Error in delete_word command: {e}")
        update.message.reply_text('An error occurred while deleting the word.')

# Define the message handler
def handle_message(update: Update, context: CallbackContext) -> None:
    message = update.message
    try:
        logger.info(f"Received message: {message.text}")
        if message.reply_to_message:
            logger.info("Message is a reply, ignoring.")
            return
        if len(message.text) < MIN_LENGTH:
            logger.info(f"Message is too short (length {len(message.text)}), ignoring.")
            return
        if not any(word in message.text.lower() for word in allowed_words):
            logger.info("No allowed words found in message, deleting.")
            context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
            context.bot.send_message(chat_id=message.chat_id, text=ON_DELETE_MESSAGE_REPLY)
            log_message = f"Deleted message from {message.from_user.username}: {message.text}"
            logger.info(log_message)
            notify_admins(context, log_message)
        else:
            logger.info("Message contains allowed words, not deleting.")
    except BadRequest as e:
        logger.error(f"Failed to handle message: {e}")
    except TelegramError as e:
        logger.error(f"Telegram error occurred: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

def main() -> None:
    try:
        updater = Updater(TOKEN)
        dispatcher = updater.dispatcher

        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("add", add_word))
        dispatcher.add_handler(CommandHandler("list_words", list_words))
        dispatcher.add_handler(CommandHandler("delete_word", delete_word))
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

        updater.start_polling()
        updater.idle()
    except TelegramError as e:
        logger.error(f"Telegram error occurred in main: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")

if __name__ == '__main__':
    main()
