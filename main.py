import requests
from tabulate import tabulate
import numpy as np

# РАБОЧИЙ КОД

print("Connecting to server...")
session = requests.Session()

def serialize_table_to_json(observation_table): # Преобразование таблицы наблюдений в формат JSON
    prefixes_main = ["e"] + observation_table.S[1:observation_table.main_table_end].tolist()
    prefixes_extra = observation_table.S[observation_table.main_table_end:].tolist()
    suffix_list = ["e"] + observation_table.E[1:].tolist()

    table_string = "".join([str(val) for row in observation_table._T.values() for val in row])

    return {
        "main_prefixes": " ".join(prefixes_main),
        "complementary_prefixes": " ".join(prefixes_extra),
        "suffixes": " ".join(suffix_list),
        "table": table_string,
    }

def generate_maze(width, height, wall_probability, exit_count): # Генерация лабиринта
    try:
        response = session.post(
            "http://localhost:8080/generate_graph",
            json={"width": width, "height": height, "pr_of_break_wall": wall_probability, "num_of_finish_edge": exit_count}
        )
        if response.status_code == 200:
            print("Maze generation succeeded.")
            return True
        print("Maze generation failed:", response.status_code)
    except requests.RequestException as exc:
        print("Request error while generating maze:", exc)
    return False

def evaluate_equivalence(observation_table): # Проверка эквивалентности таблицы наблюдений целевому автомату
    try:
        response = session.post(
            "http://localhost:8080/check_table",
            json=serialize_table_to_json(observation_table)
        )
        if response.status_code == 200:
            server_reply = response.text
            if server_reply != "true":
                print("Counterexample identified:", server_reply)
                return server_reply
            print(observation_table)
            print("Success!")
            return server_reply
        print("Error during equivalence check:", response.status_code)
    except requests.RequestException as exc:
        print("Request error during equivalence check:", exc)
    return None

def check_string_membership(word): # Проверка принадлежности строки языку
    try:
        response = session.post(
            "http://localhost:8080/check_membership",
            data=word,
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            return int(response.content) # Возвращает 1 или 0
        print("Error during membership check:", response.status_code)
    except requests.RequestException as exc:
        print("Request error during membership check:", exc)
    return ""

class ObservationTable:
    def __init__(self, alphabet):
        self.A = alphabet  # Алфавит языка (например, ['E', 'W', 'N', 'S']).
        self.S = np.array([""])  # Массив префиксов. Изначально содержит только пустую строку.
        self.E = np.array([""])  # Массив суффиксов. Изначально содержит только пустую строку.
        self._T = {0: np.array([0])}  # Таблица значений, где ключ — строка, а значение — результаты проверки.
        self.row_pointer = 0  # Указатель на текущую строку (для итерации по основным префиксам).
        self.main_table_end = 1  # Индекс конца основной таблицы (начинается с одного элемента — пустой строки).

    def add_suffixes(self, word):
        for i in range(len(word) - 1, -1, -1): # Цикл от конца строки к началу
            suffix = word[i:]  # Генерируем все возможные суффиксы.
            if suffix not in self.E:  # Проверяем, есть ли суффикс в массиве.
                self.E = np.append(self.E, suffix)  # Добавляем новый суффикс в массив.
                for row_id in self._T:  # Обновляем каждую строку таблицы для нового суффикса.
                    self._T[row_id] = np.append(
                        self._T[row_id], check_string_membership(self.S[row_id] + suffix)
                    )

    def add_new_prefix(self, prefix):
        self.S = np.append(self.S, prefix)  # Добавляем новый префикс в массив.
        new_row = [check_string_membership(prefix + suffix) for suffix in self.E]  # Генерируем строку для нового префикса.
        self._T[len(self.S) - 1] = np.array(new_row)  # Добавляем новую строку в таблицу.

    def expand_table(self):
        while self.row_pointer < self.main_table_end:
            for symbol in self.A:  # Присоединяем к каждому префиксу символы алфавита.
                self.add_new_prefix(self.S[self.row_pointer] + symbol)
                self.align_rows()  # Проверяем, можно ли обновить основную таблицу.
            self.row_pointer += 1  # Переходим к следующему префиксу.

    def align_rows(self):
        index = self.main_table_end
        while index < len(self.S):
            if self.is_unique_row(index):  # Проверяем, уникальна ли строка.
                self.move_to_main_table(index)  # Если строка уникальна, перемещаем её в основную таблицу.
            index += 1

    def is_unique_row(self, row_idx):
        return all(
            not np.array_equal(self._T[row_idx], self._T[main_idx])
            for main_idx in range(self.main_table_end)
        )

    def move_to_main_table(self, row_idx):
        row_data = self._T[row_idx].copy()  # Копируем данные строки.
        prefix = self.S[row_idx]  # Берём соответствующий префикс.

        if row_idx > self.main_table_end:
            # Перемещаем строки вниз, чтобы освободить место.
            for idx in range(row_idx, self.main_table_end, -1):
                self._T[idx] = self._T[idx - 1].copy()
                self.S[idx] = self.S[idx - 1]

        # Помещаем данные строки в основную таблицу.
        self._T[self.main_table_end] = row_data
        self.S[self.main_table_end] = prefix
        self.main_table_end += 1  # Обновляем индекс конца основной таблицы.

    def __str__(self):
        header_row = [""] + ["ε"] + list(self.E)[1:]  # Заголовок таблицы.
        table_data = [[self.S[i]] + list(self._T[i]) for i in range(len(self.S))]  # Формируем строки таблицы.
        table_data[0][0] = "ε"  # Обозначаем пустую строку как ε.
        table_data.insert(self.main_table_end + 1, ["+"] + [""] * len(self.E))  # Разделитель между таблицами.
        return tabulate([header_row] + table_data, headers="firstrow", tablefmt="github")

if __name__ == "__main__":
    alphabet = list("EWNS")
    if generate_maze(2, 4, 3, 1):
        obs_table = ObservationTable(alphabet)
        obs_table.expand_table()

        counterexample = evaluate_equivalence(obs_table)
        while counterexample != "true":
            obs_table.add_suffixes(counterexample) # добавление контрпримера как суффикса
            obs_table.align_rows() # перестановка строк
            obs_table.expand_table() # расширение таблицы
            counterexample = evaluate_equivalence(obs_table) # повторная проверка
