# import re

# with open("resources/morphology-learning-texts.txt", "r", encoding='utf-8') as f:
#     temp = f.read()

# normalized_str = re.sub(r"(\d)\s(?=[\d])", r"\1", temp)

# with open("resources/morphology-learning-texts-concat.txt", "w", encoding='utf-8') as f:
#     f.write(normalized_str)


# import pandas as pd

# # Load CSV
# df = pd.read_csv("resources/timex3_annotations.csv")

# # Convert expressions into a list of strings
# expressions = df["expression"].dropna().astype(str).drop_duplicates().tolist()

# with open("resources/expressions.txt", "w", encoding="utf-8") as f:
#     f.write("\n".join(expressions))

with open("resources/expressions.txt", "r", encoding='utf-8') as f:
    exps = f.read().split("\n")

with open("resources/expressions_preprocessed.txt", "r", encoding='utf-8') as f:
    exps_p = f.read().split("\n")

A = set(exps)
B = set(exps_p)

print(len(A))
print(len(B))

print(len(A.difference(B)))
print(B.difference(A))