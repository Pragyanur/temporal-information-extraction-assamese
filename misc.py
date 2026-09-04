import re

with open("resources/morphology-learning-texts.txt", "r", encoding='utf-8') as f:
    temp = f.read()

normalized_str = re.sub(r"(\d)\s(?=[\d])", r"\1", temp)

with open("resources/morphology-learning-texts-concat.txt", "w", encoding='utf-8') as f:
    f.write(normalized_str)
