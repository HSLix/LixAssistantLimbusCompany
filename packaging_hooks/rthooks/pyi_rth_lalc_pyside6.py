"""Delay PySide6 initialization until the unified executable selects GUI mode."""

import os
import sys


if not any(argument in {"--candidate-runner", "--packaging-probe"} for argument in sys.argv[1:]):
    from _pyi_rth_utils import prepend_path_to_environment_variable
    from _pyi_rth_utils import qt as qt_rth_utils

    qt_rth_utils.ensure_single_qt_bindings_package("PySide6")
    qt_path = os.path.join(sys._MEIPASS, "PySide6" if sys.platform == "win32" else "PySide6/Qt")
    os.environ["QT_PLUGIN_PATH"] = os.path.join(qt_path, "plugins")
    if sys.platform == "win32":
        prepend_path_to_environment_variable(sys._MEIPASS, "PATH")
    elif sys.platform == "darwin":
        prepend_path_to_environment_variable(sys._MEIPASS, "DYLD_LIBRARY_PATH")
    qt_rth_utils.create_embedded_qt_conf("PySide6", qt_path)
