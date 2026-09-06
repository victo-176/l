#!/usr/bin/env python3
"""A-to-Z logic smoke test for bot.py (stubbed Telegram/network). Run: python3 test_bot_logic.py"""
import os, sys, types as T, json, sqlite3, tempfile, importlib.util

# ---- stub external deps ----
class _FakeBtn:
    def __init__(self, **k):
        self.__dict__.update(k)
    def to_dict(self):
        return dict(self.__dict__)

tb_types = T.SimpleNamespace(
    InlineKeyboardMarkup=lambda **k: T.SimpleNamespace(add=lambda *a, **k2: None, row=lambda *a, **k2: None),
    InlineKeyboardButton=_FakeBtn,
    KeyboardButton=_FakeBtn,
    CopyTextButton=lambda **k: T.SimpleNamespace(),
)
sys.modules['telebot'] = T.SimpleNamespace(types=tb_types, TeleBot=lambda *a, **k: T.SimpleNamespace(
    message_handler=lambda *a, **k: (lambda f: f),
    callback_query_handler=lambda *a, **k: (lambda f: f),
    edit_message_text=lambda *a, **k: None,
    send_message=lambda *a, **k: None,
    answer_callback_query=lambda *a, **k: None,
    reply_to=lambda *a, **k: None,
    infinity_polling=lambda *a, **k: None,
    delete_webhook=lambda **k: None,
    register_next_step_handler_by_chat_id=lambda *a, **k: None,
    send_document=lambda *a, **k: None,
))
_apiexc = type("ApiTelegramException", (Exception,), {"__init__": lambda self, *a, **k: (setattr(self, "error_code", k.get("error_code", 0)), Exception.__init__(self, str(a)))[1]})
sys.modules['telebot.apihelper'] = T.SimpleNamespace(ApiTelegramException=_apiexc)
sys.modules['telebot.util'] = T.SimpleNamespace(update_command=lambda m, c: m)
sys.modules['socketio'] = T.SimpleNamespace(Client=T.SimpleNamespace)
sys.modules['engineio'] = T.SimpleNamespace()
sys.modules['requests'] = T.SimpleNamespace(
    post=lambda *a, **k: T.SimpleNamespace(status_code=200, text='', json=lambda: {"result": {"message_id": 1}}),
    get=lambda *a, **k: T.SimpleNamespace(status_code=200, text='', json=lambda: {}),
    Session=lambda: T.SimpleNamespace(headers=T.SimpleNamespace(update=lambda **k: None),
                                      get=lambda *a, **k: T.SimpleNamespace(status_code=200, text='', json=lambda: {}),
                                      post=lambda *a, **k: T.SimpleNamespace(status_code=200, text='', json=lambda: {})))
sys.modules['bs4'] = T.SimpleNamespace(BeautifulSoup=lambda *a, **k: T.SimpleNamespace(get_text=lambda **k: ''))
sys.modules['pyotp'] = T.SimpleNamespace(TOTP=lambda s: T.SimpleNamespace(now=lambda: '123456'))

tmp = tempfile.mkdtemp()
os.environ['PERSISTENT_DIR'] = tmp
os.environ['PREMIUM_EMOJI'] = '0'
os.environ['BOT_TOKEN'] = '0:test'

spec = importlib.util.spec_from_file_location('botmod', 'bot.py')
botmod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(botmod)

ok = True
def check(name, cond):
    global ok
    print(('PASS ' if cond else 'FAIL ') + name)
    if not cond:
        ok = False

# ---- app-filtered combos ----
botmod.save_combo('234', ['2349085281007', '2349085281327'], app_name='Talabat', broadcast=False)
botmod.save_combo('234', ['2348111111111', '2348122222222'], app_name='WhatsApp', broadcast=False)
tal = botmod.get_combo('234', 1, app_name='Talabat')
wa = botmod.get_combo('234', 1, app_name='WhatsApp')
check('Talabat combo returns only Talabat numbers', tal == ['2349085281007', '2349085281327'])
check('WhatsApp combo returns only WhatsApp numbers', '2349085281007' not in wa and len(wa) == 2)
check('no cross-app leak', '2349085281007' not in wa)
check('no-arg call still works (back-compat)', botmod.get_combo('234', 1, app_name=None) is not None)

# ---- ownership ----
check('assign Talabat num to user 1', botmod.assign_number_to_user(1, '2349085281007'))
botmod.set_number_app('2349085281007', 1, 'Talabat', '234')
check('second user cannot take owned number', botmod.assign_number_to_user(2, '2349085281007') is False)
check('user app numbers', botmod.get_numbers_for_user_app(1, 'Talabat') == ['2349085281007'])
check('user app numbers filtered by app', botmod.get_numbers_for_user_app(1, 'WhatsApp') == [])
check('get_app_for_number -> Talabat', botmod.get_app_for_number('2349085281007') == 'Talabat')

# ---- release clears ownership + list ----
botmod.release_number('2349085281007')
check('ownership cleared on release', botmod.get_numbers_for_user_app(1, 'Talabat') == [])
u = botmod.get_user(1)
check('user assigned_number cleared after release', (u is None) or (not u[5]))

# ---- comma-list OTP matching ----
botmod.save_user(7, assigned_number='234111,234222')
check('find user by second comma number', botmod.get_user_by_number('234222') == 7)

# ---- withdraw limits ----
mn, mx = botmod.get_withdraw_limits()
check('withdraw limits default', (mn, mx) == (1.0, 5.0))
check('amount below min rejected', botmod.check_withdrawal_amount(7, 0.5) is not None)
check('amount above max rejected', botmod.check_withdrawal_amount(7, 6.0) is not None)
botmod.set_setting('min_withdraw', '2.0')
botmod.set_setting('max_withdraw', '10.0')
check('limits load from DB', botmod.get_withdraw_limits() == (2.0, 10.0))

# ---- backup / restore roundtrip ----
path, counts = botmod.backup_all_tables()
check('backup file exists', os.path.exists(path))
check('backup includes number_app_assignments', 'number_app_assignments' in counts)
conn = sqlite3.connect(botmod.DB_PATH)
conn.execute("DELETE FROM users")
conn.commit()
conn.close()
okr, info = botmod.restore_from_backup()
check('restore succeeds', okr)
conn = sqlite3.connect(botmod.DB_PATH)
n = conn.execute("SELECT COUNT(*) FROM users WHERE user_id=7").fetchone()[0]
conn.close()
check('user 7 restored from backup', n == 1)

print('ALL OK' if ok else 'SOME FAILED')
sys.exit(0 if ok else 1)
