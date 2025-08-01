import asyncio
import logging
import sys
import base64
import json
import requests
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import aiohttp

# Загружаем переменные окружения
load_dotenv()

# Конфигурация из переменных окружения
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
API_KEY = os.getenv('BODYGRAM_API_KEY')
ORG_ID = os.getenv('BODYGRAM_ORG_ID')
API_URL = os.getenv('BODYGRAM_API_URL', f"https://platform.bodygram.com/api/orgs/{ORG_ID}/scans")

# Настройки бота
BOT_NAME = os.getenv('BOT_NAME', 'SENS Fit Bot')
BOT_DESCRIPTION = os.getenv('BOT_DESCRIPTION', 'Telegram bot for SENS Fit bra size fitting')

# Контактная информация
SUPPORT_EMAIL = os.getenv('SUPPORT_EMAIL', 'support@sensfit.com')
PRIVACY_EMAIL = os.getenv('PRIVACY_EMAIL', 'privacy@sensfit.com')

# Ссылки на товары
WILDBERRIES_BASE_URL = os.getenv('WILDBERRIES_BASE_URL', 'https://www.wildberries.ru/catalog/')
OZON_BASE_URL = os.getenv('OZON_BASE_URL', 'https://www.ozon.ru/product/')

# Значения по умолчанию
DEFAULT_AGE = int(os.getenv('DEFAULT_AGE', '25'))
DEFAULT_WEIGHT = int(os.getenv('DEFAULT_WEIGHT', '60000'))
DEFAULT_GENDER = os.getenv('DEFAULT_GENDER', 'female')

# Проверяем обязательные переменные
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не установлен в .env файле")
if not API_KEY:
    raise ValueError("BODYGRAM_API_KEY не установлен в .env файле")
if not ORG_ID:
    raise ValueError("BODYGRAM_ORG_ID не установлен в .env файле")

# Состояния FSM
class UserStates(StatesGroup):
    waiting_for_consent = State()
    waiting_for_method = State()
    waiting_for_height = State()
    waiting_for_front_photo = State()
    waiting_for_profile_photo = State()
    # Новые состояния для квиза
    waiting_for_quiz_comfortable_bra = State()
    waiting_for_quiz_current_size = State()
    waiting_for_quiz_underbust = State()
    waiting_for_quiz_bust = State()
    waiting_for_quiz_breast_shape = State()
    waiting_for_quiz_bra_type = State()
    waiting_for_quiz_priority = State()
    waiting_for_quiz_skin_tone = State()
    waiting_for_quiz_calculate = State()
    waiting_for_feedback = State()

# Хранилище данных пользователей
user_data: Dict[int, Dict[str, Any]] = {}

# Создаем диспетчер с хранилищем состояний
dp = Dispatcher(storage=MemoryStorage())

