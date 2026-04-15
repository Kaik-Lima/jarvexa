import requests

# Substitua pelas suas chaves reais
GEMINI_KEY = "SUA_API_KEY_GEMINI"
GROQ_KEY = "SUA_API_KEY_GROQ"

def testar_gemini():
    print("Testando Gemini...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": "Olá"}]}]}, timeout=10)
        print(f"Status Gemini: {res.status_code}")
        print(f"Resposta: {res.json()['candidates'][0]['content']['parts'][0]['text']}\n")
    except Exception as e:
        print(f"Erro no Gemini: {e}\n")

def testar_groq():
    print("Testando Groq...")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_KEY}"}
    try:
        res = requests.post(url, headers=headers, json={"model": "llama3-8b-8192", "messages": [{"role": "user", "content": "Olá"}]}, timeout=10)
        print(f"Status Groq: {res.status_code}")
        print(f"Resposta: {res.json()['choices'][0]['message']['content']}\n")
    except Exception as e:
        print(f"Erro no Groq: {e}\n")

testar_gemini()
testar_groq()