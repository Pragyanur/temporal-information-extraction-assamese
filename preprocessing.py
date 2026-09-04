import re

def initialize_charmap(texts):
    """Create character mappings to tokenize symbols, quotes, and digits."""
    syms = [
        "।", "॥", ",", ".", "?", "!", ";", ":", "—", "(", ")", '≡',
        "[", "]", "{", "}", "\"", "…", "₹", "%", "+", "=", "/", "\\",
        "*", "@", "#", "&", "|", "<", ">", "_", '৷'
    ]

    char_map = {}
    ch_list = set()

    for t in texts:
        for ch in t:
            ch_list.add(ch)

    # # Assamese & ASCII Digits
    # digits = "0123456789০১২৩৪৫৬৭৮৯"

    for ch in ch_list:
        # 1. Handle single quotes / apostrophes (pad with space for clean tokenization)
        if ch in "’'`ʼ‘":
            char_map[ch] = "'"
        # 2. Handle double quotes
        elif ch in "“”":
            char_map[ch] = '"'
        # 3. Handle defined symbols & whitespace
        elif ch == "\t":
            char_map[ch] = " "
        elif ch in syms:
            char_map[ch] = f" {ch} "
        # 4. Handle digits
        # elif ch in digits:
        #     char_map[ch] = f" {ch} "
        # 5. Default case
        else:
            char_map[ch] = ch

    return char_map

def normalizer(text, cmap):
    """Return normalized and tokenized Assamese string."""
    temp = ""

    for i in text:
        temp += cmap[i]

    # Assamese-Bengali orthographic normalization
    temp = re.sub(r"ব়", "ৰ", temp)
    temp = re.sub(r"র", "ৰ", temp)
    temp = re.sub(r"য়", "য়", temp)
    temp = re.sub(r"ড়", "ড়", temp)
    temp = re.sub(r"ঢ়", "ঢ়", temp)
    
    # Zero-Width Joiner/Non-Joiner removal
    temp = re.sub(r"[\u200c\u200d]", "", temp)
    
    # Remove duplicate consecutive matras/diacritics
    temp = re.sub(r"([়ািীুূৃেৈোৌ্ঁঃংৎ])\1+", r"\1", temp)

    # Collapse multiple whitespaces into a single space
    temp = re.sub(r"\s+", " ", temp).strip()

    # Re-connect digits separated by standard punctuation (e.g., 1 , 000 -> 1,000 or 12 . 5 -> 12.5)
    digit_pattern = re.compile(r"(?<=[0-9০-৯])\s*([,.:/\u2013\u2014-])\s*(?=[0-9০-৯])")
    temp = digit_pattern.sub(r"\1", temp)

    # Re-connect contiguous digit sequences (e.g., 2 0 2 6 -> 2026)
    temp = re.sub(r"(?<=[0-9০-৯])\s+(?=[0-9০-৯])", "", temp)

    return temp

FILE_PATH = "datasets/documents_gemini_TIMEX3" 
# FILE_PATH = "resources/expressions.txt"       # expressions only

with open(f"{FILE_PATH}.html", "r", encoding="utf-8") as f:
    text = f.read()

# expressions file
# with open(f"{FILE_PATH}", "r", encoding="utf-8") as f:
#     texts = f.read().split("\n")

# Extract content inside <text></text> tags
text_list = re.findall(r"<text>(.*?)</text>", text, re.DOTALL)
text_list = [t.strip() for t in text_list]

# remove extra in the expressions
# text_list = [t.strip() for t in texts]

# Normalize
cmap = initialize_charmap(text_list)
preprocessed_texts = [normalizer(t, cmap) for t in text_list]

# Save output
with open(f"{FILE_PATH}_preprocessed.html", "w", encoding='utf-8') as f:
    for t in preprocessed_texts:
        f.write(t + "\n\n")

# # Save expressions output
# with open("resources/expressions_preprocessed.txt", "w", encoding='utf-8') as f:
#     for t in preprocessed_texts:
#         f.write(t + "\n")

# with open(f"{FILE_PATH}_preprocessed_2.html", "w", encoding='utf-8') as f:
#     for t in text_list:
#         f.write(t + "\n\n")