def create_keyboard(*buttons: tuple[str, str]) -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопками"""
    keyboard = []
    for text, callback_data in buttons:
        keyboard.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# КОМАНДЫ (должны быть в начале, до других обработчиков)
@dp.message(Command("help"))
async def help_command(message: Message):
    """Команда помощи"""
    help_text = (
        f"🤖 {BOT_NAME} - подбор бюстгальтера\n\n"
        "Команды:\n"
        "/start - начать подбор размера\n"
        "/myfit - показать последнюю рекомендацию\n"
        "/reset - сбросить данные\n"
        "/privacy - политика конфиденциальности\n"
        "/help - эта справка"
    )
    await message.answer(help_text)

@dp.message(Command("myfit"))
async def myfit_command(message: Message):
    """Показать последнюю рекомендацию"""
    user_id = message.from_user.id
    
    if user_id in user_data and user_data[user_id].get('last_recommendation'):
        recommendation = user_data[user_id]['last_recommendation']
        result_text = (
            f"Ваша последняя рекомендация:\n\n"
            f"Размер: **{recommendation['size']}**\n"
            f"Модель: {recommendation['model']}\n"
            f"Ссылка: {recommendation['link']}"
        )
        await message.answer(result_text, parse_mode=ParseMode.MARKDOWN)
    else:
        await message.answer("У вас пока нет рекомендаций. Нажмите /start для подбора размера.")

@dp.message(Command("reset"))
async def reset_command(message: Message):
    """Сброс данных пользователя"""
    user_id = message.from_user.id
    if user_id in user_data:
        del user_data[user_id]
    await message.answer("Данные сброшены. Нажмите /start для нового подбора.")

@dp.message(Command("privacy"))
async def privacy_command(message: Message):
    """Политика конфиденциальности"""
    privacy_text = (
        "🔒 Политика конфиденциальности SENS Fit\n\n"
        "• Фото хранятся не более 24 часов\n"
        "• Данные используются только для подбора размера\n"
        "• Мы не передаем данные третьим лицам\n"
        "• Соблюдаем 152-ФЗ и GDPR\n\n"
        f"По вопросам: {PRIVACY_EMAIL}"
    )
    await message.answer(privacy_text)

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """Обработчик команды /start"""
    user_id = message.from_user.id
    
    # Инициализируем данные пользователя
    user_data[user_id] = {
        'photos': {},
        'quiz_data': {},
        'last_recommendation': None
    }
    
    welcome_text = (
        "SENS Fit 👋\n\n"
        "Подберём бюстгальтер, который вы не почувствуете на себе.\n"
        "💡 Нужно 1-2 минуты и сантиметровая лента *или* 2 фото.\n\n"
        "Готовы продолжить?"
    )
    
    keyboard = create_keyboard(
        ("✅ Да", "consent_yes"),
        ("❌ Нет", "consent_no")
    )
    
    await message.answer(welcome_text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "consent_no")
async def handle_consent_no(callback: CallbackQuery):
    """Обработка отказа от согласия"""
    await callback.message.edit_text(
        "Спасибо за интерес к SENS Fit! 😊\n"
        "Если передумаете, просто нажмите /start"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "consent_yes")
async def handle_consent_yes(callback: CallbackQuery, state: FSMContext):
    """Обработка согласия и переход к согласию на обработку данных"""
    consent_text = (
        "Мы попросим ваши мерки / фото только для расчёта размера.\n"
        "Фото храним ≤ 24 ч, потом удаляем.\n\n"
        "Нажимая «Согласен», вы даёте согласие на 152-ФЗ / GDPR."
    )
    
    keyboard = create_keyboard(
        ("✅ Согласен", "data_consent_yes"),
        ("❌ Отмена", "data_consent_no")
    )
    
    await callback.message.edit_text(consent_text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "data_consent_no")
async def handle_data_consent_no(callback: CallbackQuery):
    """Обработка отказа от обработки данных"""
    await callback.message.edit_text(
        "Понятно! Без согласия на обработку данных мы не можем подобрать размер.\n"
        "Если передумаете, нажмите /start"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "data_consent_yes")
async def handle_data_consent_yes(callback: CallbackQuery, state: FSMContext):
    """Обработка согласия на данные и выбор метода"""
    method_text = "Как вам удобнее подобрать размер?"
    
    keyboard = create_keyboard(
        ("📸 Фото-скан (точнее)", "method_photo"),
        ("✏️ Квиз без фото", "method_quiz")
    )
    
    await callback.message.edit_text(method_text, reply_markup=keyboard)
    await callback.answer()

# ФОТО-СКАН СЦЕНАРИЙ
@dp.callback_query(lambda c: c.data == "method_photo")
async def handle_method_photo(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора фото-скана"""
    photo_instructions = (
        "Нужно 2 фото в полный рост:\n"
        "1⃣ Спереди   2⃣ Профиль\n\n"
        "• Обтягивающее бельё или лёгкий топ\n"
        "• Светлый однородный фон\n"
        "• Руки вдоль тела\n"
        "• Свет без резких теней\n\n"
        "Когда будете готовы, нажмите «Сделать фото»."
    )
    
    keyboard = create_keyboard(("📷 Сделать фото", "start_photo_process"))
    
    await callback.message.edit_text(photo_instructions, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "start_photo_process")
async def start_photo_process(callback: CallbackQuery, state: FSMContext):
    """Начало процесса фото-скана - запрос роста"""
    await state.set_state(UserStates.waiting_for_height)
    await callback.message.edit_text("Введите ваш рост (см) — нужен для точности.")
    await callback.answer()

