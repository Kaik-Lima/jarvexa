import os
import logging
import ask_sdk_core.utils as ask_utils
import requests
from datetime import date

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 🔑 COLOQUE SUAS CHAVES AQUI
GEMINI_API_KEY = "SUA_API_KEY_GEMINI"
GROQ_API_KEY = "SUA_API_KEY_GROQ"

# Variável global para rastrear o dia em que a cota do Gemini acabou
# Nota: A AWS Lambda pode resetar essa variável em caso de "Cold Start".
gemini_exhausted_date = None

# ================================
# 🧠 IA - GEMINI
# ================================
def usar_gemini(prompt):
    # Atualizado para o modelo 1.5-flash, mais rápido e eficiente
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

    body = {
        "contents": [
            {
                "parts": [{"text": f"Responda em português, de forma clara, conversacional e em até 400 caracteres: {prompt}"}]
            }
        ]
    }

    response = requests.post(url, json=body)
    
    # Se a cota diária acabar, a API retorna 429
    if response.status_code == 429:
        raise ValueError("QUOTA_EXCEEDED")
        
    # Lança erro para outros problemas (500, 400, etc)
    response.raise_for_status()
    
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


# ================================
# ⚡ IA - GROQ (FALLBACK)
# ================================
def usar_groq(prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    body = {
        "model": "llama3-8b-8192",
        "messages": [
            {
                "role": "user",
                "content": f"Responda em português, de forma clara, conversacional e em até 400 caracteres: {prompt}"
            }
        ]
    }

    response = requests.post(url, headers=headers, json=body)
    response.raise_for_status()
    data = response.json()

    return data["choices"][0]["message"]["content"]


# ================================
# 🔁 ORQUESTRADOR (GEMINI → GROQ POR DIA)
# ================================
def perguntar_ia(prompt):
    global gemini_exhausted_date
    hoje = date.today()

    # Se a cota já estourou hoje, vai direto para o Groq
    if gemini_exhausted_date == hoje:
        logger.info("Cota do Gemini excedida para hoje. Usando Groq como protagonista.")
        return usar_groq(prompt)

    try:
        return usar_gemini(prompt)
    except ValueError as e:
        if str(e) == "QUOTA_EXCEEDED":
            logger.warning("Cota do Gemini (429) atingida! Mudando para Groq pelo resto do dia.")
            gemini_exhausted_date = hoje # Marca o dia de hoje como esgotado
            return usar_groq(prompt)
        return usar_groq(prompt) # Fallback de segurança
    except Exception as e:
        logger.error(f"Erro no Gemini (não relacionado a cota): {e}")
        # Em caso de instabilidade normal, tenta o Groq mas não bloqueia o Gemini pro resto do dia
        return usar_groq(prompt)


# ================================
# 🎯 HANDLERS DA ALEXA
# ================================
class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        speak_output = "Olá! Qual a sua pergunta?"
        return (
            handler_input.response_builder.speak(speak_output)
            .ask(speak_output)
            .response
        )


class GptQueryIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("GptQueryIntent")(handler_input)

    def handle(self, handler_input):
        query = handler_input.request_envelope.request.intent.slots["query"].value
        
        resposta = generate_gpt_response(query)

        return (
            handler_input.response_builder.speak(resposta)
            .ask("Você pode fazer outra pergunta ou dizer sair.")
            .response
        )


# ================================
# 🧠 FUNÇÃO PRINCIPAL
# ================================
def generate_gpt_response(query):
    try:
        resposta = perguntar_ia(query)
        # Limite da Alexa para uma fala fluida
        return resposta[:400]
    except Exception as e:
        logger.error(f"Erro geral: {e}")
        return "Desculpe, meus servidores de inteligência artificial estão indisponíveis no momento."


class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        speak_output = "Você pode me fazer qualquer pergunta."
        return (
            handler_input.response_builder.speak(speak_output)
            .ask(speak_output)
            .response
        )


class CancelOrStopIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or \
               ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input)

    def handle(self, handler_input):
        speak_output = "Até logo!"
        return handler_input.response_builder.speak(speak_output).response


class SessionEndedRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        return handler_input.response_builder.response


class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        return True

    def handle(self, handler_input, exception):
        logger.error(exception, exc_info=True)
        speak_output = "Desculpe, ocorreu um erro interno na skill."
        return (
            handler_input.response_builder.speak(speak_output)
            .ask("Pode repetir?")
            .response
        )


# ================================
# 🚀 BUILD FINAL
# ================================
sb = SkillBuilder()

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(GptQueryIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())

sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()