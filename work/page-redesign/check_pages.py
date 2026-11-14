"""检查页面配置兼容、交互与重载；运行：QT_QPA_PLATFORM=offscreen .venv/bin/python work/page-redesign/check_pages.py。"""
import importlib.util
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

app = QApplication([])
base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / 'pages'

class Context:
    """提供页面资源和独立配置副本。"""
    def __init__(self, name, config=None, language='zh_CN'):
        self.path = base / name
        self.config = config or {}
        self.language = language
    def translate(self, zh, en):
        return zh if self.language == 'zh_CN' else en
    def load(self, defaults):
        return {**defaults, **self.config}
    def resource_path(self, path):
        return self.path / path

def load(name):
    spec = importlib.util.spec_from_file_location(name, base / name / 'page.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

team_module = load('team_presets')
mirror_module = load('mirror')
for language in ('zh_CN', 'en_US'):
    team = team_module.create_page(Context('team_presets', {'teams': [['yi_sang', 'faust']]}, language))
    assert team.submit()['teams'][0]['sinners'] == ['yi_sang', 'faust']
    team._keyword_buttons['burn'].click()
    team._slot_boxes[3].click()
    team._slot_boxes[1].click()
    team._slot_boxes[3].click()
    assert team.submit()['teams'][0]['gift_slot_order'] == [1]
    team._select_team(1)
    assert team._keyword_buttons['none'].isChecked()
    team._select_team(0)
    assert team._keyword_buttons['burn'].isChecked()
    team._order_list.setCurrentRow(1)
    team._move_sinner(-1)
    assert team.submit()['teams'][0]['sinners'] == ['faust', 'yi_sang']
    team._remove_sinner()
    assert team.submit()['teams'][0]['sinners'] == ['yi_sang']
    data = team.submit()
    assert team_module.create_page(Context('team_presets', data, language)).submit() == data
    mirror = mirror_module.create_page(Context('mirror', {'mirror_team': 8}, language))
    assert mirror.submit()['mirror_teams'] == [8]
    key = mirror_module.STAR_CARDS[0][0]
    mirror._star_buttons[key][2].click()
    assert [b.isChecked() for b in mirror._star_buttons[key]] == [False, False, True]
    data = mirror.submit()
    assert data['star_levels'][key] == 2
    assert mirror_module.create_page(Context('mirror', data, language)).submit() == data
    mirror._tabs.setCurrentIndex(1)
    mirror.resize(1280, 760)
    mirror.show()
    app.processEvents()
    mirror.grab().save(str(Path(__file__).parent / f'starlight-selected-{language}.png'))
    mirror.close()
    mirror._star_buttons[key][0].click()
    assert mirror.submit()['star_levels'][key] == 0
    mirror._clear_stars()
    assert not any(mirror.submit()['star_levels'].values())
    picker = mirror_module.TeamPickerDialog(Context('mirror', language=language), [8, 3])
    picker._order_list.setCurrentRow(1)
    picker._move_current(-1)
    assert picker.selected_teams() == [3, 8]
    picker.reject()
    assert mirror.submit()['mirror_teams'] == [8]
    for page, name, indices in ((team, 'team', (0, 1)), (mirror, 'mirror', (0, 1, 2))):
        page.resize(1280, 760)
        page.show()
        for index in indices:
            page._tabs.setCurrentIndex(index)
            app.processEvents()
            page.grab().save(str(Path(__file__).parent / f'{name}-{language}-{index}.png'))
        page.close()
assert mirror_module._restore_star_levels({'star_of_the_beginning': True, 'unknown': 2}) == mirror_module._restore_star_levels(None)
assert mirror_module._restore_teams({'mirror_teams': [3, 3, 99, '8']}) == [3, 8]
print('Page interaction and configuration checks passed in Chinese and English.')