@dp.message(UserStates.waiting_for_height)
async def handle_height_input(message: Message, state: FSMContext):
    """Обработка ввода роста"""
    try:
        height = int(message.text)
        if 130 <= height <= 220:
            user_id = message.from_user.id
            user_data[user_id]['height'] = height
            
            await state.set_state(UserStates.waiting_for_front_photo)
            await message.answer("Загрузите фронтальное фото.")
        else:
            await message.answer("Пожалуйста, введите рост от 130 до 220 см.")
    except ValueError:
        await message.answer("Пожалуйста, введите число.")

@dp.message(UserStates.waiting_for_front_photo)
async def handle_front_photo(message: Message, state: FSMContext):
    """Обработка фронтального фото"""
    if not message.photo:
        await message.answer("Пожалуйста, отправьте фото.")
        return
    
    user_id = message.from_user.id
    
    # Получаем фото
    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    file_path = file.file_path
    file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
    
    # Скачиваем фото
    img_bytes = await download_image_from_url(file_url)
    if img_bytes is None:
        await message.answer("Не удалось скачать фото. Попробуйте еще раз.")
        return
    
    # Сохраняем фронтальное фото
    user_data[user_id]['photos']['front'] = img_bytes
    
    await state.set_state(UserStates.waiting_for_profile_photo)
    await message.answer("Теперь фото сбоку (левый или правый профиль).")

