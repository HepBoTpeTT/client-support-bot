import os
import openai
import config

api_key = config.OPENAI_API_KEY
if not api_key:
    raise RuntimeError("OPENAI_API_KEY is not set")

client = openai.OpenAI(api_key=api_key)

def ask_gpt(context_blocks, question, history=None):
    context = "\n\n".join([f"Источник: {url}\n{content}" for url, content in context_blocks])
    messages = [{"role": "system", "content": "Ты — дружелюбный и профессиональный ассистент отеля."}]

    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": f"""
            Используй информацию ниже, чтобы ответить на вопрос клиента о гостинице, услугах, ценах, правилах и т.д. можешь давать не точную информацию, а делать выводы на основе данных
            Если есть полезные ссылки, контакты или адрес — обязательно укажи.

            === Информация с сайта отеля ===
            {context}

            === Вопрос клиента ===
            {question}
        """})

    response = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=messages,
        temperature=0.7
    )
    return response.choices[0].message.content