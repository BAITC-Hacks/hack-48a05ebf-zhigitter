#!/usr/bin/env python3
"""Смоук-тесты FAQ-бота: python test_bot.py"""

from __future__ import annotations

import sys

import bot

FAQ = bot.load_faq()

# (запрос, ожидаемый номер пары в faq.txt или None для «не знаю»)
CASES = [
    # перефразировки, которых нет в faq.txt дословно
    ("сколько времени осталось", 0),
    ("когда дедлайн", 0),
    ("кто участвует", 1),
    ("как называется наша команда", 1),
    ("что за трек", 2),
    ("куда заливать код", 3),
    ("как сдать решение", 3),
    ("будут ли призы", 4),
    # слово встречается только в тексте ответа
    ("rag", 2),
    # непохожие вопросы — бот должен признаться, что не знает
    ("как приготовить борщ", None),
    ("погода в Алматы", None),
    ("расскажи анекдот", None),
]

# каждый исходный вопрос обязан находить сам себя
CASES += [(entry["question"], i) for i, entry in enumerate(FAQ)]


def main() -> int:
    failed = []
    for query, expected in CASES:
        got, value = bot.find_answer(query, FAQ)
        if got != expected:
            failed.append(f"  «{query}»: ожидали {expected}, получили {got} (score={value:.2f})")

    reply, found = bot.respond("как приготовить борщ", FAQ)
    if found or "Не знаю" not in reply:
        failed.append("  respond() не вернул «не знаю» на посторонний вопрос")

    total = len(CASES) + 1
    if failed:
        print(f"FAIL: {len(failed)} из {total}")
        print("\n".join(failed))
        return 1
    print(f"OK: {total}/{total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