@dp.message(UserStates.waiting_for_profile_photo)
async def handle_profile_photo(message: Message, state: FSMContext):
    """Обработка профильного фото и отправка на API"""
    if not message.photo:
        await message.answer("Пожалуйста, отправьте фото.")
        return
    
    user_id = message.from_user.id
    
    # Получаем фото
    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    file_path = file.file_path
    file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
    
    # Скачиваем фото
    img_bytes = await download_image_from_url(file_url)
    if img_bytes is None:
        await message.answer("Не удалось скачать фото. Попробуйте еще раз.")
        return
    
    # Сохраняем профильное фото
    user_data[user_id]['photos']['profile'] = img_bytes
    
    # Показываем обработку
    processing_msg = await message.answer("⏳ Анализируем фото… (~5 сек)")
    
    # Отправляем на API
    result = await send_photos_to_api(user_id)
    
    if result:
        # Сохраняем рекомендацию
        user_data[user_id]['last_recommendation'] = result
        
        # Показываем результат
        result_text = (
            f"✔️ Ваш идеальный размер: **{result['size']}**\n"
            f"Рекомендуемая модель:\n"
            f"• {result['model']}\n"
            f"• Ссылка: [🛍️ Купить на WB]({result['link']})"
        )
        
        keyboard = create_keyboard(
            ("✅ Подошло", "feedback_good"),
            ("❌ Не подошло", "feedback_bad")
        )
        
        await processing_msg.edit_text(result_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        await state.set_state(UserStates.waiting_for_feedback)
    else:
        await processing_msg.edit_text("Ошибка при анализе фото. Попробуйте еще раз.")

# КВИЗ СЦЕНАРИЙ
@dp.callback_query(lambda c: c.data == "method_quiz")
async def handle_method_quiz(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора квиза"""
    await state.set_state(UserStates.waiting_for_quiz_comfortable_bra)
    question_text = "Есть ли у вас сейчас бюстгальтер, который сидит комфортно?"
    keyboard = create_keyboard(
        ("👍 Да", "quiz_comfortable_yes"),
        ("👎 Нет", "quiz_comfortable_no")
    )
    await callback.message.edit_text(question_text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("quiz_comfortable_"))
async def handle_comfortable_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора удобного бюстгальтера"""
    user_id = callback.from_user.id
    comfortable_type = callback.data.split("_")[2]
    user_data[user_id]['quiz_data']['comfortable_bra'] = comfortable_type
    
    if comfortable_type == "yes":
        # Если есть удобный бюстгальтер
        await state.set_state(UserStates.waiting_for_quiz_current_size)
        await callback.message.edit_text("Укажите его размер (пример: 75C).")
    else:
        # Если нет удобного бюстгальтера
        await state.set_state(UserStates.waiting_for_quiz_underbust)
        await callback.message.edit_text("Возьмите сантиметровую ленту. Измерьте под грудью (плотно). Введите число в см.")
    await callback.answer()

@dp.message(UserStates.waiting_for_quiz_current_size)
async def handle_current_size_input(message: Message, state: FSMContext):
    """Обработка ввода текущего размера"""
    current_size = message.text.strip()
    user_id = message.from_user.id
    user_data[user_id]['quiz_data']['current_size'] = current_size
    
    await state.set_state(UserStates.waiting_for_quiz_underbust)
    await message.answer("Возьмите сантиметровую ленту. Измерьте под грудью (плотно). Введите число в см.")

@dp.message(UserStates.waiting_for_quiz_underbust)
async def handle_underbust_input(message: Message, state: FSMContext):
    """Обработка ввода обхвата под грудью"""
    try:
        underbust = int(message.text)
        if 60 <= underbust <= 120:
            user_id = message.from_user.id
            user_data[user_id]['quiz_data']['underbust'] = underbust
            
            await state.set_state(UserStates.waiting_for_quiz_bust)
            await message.answer("Введите обхват груди (см):")
        else:
            await message.answer("Пожалуйста, введите число от 60 до 120 см.")
    except ValueError:
        await message.answer("Пожалуйста, введите число.")

@dp.message(UserStates.waiting_for_quiz_bust)
async def handle_bust_input(message: Message, state: FSMContext):
    """Обработка ввода обхвата груди"""
    try:
        bust = int(message.text)
        if 70 <= bust <= 140:
            user_id = message.from_user.id
            user_data[user_id]['quiz_data']['bust'] = bust
            
            await state.set_state(UserStates.waiting_for_quiz_breast_shape)
            await message.answer("Как бы вы описали форму груди?", reply_markup=create_keyboard(
                ("🔻 Широкая база", "breast_shape_wide"),
                ("🔸 Узкая / объёмная", "breast_shape_narrow"),
                ("🔹 Низкий посад", "breast_shape_low"),
                ("❔ Не знаю", "breast_shape_unknown")
            ))
        else:
            await message.answer("Пожалуйста, введите число от 70 до 140 см.")
    except ValueError:
        await message.answer("Пожалуйста, введите число.")

@dp.callback_query(lambda c: c.data.startswith("breast_shape_"))
async def handle_breast_shape_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора формы груди"""
    user_id = callback.from_user.id
    breast_shape = callback.data.split("_")[2]
    user_data[user_id]['quiz_data']['breast_shape'] = breast_shape
    
    await state.set_state(UserStates.waiting_for_quiz_bra_type)
    await callback.message.edit_text("Какой тип бюстгальтера предпочитаете?", reply_markup=create_keyboard(
        ("👙 Бралетт", "bra_type_bralette"),
        ("💪 Спортивный", "bra_type_sport"),
        ("💎 Классический", "bra_type_classic"),
        ("🚀 Лёгкий push-up", "bra_type_pushup")
    ))
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("bra_type_"))
async def handle_bra_type_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа бюстгальтера"""
    user_id = callback.from_user.id
    bra_type = callback.data.split("_")[2]
    user_data[user_id]['quiz_data']['bra_type'] = bra_type
    
    await state.set_state(UserStates.waiting_for_quiz_priority)
    await callback.message.edit_text("Что для вас важнее всего?", reply_markup=create_keyboard(
        ("☁️ Комфорт", "priority_comfort"),
        ("👁 Эстетика", "priority_aesthetics"),
        ("🤸‍♀️ Поддержка", "priority_support")
    ))
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("priority_"))
async def handle_priority_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора приоритета"""
    user_id = callback.from_user.id
    priority = callback.data.split("_")[1]
    user_data[user_id]['quiz_data']['priority'] = priority
    
    await state.set_state(UserStates.waiting_for_quiz_skin_tone)
    await callback.message.edit_text("Ваш оттенок кожи ближе к…", reply_markup=create_keyboard(
        ("🌕 Светлый", "skin_tone_light"),
        ("🏽 Средний", "skin_tone_medium"),
        ("🏿 Тёмный", "skin_tone_dark")
    ))
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("skin_tone_"))
async def handle_skin_tone_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора тона кожи"""
    user_id = callback.from_user.id
    skin_tone = callback.data.split("_")[2]
    user_data[user_id]['quiz_data']['skin_tone'] = skin_tone
    
    # Получаем все данные квиза для отображения
    quiz_data = user_data[user_id]['quiz_data']
    
    # Создаем текст с выбранными пунктами
    summary_text = "📋 Ваши ответы:\n\n"
    
    # Добавляем каждый выбранный пункт
    if 'comfortable_bra' in quiz_data:
        comfortable_text = "👍 Да" if quiz_data['comfortable_bra'] == 'yes' else "👎 Нет"
        summary_text += f"• Есть ли комфортный бюстгальтер: {comfortable_text}\n"
    
    if 'current_size' in quiz_data:
        summary_text += f"• Текущий размер: {quiz_data['current_size']}\n"
    
    if 'underbust' in quiz_data:
        summary_text += f"• Обхват под грудью: {quiz_data['underbust']} см\n"
    
    if 'bust' in quiz_data:
        summary_text += f"• Обхват груди: {quiz_data['bust']} см\n"
    
    if 'breast_shape' in quiz_data:
        shape_map = {
            'wide': "🔻 Широкая база",
            'narrow': "🔸 Узкая / объёмная", 
            'low': "🔹 Низкий посад",
            'unknown': "❔ Не знаю"
        }
        summary_text += f"• Форма груди: {shape_map.get(quiz_data['breast_shape'], quiz_data['breast_shape'])}\n"
    
    if 'bra_type' in quiz_data:
        type_map = {
            'bralette': "👙 Бралетт",
            'sport': "💪 Спортивный",
            'classic': "💎 Классический",
            'pushup': "🚀 Лёгкий push-up"
        }
        summary_text += f"• Тип бюстгальтера: {type_map.get(quiz_data['bra_type'], quiz_data['bra_type'])}\n"
    
    if 'priority' in quiz_data:
        priority_map = {
            'comfort': "☁️ Комфорт",
            'aesthetics': "👁 Эстетика",
            'support': "🤸‍♀️ Поддержка"
        }
        summary_text += f"• Приоритет: {priority_map.get(quiz_data['priority'], quiz_data['priority'])}\n"
    
    if 'skin_tone' in quiz_data:
        tone_map = {
            'light': "🌕 Светлый",
            'medium': "🏽 Средний", 
            'dark': "🏿 Тёмный"
        }
        summary_text += f"• Тон кожи: {tone_map.get(quiz_data['skin_tone'], quiz_data['skin_tone'])}\n"
    
    # Отправляем сообщение с выбранными пунктами
    await callback.message.edit_text(summary_text)
    
    # Отправляем отдельное сообщение с кнопкой "Рассчитать"
    await callback.message.answer("Теперь нажмите «Рассчитать» для получения рекомендации:", reply_markup=create_keyboard(
        ("🚀 Рассчитать", "quiz_calculate")
    ))
    
    await state.set_state(UserStates.waiting_for_quiz_calculate)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "quiz_calculate")
