from django.shortcuts import render
from .analysis import detect_repair_cues

def home(request):
    result = None
    if request.method == "POST":
        instruction = request.POST.get("instruction", "").strip()
        if instruction:
            cues = detect_repair_cues(instruction)
            if cues:
                result = "Potential repair cues detected: " + ", ".join(cues)
            else:
                result = "No repair cues from our list were detected."
            result += " No AI agent action was executed."
        else:
            result = "Please enter an instruction."
    return render(request, "core/home.html", {"result": result})
