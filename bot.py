import asyncio
import logging
import sys
import base64
import json
import requests
from typing import Dict, Any, Optional
from dataclasses import dataclass

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import aiohttp

TOKEN = '8175085117:AAH9h_xypx-tJ81j1XYarH9sRV2h99D6kJA'
API_KEY = '54XhqXF46TjiEEkeQN511K10zAUfZUNYrWkgveUQZPc'
ORG_ID = 'org_EkyEdbEB1UCmXvn1MUgTN' 
API_URL = f"https://platform.bodygram.com/api/orgs/{ORG_ID}/scans" 

# Состояния FSM
class UserStates(StatesGroup):
    waiting_for_consent = State()
    waiting_for_method = State()
    waiting_for_height = State()
    waiting_for_front_photo = State()
    waiting_for_profile_photo = State()
    waiting_for_quiz_underbust = State()
    waiting_for_quiz_bust = State()
    waiting_for_quiz_style = State()
    waiting_for_quiz_comfort = State()
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
        "🤖 SENS Fit Bot - подбор бюстгальтера\n\n"
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
        "По вопросам: privacy@sensfit.com"
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
    await state.set_state(UserStates.waiting_for_quiz_underbust)
    await callback.message.edit_text("Введите обхват под грудью (см):")
    await callback.answer()

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
            
            await state.set_state(UserStates.waiting_for_quiz_style)
            await message.answer("Выберите стиль бюстгальтера:", reply_markup=create_keyboard(
                ("Классический", "style_classic"),
                ("Спортивный", "style_sport"),
                ("Кружевной", "style_lace")
            ))
        else:
            await message.answer("Пожалуйста, введите число от 70 до 140 см.")
    except ValueError:
        await message.answer("Пожалуйста, введите число.")

@dp.callback_query(lambda c: c.data.startswith("style_"))
async def handle_style_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора стиля"""
    user_id = callback.from_user.id
    style = callback.data.split("_")[1]
    user_data[user_id]['quiz_data']['style'] = style
    
    await state.set_state(UserStates.waiting_for_quiz_comfort)
    await callback.message.edit_text("Выберите уровень комфорта:", reply_markup=create_keyboard(
        ("Комфорт", "comfort_comfort"),
        ("Средний", "comfort_medium"),
        ("Плотный", "comfort_tight")
    ))
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("comfort_"))
async def handle_comfort_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора комфорта и расчет размера"""
    user_id = callback.from_user.id
    comfort = callback.data.split("_")[1]
    user_data[user_id]['quiz_data']['comfort'] = comfort
    
    # Рассчитываем размер на основе квиза
    quiz_result = calculate_quiz_size(user_id)
    
    if quiz_result:
        # Сохраняем рекомендацию
        user_data[user_id]['last_recommendation'] = quiz_result
        
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
        
        await callback.message.edit_text(result_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        await state.set_state(UserStates.waiting_for_feedback)
    else:
        await callback.message.edit_text("Ошибка при расчете размера. Попробуйте еще раз.")
    
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
                "age": 25,  # Можно добавить в квиз
                "weight": 60000,  # Можно добавить в квиз
                "height": height * 10,  # API ожидает в мм
                "gender": "female",
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
        link = "https://www.wildberries.ru/catalog/12345678"
        
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
        
        # Простая логика определения размера (заглушка)
        cup_size = bust - underbust
        if cup_size <= 10:
            cup = "A"
        elif cup_size <= 12:
            cup = "B"
        elif cup_size <= 14:
            cup = "C"
        else:
            cup = "D"
        
        band_size = underbust
        if band_size < 70:
            band_size = 70
        elif band_size > 90:
            band_size = 90
        
        size = f"{band_size}{cup} EU"
        model = "SENS SoftTouch Classic (беж), код 12345678"
        link = "https://www.wildberries.ru/catalog/12345678"
        
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