async def handle_quiz_calculate(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки «Рассчитать»"""
    user_id = callback.from_user.id
    
    # Показываем обработку
    processing_msg = await callback.message.edit_text("⏳ Рассчитываем размер… (~5 сек)")
    
    # Рассчитываем размер на основе квиза
    quiz_result = calculate_quiz_size(user_id)
    
    if quiz_result:
        # Сохраняем рекомендацию
        user_data[user_id]['last_recommendation'] = quiz_result
        
        # Показываем результат
        result_text = (
            f"✔️ Рекомендуемый размер: **{quiz_result['size']}**\n"
            f"Подойдёт модель:\n"
            f"• {quiz_result['model']}\n"
            f"Ссылки: [WB]({quiz_result['link']}) [Ozon]({quiz_result['link']})"
        )
        
        keyboard = create_keyboard(
            ("✅ Подошло", "feedback_good"),
            ("❌ Не подошло", "feedback_bad")
        )
        
        await processing_msg.edit_text(result_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        await state.set_state(UserStates.waiting_for_feedback)
    else:
        await processing_msg.edit_text("Ошибка при расчете размера. Попробуйте еще раз.")
    
    await callback.answer()

# ОБРАТНАЯ СВЯЗЬ
@dp.callback_query(lambda c: c.data.startswith("feedback_"))
async def handle_feedback(callback: CallbackQuery, state: FSMContext):
    """Обработка обратной связи"""
    feedback_type = callback.data.split("_")[1]
    
    if feedback_type == "good":
        await callback.message.edit_text(
            "Спасибо! Это помогает нам стать точнее 💜\n\n"
            "Нажмите /start для нового подбора размера."
        )
    else:
        await callback.message.edit_text(
            "Спасибо за обратную связь! Мы учтем это для улучшения точности.\n\n"
            "Нажмите /start для нового подбора размера."
        )
    
    await callback.answer()

# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
async def download_image_from_url(file_url: str) -> Optional[bytes]:
    """Скачивает изображение по URL"""
    try:
        response = requests.get(file_url)
        if response.status_code == 200:
            return response.content
        return None
    except Exception as e:
        logging.error(f"Ошибка при скачивании изображения: {e}")
        return None

async def send_photos_to_api(user_id: int) -> Optional[Dict[str, str]]:
    """Отправляет фото на API и возвращает результат"""
    try:
        user_info = user_data[user_id]
        front_photo = user_info['photos']['front']
        profile_photo = user_info['photos']['profile']
        height = user_info['height']
        
        front_photo_base64 = base64.b64encode(front_photo).decode()
        profile_photo_base64 = base64.b64encode(profile_photo).decode()
        
        headers = {"Authorization": API_KEY}
        
        data = {
            "customScanId": f"scan_{user_id}",
            "photoScan": {
                "age": DEFAULT_AGE,
                "weight": DEFAULT_WEIGHT,
                "height": height * 10,  # API ожидает в мм
                "gender": DEFAULT_GENDER,
                "frontPhoto": front_photo_base64,
                "rightPhoto": profile_photo_base64,
            },
        }
        
        response = requests.post(url=API_URL, headers=headers, json=data)
        
        if response.status_code == 200:
            api_data = response.json()
            return parse_api_response_for_size(api_data)
        else:
            logging.error(f"API request failed: {response.text}")
            return None
            
    except Exception as e:
        logging.error(f"Ошибка при отправке на API: {e}")
        return None



def parse_api_response_for_size(data: Dict[str, Any]) -> Dict[str, str]:
    """Парсит ответ API для получения размера бюстгальтера"""
    try:
        # Здесь должна быть логика определения размера на основе измерений
        # Пока возвращаем заглушку
        measurements = data.get('measurements', [])
        
        # Простая логика определения размера (заглушка)
        size = "75C EU (34C US)"
        model = "SENS Seamless SoftTouch, цвет Nude"
        link = f"{WILDBERRIES_BASE_URL}12345678"
        
        return {
            'size': size,
            'model': model,
            'link': link
        }
    except Exception as e:
        logging.error(f"Ошибка при парсинге ответа API: {e}")
        return None

def calculate_quiz_size(user_id: int) -> Optional[Dict[str, str]]:
    """Рассчитывает размер на основе квиза"""
    try:
        quiz_data = user_data[user_id]['quiz_data']
        underbust = quiz_data['underbust']
        bust = quiz_data['bust']
        
        # Если есть текущий размер, используем его как основу
        if 'current_size' in quiz_data and quiz_data['current_size']:
            size = quiz_data['current_size']
        else:
            # Рассчитываем размер на основе измерений
            cup_size = bust - underbust
            if cup_size <= 10:
                cup = "A"
            elif cup_size <= 12:
                cup = "B"
            elif cup_size <= 14:
                cup = "C"
            elif cup_size <= 16:
                cup = "D"
            else:
                cup = "E"
            
            band_size = underbust
            if band_size < 70:
                band_size = 70
            elif band_size > 90:
                band_size = 90
            
            size = f"{band_size}{cup} EU"
        
        # Выбираем модель на основе предпочтений
        bra_type = quiz_data.get('bra_type', 'classic')
        priority = quiz_data.get('priority', 'comfort')
        skin_tone = quiz_data.get('skin_tone', 'light')
        
        if bra_type == 'bralette':
            model = "SENS Bralette Comfort (беж), код 12345678"
        elif bra_type == 'sport':
            model = "SENS Sport Active (черный), код 12345679"
        elif bra_type == 'pushup':
            model = "SENS Push-up Delight (беж), код 12345680"
        else:  # classic
            model = "SENS SoftTouch Classic (беж), код 12345678"
        
        link = f"{WILDBERRIES_BASE_URL}12345678"
        
        return {
            'size': size,
            'model': model,
            'link': link
        }
    except Exception as e:
        logging.error(f"Ошибка при расчете размера: {e}")
        return None

async def main() -> None:
    """Главная функция"""
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())