from django.shortcuts import render

def home(request):
    result = None
    if request.method == "POST":
        instruction = request.POST.get("instruction", "").strip()
        if instruction:
            result = "Demo: Instruction received. No AI agent action was executed."
        else:
            result = "Please enter an instruction."
    return render(request, "core/home.html", {"result": result})
