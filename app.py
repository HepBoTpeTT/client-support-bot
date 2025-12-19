# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, render_template
from universal_parser import scrape_recursive, save_to_db, init_db
from semantic import embed_pages, search_similar
from openai_helper import ask_gpt
import config

app = Flask(__name__, template_folder='templates')

@app.before_first_request
def setup():
    init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/parse', methods=['POST'])
def parse_site():
    data = request.get_json(silent=True) or {}
    url = data.get("url")

    if not url:
        return jsonify({"error": "URL не указан"}), 400

    try:
        pages = scrape_recursive(url, max_pages=config.MAX_PAGES)
        if not pages:
            return jsonify({"error": "Не удалось получить содержимое страниц. Проверьте ссылку."}), 400

        save_to_db(pages)
        embed_pages()

        return jsonify(
            {
                "message": f"✅ Успешно спарсено {len(pages)} страниц и обновлены эмбеддинги.",
                "pages": len(pages),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json(silent=True) or {}
    question = data.get("question")

    if not question:
        return jsonify({"error": "Вопрос не указан"}), 400

    try:
        results = search_similar(question)

        if not results:
            return jsonify(
                {
                    "answer": "❌ Ничего не найдено по базе. Попробуйте сначала спарсить сайт.",
                    "matches": 0,
                }
            )

        context = [(url, content[:1000]) for _, url, content in results]
        answer = ask_gpt(context, question)

        return jsonify(
            {
                "answer": answer,
                "matches": len(results),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=config.FLASK_DEBUG)
