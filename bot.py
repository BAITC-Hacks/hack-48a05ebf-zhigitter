#!/usr/bin/env python3
"""FAQ-бот на 5 вопросов.

Терминальный чат: пользователь пишет вопрос, бот ищет ближайшую пару в faq.txt
по совпадению ключевых слов и печатает ответ. Если ничего похожего — «не знаю».
Только стандартная библиотека.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

FAQ_PATH = Path(__file__).with_name("faq.txt")

# Порог уверенности: если лучший ответ набрал меньше — честно говорим «не знаю».
THRESHOLD = 0.34
# Веса: важно, где именно нашлось слово из запроса.
W_QUESTION = 1.0
W_KEYWORDS = 0.8
W_ANSWER = 0.4
# Бонус, если запрос целиком встречается внутри вопроса.
W_SUBSTRING = 0.15
# Грубый стеммер: обрезаем слово до 4 букв, чтобы «призы», «призов» и «приз»
# считались одним словом. Морфологические библиотеки для 5 вопросов избыточны.
STEM_LEN = 4

STOPWORDS = {
    "а", "бы", "будет", "будут", "быть", "в", "во", "вообще", "все", "всё", "вы",
    "где", "для", "до", "его", "ее", "её", "если", "есть", "ещё", "еще", "же",
    "за", "и", "из", "или", "к", "как", "какие", "какой", "кто", "куда", "ли",
    "мне", "можно", "мы", "на", "надо", "нам", "наш", "наша", "наши", "не",
    "ни", "но", "ну", "нужно", "о", "об", "он", "она", "они", "по", "подскажи",
    "пожалуйста", "почему", "расскажи", "с", "скажи", "сколько", "со", "так",
    "такое", "там", "ты", "у", "что", "чем", "это", "этот", "я",
}


def stem(word: str) -> str:
    """Обрезаем окончание, чтобы формы одного слова совпали."""
    return word[:STEM_LEN] if len(word) > STEM_LEN else word


def normalize(text: str) -> list[str]:
    """Текст -> список значимых основ слов."""
    text = text.lower().replace("ё", "е")
    words = re.findall(r"[a-zа-я0-9]+", text)
    return [stem(w) for w in words if w not in STOPWORDS]


def load_faq(path: Path = FAQ_PATH) -> list[dict]:
    """Читает faq.txt: блоки Q:/A: (+ необязательный K: со словами-синонимами)."""
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        sys.exit(f"Не могу прочитать {path}: {exc}")

    entries: list[dict] = []
    current: dict[str, str] = {}
    field: str | None = None

    def flush() -> None:
        if current.get("question") and current.get("answer"):
            entries.append(
                {
                    "question": current["question"],
                    "answer": current["answer"],
                    "q_tokens": normalize(current["question"]),
                    "k_tokens": normalize(current.get("keywords", "")),
                    "a_tokens": normalize(current["answer"]),
                }
            )
        current.clear()

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if line.startswith("#"):
            continue
        if not line:
            flush()
            field = None
            continue
        tag = line[:2].upper()
        if tag in ("Q:", "A:", "K:"):
            field = {"Q:": "question", "A:": "answer", "K:": "keywords"}[tag]
            current[field] = line[2:].strip()
        elif field:  # продолжение многострочного значения
            current[field] = f"{current[field]} {line}".strip()
    flush()

    if not entries:
        sys.exit(f"В {path} не нашлось ни одной пары Q:/A:.")
    return entries


def score(query_tokens: list[str], entry: dict, query_text: str) -> float:
    """Доля слов запроса, нашедшихся в паре, с учётом веса места находки."""
    if not query_tokens:
        return 0.0
    total = 0.0
    for token in query_tokens:
        if token in entry["q_tokens"]:
            total += W_QUESTION
        elif token in entry["k_tokens"]:
            total += W_KEYWORDS
        elif token in entry["a_tokens"]:
            total += W_ANSWER
    result = total / len(query_tokens)
    if query_text and query_text in entry["question"].lower().replace("ё", "е"):
        result += W_SUBSTRING
    return result


def find_answer(query: str, faq: list[dict]) -> tuple[int | None, float]:
    """Возвращает (индекс лучшей пары или None, её скор)."""
    tokens = normalize(query)
    query_text = query.lower().replace("ё", "е").strip()
    best_index, best_score = None, 0.0
    for index, entry in enumerate(faq):
        current = score(tokens, entry, query_text)
        if current > best_score:
            best_index, best_score = index, current
    if best_index is None or best_score < THRESHOLD:
        return None, best_score
    return best_index, best_score


def format_topics(faq: list[dict]) -> str:
    return "\n".join(f"  {i + 1}. {e['question']}" for i, e in enumerate(faq))


def respond(query: str, faq: list[dict], debug: bool = False) -> tuple[str, bool]:
    """Готовая реплика бота и признак «ответ найден»."""
    index, value = find_answer(query, faq)
    suffix = f"   [score={value:.2f}]" if debug else ""
    if index is None:
        return (
            "Не знаю. Я отвечаю только на эти вопросы:\n"
            + format_topics(faq)
            + suffix
        ), False
    return faq[index]["answer"] + suffix, True


def main(argv: list[str]) -> int:
    try:  # чтобы кириллица не ломалась при выводе в файл или пайп
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if not sys.stdin.isatty():  # ввод из пайпа/файла приходит в utf-8
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

    args = [a for a in argv[1:] if a != "--debug"]
    debug = "--debug" in argv[1:]
    faq = load_faq()

    if args:  # разовый вопрос: python bot.py "какой трек"
        reply, found = respond(" ".join(args), faq, debug)
        print(reply)
        return 0 if found else 2

    print("FAQ-бот репетиции HackAlem AI. Команда Zhigitter.")
    print(f"Знаю ответы на {len(faq)} вопросов:")
    print(format_topics(faq))
    print("Команды: «помощь» — показать вопросы, «выход» — закончить.\n")

    while True:
        try:
            query = input("вы> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nпока!")
            return 0
        if not query:
            continue
        if query.lower() in ("выход", "exit", "quit", "q"):
            print("пока!")
            return 0
        if query.lower() in ("помощь", "help", "?"):
            print(f"бот> Мои вопросы:\n{format_topics(faq)}\n")
            continue
        reply, _ = respond(query, faq, debug)
        print(f"бот> {reply}\n")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
