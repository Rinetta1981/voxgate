import csv
from core.analysis import detect_repair_cues

counts = {"TP": 0, "FP": 0, "FN": 0, "TN": 0}

with open("data/waitwise_cases.csv", newline="", encoding="utf-8") as file:
    for row in csv.DictReader(file):
        gold = int(row["revises_prior_instruction"])
        predicted = int(bool(detect_repair_cues(row["transcript"])))
        if gold == 1 and predicted == 1:
            counts["TP"] += 1
        elif gold == 0 and predicted == 1:
            counts["FP"] += 1
        elif gold == 1 and predicted == 0:
            counts["FN"] += 1
        else:
            counts["TN"] += 1

precision = counts["TP"] / (counts["TP"] + counts["FP"]) if counts["TP"] + counts["FP"] else 0
recall = counts["TP"] / (counts["TP"] + counts["FN"]) if counts["TP"] + counts["FN"] else 0
print(counts)
print(f"Precision: {precision:.2f}")
print(f"Recall: {recall:.2f}")
