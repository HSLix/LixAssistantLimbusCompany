# coding: utf-8
from json_manager import config_manager
# import gettext
from gettext import translation

def initI18n():
    # lang = []
    lang = config_manager.get_config("gui").get("language")
    # print(lang)
    t = translation(domain="messages", localedir="i18n", languages=[lang], fallback=True)
    return t.gettext

def getLang():
    return config_manager.get_config("gui").get("language")

_ = initI18n()