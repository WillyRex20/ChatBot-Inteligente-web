# Chatbot Inteligente con Documentos

Proyecto academico de la Semana 13: Tecnologias Base, IA, recuperacion semantica y web.

## Descripcion

Este proyecto implementa un chatbot inteligente capaz de consultar documentos PDF, TXT y DOCX. El sistema procesa el texto, crea embeddings, almacena la informacion en una base vectorial FAISS y responde preguntas mediante LangChain.

La aplicacion puede ejecutarse en localhost e incluye una interfaz web con HTML, CSS y JavaScript.

## Arquitectura

```text
Usuario
  -> Pagina Web HTML + JavaScript
  -> Interfaz del Chatbot
  -> Flask API
  -> LangChain
  -> FAISS
  -> Documento PDF/TXT/DOCX
  -> Modelo de IA
```

## Tecnologias

- Python
- Flask
- LangChain
- FAISS
- HuggingFace Transformers
- Sentence Transformers
- HTML
- CSS
- JavaScript
- Google Colab
- GitHub

## Estructura

```text
chatbot-rag/
├── app/
│   ├── chatbot.py
│   ├── config.py
│   ├── document_loader.py
│   ├── embeddings.py
│   ├── main.py
│   └── vectorstore.py
├── data/
│   └── documento_demo.txt
├── web/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── requirements.txt
├── README.md
└── notebook.ipynb
```

## Instalacion local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

Luego abrir:

```text
http://127.0.0.1:5000
```

## Uso

1. Ejecutar el servidor Flask.
2. Abrir la pagina web.
3. Subir uno o varios documentos PDF, TXT o DOCX.
4. Esperar el mensaje de procesamiento correcto.
5. Escribir preguntas sobre el contenido del documento.
6. Revisar la respuesta y las fuentes recuperadas.

Tambien se puede usar el boton `Indexar carpeta data/` para probar el documento de demostracion.

La carga soporta documentos de hasta 500 MB por solicitud. Los documentos pesados pueden tardar mas porque el sistema debe extraer texto, dividirlo, crear embeddings y guardar el indice FAISS.

Los PDF deben tener texto seleccionable. Si el PDF es escaneado o contiene solo imagenes, primero necesita OCR para que el chatbot pueda leerlo.

Si ocurre un problema, la web muestra una alerta clara indicando el motivo: formato no permitido, archivo demasiado pesado, servidor no disponible o error de procesamiento.

## Modelo de IA

Por defecto, el proyecto usa embeddings locales de HuggingFace y un respondedor rapido basado en los fragmentos recuperados del documento. Esto evita respuestas inventadas y acelera la respuesta en localhost.

```text
sentence-transformers/all-MiniLM-L6-v2
```

Si se configura la variable `OPENAI_API_KEY`, el sistema usa OpenAI mediante LangChain para respuestas mas naturales y similares a ChatGPT:

```bash
set OPENAI_API_KEY=tu_clave
python -m app.main
```

Tambien puedes copiar `.env.example` como `.env` y colocar ahi la clave:

```text
OPENAI_API_KEY=tu_clave
HF_HUB_OFFLINE=1
```

Para respuestas mas profesionales y parecidas a ChatGPT, se recomienda usar OpenAI. El modo local con HuggingFace funciona sin pagos, pero es mas limitado y puede dar respuestas menos naturales.

## Calidad de respuestas

El proyecto no entrena un modelo desde cero. Usa una arquitectura RAG: lee el documento, crea embeddings, recupera fragmentos relevantes y genera una respuesta basada en ese contenido.

- Modo local: rapido, gratuito y fiel al documento; genera respuestas extractivas y resumentes.
- Modo OpenAI: mas natural, conversacional y parecido a ChatGPT; requiere `OPENAI_API_KEY`.

En ambos modos, si la informacion no aparece en el documento, el chatbot debe indicarlo claramente.

## Funcionalidades obligatorias

- Lectura de PDF, TXT y DOCX.
- Procesamiento textual.
- Creacion de embeddings.
- Busqueda semantica.
- Base vectorial FAISS.
- Integracion con LangChain.
- Interfaz web.
- Historial de chat durante la sesion.
- Carga dinamica de multiples documentos.
- Ejecucion local por localhost.

## Definicion de terminos y aporte personal

### LangChain

LangChain es un framework que permite organizar aplicaciones basadas en modelos de lenguaje. En este proyecto lo entiendo como el coordinador principal del chatbot, porque conecta la pregunta del usuario, la memoria conversacional, el recuperador semantico, la base vectorial y el modelo de IA.

### Embeddings

Los embeddings son representaciones numericas del significado de un texto. Mi comprension es que convierten palabras, parrafos o documentos en vectores que una computadora puede comparar. Gracias a ellos, el sistema no busca solo palabras exactas, sino ideas relacionadas.

### Busqueda semantica

La busqueda semantica es una forma de recuperar informacion considerando el significado de la consulta. En este proyecto, si el usuario pregunta con palabras diferentes a las del documento, FAISS puede encontrar fragmentos relacionados porque compara embeddings y no solo coincidencias literales.

## Evidencias para entrega

Para completar el informe final en formato APA 7, se recomienda incluir capturas de:

- Notebook ejecutado en Google Colab.
- Repositorio publicado en GitHub.
- Interfaz web funcionando en localhost o en internet.
- Carga de documento exitosa.
- Pregunta respondida por el chatbot.

## Referencias en formato APA 7

Facebook AI Similarity Search. (2024). *FAISS documentation*. https://faiss.ai/

Hugging Face. (2024). *Transformers documentation*. https://huggingface.co/docs/transformers

LangChain. (2024). *LangChain documentation*. https://python.langchain.com/

OpenAI. (2024). *OpenAI API documentation*. https://platform.openai.com/docs
