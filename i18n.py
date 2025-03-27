# coding: utf-8
from json_manager import config_manager
# import gettext
from gettext import translation

def getLang():
    return config_manager.get_config("gui").get("language")

def initI18n():
    # lang = []
    lang = getLang() 
    # print(lang)

    t = translation(domain="messages", localedir="i18n", languages=[lang], fallback=True)

    return t.gettext


_ = initI18n()