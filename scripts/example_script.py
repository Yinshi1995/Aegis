"""
Пример скрипта для запуска через ScriptRunnerTool.
Получает JSON через stdin, обрабатывает и выводит результат в stdout.
"""
import json
import sys


def main():
    """Прочитать аргументы из stdin и вернуть результат."""
    raw = sys.stdin.read()
    args = json.loads(raw) if raw.strip() else {}

    action = args.get("action", "hello")

    if action == "hello":
        name = args.get("name", "Мир")
        print(f"Привет, {name}!")

    elif action == "sum":
        numbers = args.get("numbers", [])
        result = sum(numbers)
        print(json.dumps({"result": result}))

    elif action == "info":
        print(json.dumps({
            "python": sys.version,
            "args_received": args,
        }, ensure_ascii=False))

    else:
        print(f"Неизвестное действие: {action}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
