"""tier1_runner.py — обёртка для запуска tier1-traffic-studio агентов.

`tier1-fresh/start_studio.py` импортирует `from studio.agents import ...`,
но реальная папка называется `tier1-fresh`, не `studio`. Этот wrapper
регистрирует пакет `studio` в sys.modules указывающий на tier1-fresh,
затем exec'ит start_studio.py.

Использование:
    python tier1_runner.py --once
    python tier1_runner.py --agent seo_curator
"""
import os
import sys
import runpy
from pathlib import Path

TIER1_ROOT = Path(r"C:\Users\CarlosRi\Desktop\tier1-fresh")


def main():
    # 1) Регистрируем `studio` как пакет, указывающий на tier1-fresh
    import importlib.util
    import types

    # Создаём synthetic package
    studio_pkg = types.ModuleType("studio")
    studio_pkg.__path__ = [str(TIER1_ROOT)]
    sys.modules["studio"] = studio_pkg

    # 2) Регистрируем подпакеты (agents, config)
    for sub in ["agents", "config"]:
        sub_path = TIER1_ROOT / sub
        if sub_path.exists() and (sub_path / "__init__.py").exists():
            sub_pkg = types.ModuleType(f"studio.{sub}")
            sub_pkg.__path__ = [str(sub_path)]
            sys.modules[f"studio.{sub}"] = sub_pkg

    # 3) Парсим аргументы и exec'им start_studio.py
    args = sys.argv[1:]
    script = TIER1_ROOT / "start_studio.py"
    print(f"[tier1_runner] cwd={TIER1_ROOT}")
    print(f"[tier1_runner] script={script}")
    print(f"[tier1_runner] args={args}")
    sys.argv = [str(script)] + args
    os.chdir(TIER1_ROOT)
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
