from pyvirtualdisplay import Display
from patchright.sync_api import sync_playwright
import time
import random
import base64
from PIL import Image
import requests
import pytesseract
from io import BytesIO
import os
import subprocess
from datetime import datetime


def kill_existing_xvfb():
    try:
        subprocess.run(["pkill", "-f", "Xvfb"], check=False)
        print("🛑 Предыдущие процессы Xvfb завершены.")
    except Exception as e:
        print(f"⚠️ Не удалось завершить Xvfb: {e}")




def launch_browser():
    # Инициализация виртуального дисплея
    display = Display(visible=0, size=(1280, 720))
    display.start()


    print("🚀 Запуск Playwright...")

    p = sync_playwright().start()
    browser = p.chromium.launch(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
            "--window-size=1280,720",
        ]
    )

    print("🌐 Браузер успешно запущен.")

    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
    )

    page = context.new_page()
    print("📄 Страница успешно создана.")

    return p, browser, page  # возвращаем только 3 значения


def human_like_mouse_movement(page):
    viewport = page.viewport_size
    width, height = viewport['width'], viewport['height']
    for _ in range(5):
        x = random.randint(100, width - 100)
        y = random.randint(100, height - 100)
        page.mouse.move(x, y, steps=10)
        time.sleep(random.uniform(0.1, 0.5))


def click_cloudflare_checkbox(page):
    print("🛡️ Пытаемся кликнуть по Cloudflare капче...")

    x = 300
    y = 300

    page.wait_for_timeout(1500)
    page.mouse.move(x, y, steps=15)
    page.wait_for_timeout(500)
    page.mouse.click(x, y)

    page.wait_for_timeout(3000)  # подождем немного после клика

    # Проверка наличия текста "Verify you are human"
    try:
        verify_elem = page.query_selector("#EJBt3")
        if verify_elem:
            text = verify_elem.inner_text()
            if "Verify you are human" in text:
                print("❌ Cloudflare проверка не пройдена. Начинаем заново.")
                raise Exception("Cloudflare captcha not passed")
    except Exception as e:
        print(f"⚠️ Проверка капчи завершилась с ошибкой: {e}")
        raise  # проброс ошибки наружу, чтобы main() перезапустил процесс

    print("✅ Клик по капче выполнен и проверка пройдена.")


def send_telegram_message(message):
    bot_token = "7847467543:AAEz53PH7T8KMhl3slociWCRLBuU6aWLA3I"
    chat_id = "-4726175328"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print("✅ Сообщение успешно отправлено в Telegram.")
        else:
            print(f"⚠️ Ошибка отправки сообщения: {response.text}")
    except Exception as e:
        print(f"❌ Ошибка при отправке сообщения в Telegram: {e}")


def get_captcha_text(page, max_attempts=3):
    page.wait_for_timeout(1000)
    for attempt in range(1, max_attempts + 1):
        print(f"[Попытка {attempt}] Получаем капчу...")

        try:
            img_elem = page.wait_for_selector("img.imageCaptcha", timeout=5000)

            for _ in range(10):
                src = img_elem.evaluate("el => el.getAttribute('src')")
                if src and src.startswith("data:image"):
                    break
                time.sleep(0.5)
            else:
                print("❌ Картинка капчи не загрузилась.")
                page.reload()
                page.wait_for_timeout(2000)
                continue

        except Exception as e:
            print(f"❌ Капча не найдена: {e}")
            page.reload()
            page.wait_for_timeout(2000)
            continue

        if not src or not src.startswith("data:image"):
            print("⚠️ Невалидный src капчи.")
            page.reload()
            page.wait_for_timeout(2000)
            continue

        try:
            base64_data = src.split(",")[1]
            image_data = base64.b64decode(base64_data)
            image = Image.open(BytesIO(image_data)).convert("L")

            captcha_text = pytesseract.image_to_string(
                image,
                config='--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            ).strip()

            if not captcha_text:
                print("⚠️ Капча не распознана. Пробуем снова...")
                page.reload()
                page.wait_for_timeout(3000)
                continue

            print(f"✅ Капча распознана: {captcha_text}")
            page.wait_for_timeout(1000)
            page.fill('.languageCaptcha',captcha_text)
            page.wait_for_timeout(1000)
            page.click(".btn-danger")
            try:
                # Ждём появления модального окна
                page.wait_for_timeout(2000)
                popup = page.query_selector(".swal2-modal")
                class_name = popup.evaluate("el => el.className")

                # Проверяем, стал ли он видимым
                if class_name and "visible" in class_name:
                    popup_text = popup.inner_text()
                    print(f"⚠️ Появился попап:")

                    if "Təsdiq kodu yanlışdır." or "Təsdiq kodundan istifadə edin." in popup_text:
                        print("❌ Неверная капча. Перезагружаем страницу...")

                        confirm_button = popup.query_selector(".swal2-confirm")
                        if confirm_button:
                            confirm_button.click()
                            page.wait_for_timeout(1000)

                        page.reload()
                        page.wait_for_timeout(3000)
                        continue
                else:
                    print("✅ Попап не появился — капча пройдена.")
            except Exception as e:
                print(f"⚠️ Ошибка при проверке попапа: {e}")

            print("✅ Капча прошла успешно.")
            return captcha_text, True

        except Exception as e:
            print(f"⚠️ Ошибка обработки капчи: {e}")
            page.wait_for_timeout(3000)

    print("❌ Капча не пройдена после всех попыток.")
    return "", False

def fill_form(page):
    page.select_option("#country", value="1")
    page.select_option("#visitingcountry", value="1")
    page.select_option("#city", value="7")
    page.select_option("#office", value="1")
    page.select_option("#officetype", value="1")
    page.select_option("#totalPerson", value="1")

    time.sleep(1)


def check_available_day(page):
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        available_day_alert = page.query_selector(".alert-danger.text-left")
        if available_day_alert:
            alert_text = available_day_alert.inner_text()
            if "Əlçatan tarix yoxdur" in alert_text:
                message = f"yer yoxdur — {now}"
                print(message)
                return False
        message = f"✅ Azad yer tapildi — {now}"
        send_telegram_message(message)
        print(message)
        return True
    except Exception as e:
        error_message = f"⚠️ Ошибка при проверке доступных дат: {e}"
        send_telegram_message(error_message)
        print(error_message)
        return False


def main():
    # 👉 Стартуем виртуальный дисплей
    kill_existing_xvfb()
    display = Display(visible=0, size=(1920, 1080))
    display.start()

    try:
        p, browser, page = launch_browser()
        page.goto("https://az-appointment.visametric.com/az")

        human_like_mouse_movement(page)
        page.wait_for_timeout(7000)

        click_cloudflare_checkbox(page)
        page.wait_for_timeout(2000)


        captcha_text, captcha_success = get_captcha_text(page)
        print("Распознанная капча:", captcha_text)

        if not captcha_success:
            print("❌ Капча е пройдена. Скрипт останавливается.")
            return

        page.wait_for_timeout(3000)
        fill_form(page)

        if check_available_day(page):
            print("✅ Даты доступны для записи.")
            page.click("#btnAppCountNext")
        else:
            print("")

        time.sleep(5)

    finally:
        browser.close()
        p.stop()
        # 👉 Останавливаем виртуальный дисплей
        display.stop()


if __name__ == "__main__":
    main()
