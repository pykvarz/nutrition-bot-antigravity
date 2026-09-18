import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()


def init_sheets():
    """
    Автоматически создает все необходимые листы и заголовки колонок в Google Таблице.
    """
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    cred_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    cred_json_str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = os.getenv("SPREADSHEET_ID")

    if not sheet_id:
        print("❌ Ошибка: SPREADSHEET_ID не указан в .env")
        sys.exit(1)

    if cred_file and os.path.exists(cred_file):
        creds = Credentials.from_service_account_file(cred_file, scopes=scopes)
    elif cred_json_str:
        creds = Credentials.from_service_account_info(json.loads(cred_json_str), scopes=scopes)
    else:
        print("❌ Ошибка: Укажите GOOGLE_SERVICE_ACCOUNT_FILE или GOOGLE_SERVICE_ACCOUNT_JSON в .env")
        sys.exit(1)

    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(sheet_id)

    # Описание необходимых листов и колонок
    sheets_config = {
        "Дневник": [
            "ID_записи", "Telegram_Update_ID", "Реальное_время", "Расчетная_дата",
            "Что_съедено", "Ккал", "Б", "Ж", "У", "Источник", "Тип", "Структура_JSON",
            "Оригинальный_текст", "Telegram_Message_ID", "Примечание"
        ],
        "Шаблоны": [
            "Название_блюда", "Калории", "Белки", "Жиры", "Углеводы", "Структура_JSON", "Примечание"
        ],
        "Рецепты": [
            "ID_рецепта", "Название", "Дата_создания", "Количество_порций",
            "Ккал_всего", "Белки_всего", "Жиры_всего", "Углеводы_всего",
            "Ккал_на_порцию", "Белки_на_порцию", "Жиры_на_порцию", "Углеводы_на_порцию",
            "Структура_JSON", "Примечание"
        ],
        "Настройки": [
            "Ключ", "Значение"
        ],
        "Состояние": [
            "Ключ", "Значение", "Updated_At"
        ],
        "История_действий": [
            "ID_действия", "Время", "Тип_действия", "Entity_Type", "Entity_ID",
            "Before_JSON", "After_JSON", "Undone"
        ],
    }

    existing_worksheets = {ws.title: ws for ws in spreadsheet.worksheets()}

    for title, headers in sheets_config.items():
        if title not in existing_worksheets:
            print(f"[+] Sozdanie lista '{title}'...")
            ws = spreadsheet.add_worksheet(title=title, rows=100, cols=len(headers) + 2)
            ws.append_row(headers)
        else:
            ws = existing_worksheets[title]
            all_vals = ws.get_all_values()
            if not all_vals:
                print(f"[*] Zapolnenie zagolovkov dlya '{title}'...")
                ws.append_row(headers)
            else:
                print(f"[OK] List '{title}' uzhe sushestvuet.")

    # Заполнение дефолтных настроек, если пусто
    ws_settings = spreadsheet.worksheet("Настройки")
    settings_vals = ws_settings.get_all_values()
    if len(settings_vals) <= 1:
        print("[*] Zapolnenie bazovyh nastroek...")
        default_settings = [
            ["TARGET_CALORIES", "2000"],
            ["TARGET_PROTEIN", "140"],
            ["TARGET_FAT", "60"],
            ["TARGET_CARBS", "220"],
            ["TIMEZONE", "Asia/Almaty"],
            ["DAY_CUTOFF_HOUR", "4"],
        ]
        for row in default_settings:
            ws_settings.append_row(row)

    print("[SUCCESS] Google Sheets uspeshno inicializirovana!")


if __name__ == "__main__":
    init_sheets()
