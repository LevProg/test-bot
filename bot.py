import telebot
import pandas as pd
import sqlite3
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random

TOKEN = 'your-token'
bot = telebot.TeleBot(TOKEN)

conn = sqlite3.connect('sites.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    url TEXT,
    xpath TEXT
)''')
conn.commit()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    bot.reply_to(message, "Привет! Нажми кнопку ниже, чтобы загрузить Excel-файл с данными о сайтах.", reply_markup=markup)

@bot.message_handler(content_types=['document'])
def handle_document(message):
    if message.document.mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open('uploaded_file.xlsx', 'wb') as new_file:
            new_file.write(downloaded_file)
        
        df = pd.read_excel('uploaded_file.xlsx')
        
        # Форматируем вывод в Markdown
        response = "📋 **Содержимое файла:**\n\n"
        response += "```\n"
        response += f"{'Название':<12} | {'URL':<60} | {'XPath'}\n"
        response += "-" * 90 + "\n"
        for index, row in df.iterrows():
            title = str(row['title'])[:12].ljust(12)  # Обрезаем длинные названия
            url = str(row['url'])[:60] + ("..." if len(str(row['url'])) > 60 else "")  # Укорачиваем URL
            xpath = str(row['xpath'])
            response += f"{title} | {url:<60} | {xpath}\n"
        response += "```\n"
        
        bot.send_message(message.chat.id, response, parse_mode='Markdown')
        
        for index, row in df.iterrows():
            cursor.execute('INSERT INTO sites (title, url, xpath) VALUES (?, ?, ?)', 
                           (row['title'], row['url'], row['xpath']))
        conn.commit()
        
        bot.send_message(message.chat.id, "✅ Данные сохранены. Используй `/average_price` для вычисления средней цены.", parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, "❌ Загрузите файл в формате Excel (.xlsx).", parse_mode='Markdown')
def parse_price(url, xpath):
    try:
        # Используем Selenium, потому что цены подгружаются в JS
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        service = Service(executable_path="your-path")  # Укажите путь к chromedriver.exe
        driver = webdriver.Chrome(service=service, options=chrome_options)   

        print(f"Запрос к {url}")
        driver.get(url)
        
        # Случайные действия, чтобы избежать блокировки 
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(random.uniform(2, 4))
        
        # Ждем элементы
        try:
            price_elements = WebDriverWait(driver, 5).until(
                EC.presence_of_all_elements_located((By.XPATH, xpath))
            )
            print(f"Найдено элементов по XPath '{xpath}': {len(price_elements)}")
        except Exception as e:
            print(f"Не удалось найти элементы по XPath '{xpath}': {str(e)}")
            driver.quit()
            return []

        prices = []
        for i, elem in enumerate(price_elements):
            price_text = elem.text.strip()
            price_text = re.sub(r'[^\d]', '', price_text)
            if price_text:
                price = float(price_text)
                prices.append(price)
        print(f"Итоговый список цен: {prices}")
        driver.quit()
        return prices
    except Exception as e:
        print(f"Ошибка парсинга {url}: {e}")
        driver.quit()
        return []

@bot.message_handler(commands=['average_price'])
def average_price(message):
    cursor.execute('SELECT title, url, xpath FROM sites')
    sites = cursor.fetchall()
    
    for site in sites:
        title, url, xpath = site
        prices = parse_price(url, xpath)
        if prices:
            avg_price = sum(prices) / len(prices)
            bot.send_message(message.chat.id, f"Средняя цена на {title}: {avg_price:.2f} руб.")
        else:
            bot.send_message(message.chat.id, f"Не удалось найти цены на {title} (ошибка парсинга или неверный XPath).")

def test():
    # Тестовые данные
    sites = [
        ("M.Video Поиск", "https://www.mvideo.ru/product-list-page?q=айфон+15", "//span[contains(@class, 'price__main')]"),
        ("Ozon Поиск", "https://www.ozon.ru/category/smartfony-15502/apple-26303000/?text=айфон+15", "//span[contains(@class, 'c3025-b1')]")
    ]

    for title, url, xpath in sites:
        print(f"\nТестирование {title}:")
        prices = parse_price(url, xpath)
        print(f"Результат: {prices}")


if __name__ == '__main__':
    bot.polling(none_stop=True)