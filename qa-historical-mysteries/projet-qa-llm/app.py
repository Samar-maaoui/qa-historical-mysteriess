import streamlit as st
import mysql.connector
import os
import faiss
from sentence_transformers import SentenceTransformer, CrossEncoder
from dotenv import load_dotenv
from groq import Groq
import numpy as np
import folium
from streamlit_folium import st_folium
import requests
from urllib.parse import quote
from deep_translator import GoogleTranslator
import asyncio
import edge_tts
import secrets
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
import random
import json

load_dotenv()

st.set_page_config(page_title="QA Mystères Historiques", page_icon="🏛️", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=EB+Garamond:ital,wght@0,400;0,600;1,400&display=swap');
.stApp { background: linear-gradient(180deg, #f3e9d2 0%, #ecdfc0 100%); }
html, body, [class*="css"] { font-family: 'EB Garamond', serif; }
.main-title { font-family: 'Cinzel', serif; font-size: 2.6rem; font-weight: 700; color: #6b4423; letter-spacing: 1px; margin-bottom: 0; text-align: center; }
.subtitle { color: #8a6d4f; font-size: 1.15rem; font-style: italic; margin-bottom: 0.5rem; text-align: center; }
.ornament { text-align: center; color: #b08d57; font-size: 1.3rem; margin: 0 0 1.5rem 0; }
.source-badge { display: inline-block; background-color: #d9c39a; color: #5c3d1f; padding: 0.35rem 0.9rem; border-radius: 20px; margin: 0.2rem; font-size: 0.85rem; font-weight: 600; border: 1px solid #b08d57; }
.fait-card { background-color: #fdf6e6; border: 1px solid #c9a96a; border-left: 5px solid #8a6d4f; border-radius: 8px; padding: 1rem; margin: 1rem 0; font-style: italic; color: #5c3d1f; }
section[data-testid="stSidebar"] { background-color: #e8d9b5; }
.stMarkdown, .stText, p, span, label, .stCaption { color: #4a3728; }
.stButton>button { background-color: #8a6d4f; color: #fdf6e6; border-radius: 20px; border: none; font-family: 'EB Garamond', serif; font-weight: 600; transition: transform 0.15s ease; }
.stButton>button:hover { transform: scale(1.03); background-color: #6b4423; }
.hors-corpus { background-color: #fbeae5; border: 1px solid #c97b5f; border-left: 5px solid #a8442a; border-radius: 8px; padding: 1rem; margin: 1rem 0; color: #7a2e1a; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def charger_ressources():
    conn = mysql.connector.connect(host="localhost", user="root", password="", database="llm")
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM chunks ORDER BY position")
    chunks = cursor.fetchall()
    cursor.close()
    conn.close()
    index = faiss.read_index("index.faiss")
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    nli_model = CrossEncoder("cross-encoder/nli-deberta-v3-small")
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return chunks, index, model, reranker, nli_model, client


chunks, index, model, reranker, nli_model, client = charger_ressources()

SUJETS = [
    "Grande Pyramide de Gizeh", "Machu Picchu", "Stonehenge", "Pompéi",
    "Civilisation maya", "Civilisation minoenne", "Île de Pâques", "Pétra",
    "Angkor Vat", "Atlantide", "Nan Madol", "Göbekli Tepe",
    "Olmèques", "Teotihuacan", "Colosse de Rhodes",
    "Carthage", "Guerres puniques", "Hannibal Barca", "Dougga", "El Jem",
    "Utique", "Kerkouane", "Kairouan", "Grande Mosquée de Kairouan", "Dynastie hafside", "Ifriqiya",
    "Protectorat français de Tunisie", "Habib Bourguiba",
    "Mouvement national tunisien", "Indépendance de la Tunisie",
    "Révolution tunisienne",
    "Empire romain", "Jules César", "Alexandre le Grand", "Empire perse",
    "Grèce antique", "Athènes antique", "Sparte", "Égypte antique",
    "Cléopâtre", "Empire byzantin", "Dynastie Han", "Grande Muraille de Chine",
    "Qin Shi Huang",
    "Charlemagne", "Empire carolingien", "Croisades", "Gengis Khan",
    "Empire mongol", "Saladin", "Guerre de Cent Ans", "Jeanne d'Arc",
    "Empire ottoman", "Renaissance italienne", "Route de la soie",
    "Grandes découvertes", "Christophe Colomb", "Empire aztèque", "Empire inca",
    "Traite négrière transatlantique", "Révolution française", "Napoléon Bonaparte",
    "Révolution industrielle", "Colonisation de l'Afrique", "Louis XIV",
    "Marie-Antoinette", "Révolution américaine", "Déclaration d'indépendance des États-Unis",
    "Première Guerre mondiale", "Seconde Guerre mondiale", "Adolf Hitler",
    "Guerre froide", "Décolonisation", "Chute du mur de Berlin",
    "Révolution russe", "Mao Zedong", "Mahatma Gandhi", "Guerre de Sécession",
    "Abraham Lincoln", "Otto von Bismarck", "Unification de l'Allemagne",
]

SITES_COORDS = {
    "Grande Pyramide de Gizeh": (29.9792, 31.1342), "Machu Picchu": (-13.1631, -72.5450),
    "Stonehenge": (51.1789, -1.8262), "Pompéi": (40.7461, 14.4989),
    "Civilisation maya": (20.6843, -88.5678), "Civilisation minoenne": (35.2977, 25.1628),
    "Île de Pâques": (-27.1127, -109.3497), "Pétra": (30.3285, 35.4444),
    "Angkor Vat": (13.4125, 103.8670), "Nan Madol": (6.8425, 158.3336),
    "Göbekli Tepe": (37.2231, 38.9224), "Olmèques": (18.1000, -94.0333),
    "Teotihuacan": (19.6925, -98.8438), "Colosse de Rhodes": (36.4477, 28.2242),
    "Carthage": (36.8531, 10.3233), "Dougga": (36.4222, 9.2192),
    "El Jem": (35.2969, 10.7072), "Utique": (37.0578, 10.0631),
    "Kerkouane": (36.9500, 11.1000), "Kairouan": (35.6786, 10.0963),
    "Empire romain": (41.9028, 12.4964),
    "Athènes antique": (37.9838, 23.7275),
    "Sparte": (37.0810, 22.4234),
    "Empire byzantin": (41.0082, 28.9784),
    "Grande Muraille de Chine": (40.4319, 116.5704),
    "Chute du mur de Berlin": (52.5163, 13.3777),
}

VOIX_PAR_LANGUE = {"fr": "fr-FR-DeniseNeural", "en": "en-US-AriaNeural", "ar": "ar-SA-ZariyahNeural", "es": "es-ES-ElviraNeural"}

FAITS_INTRO = ["📜 Le saviez-vous ?", "🏺 Anecdote du jour", "⚱️ Fragment d'histoire"]

if "historique" not in st.session_state:
    st.session_state.historique = []

if "user_email" not in st.session_state:
    st.session_state.user_email = None

if "quiz_score" not in st.session_state:
    st.session_state.quiz_score = 0
if "quiz_total" not in st.session_state:
    st.session_state.quiz_total = 0
if "quiz_actuel" not in st.session_state:
    st.session_state.quiz_actuel = None
if "quiz_par_question" not in st.session_state:
    st.session_state.quiz_par_question = {}


def generer_et_envoyer_lien(email):
    token = secrets.token_urlsafe(32)
    expiration = datetime.now() + timedelta(minutes=15)
    conn = mysql.connector.connect(host="localhost", user="root", password="", database="llm")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO magic_tokens (token, email, date_expiration) VALUES (%s, %s, %s)", (token, email, expiration))
    cursor.execute("INSERT IGNORE INTO users (email) VALUES (%s)", (email,))
    conn.commit()
    cursor.close()
    conn.close()
    lien = f"http://localhost:8501/?token={token}"
    corps_email = f"Bonjour,\n\nClique sur ce lien pour te connecter au QA System Mysteres Historiques :\n\n{lien}\n\nCe lien expire dans 15 minutes."
    msg = MIMEText(corps_email)
    msg["Subject"] = "Ton lien de connexion - QA System"
    msg["From"] = os.getenv("SMTP_EMAIL")
    msg["To"] = email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as serveur:
            serveur.login(os.getenv("SMTP_EMAIL"), os.getenv("SMTP_APP_PASSWORD"))
            serveur.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Erreur d'envoi : {e}")
        return False


def verifier_token(token):
    conn = mysql.connector.connect(host="localhost", user="root", password="", database="llm")
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM magic_tokens WHERE token = %s", (token,))
    resultat = cursor.fetchone()
    if resultat and not resultat["utilise"] and resultat["date_expiration"] > datetime.now():
        cursor.execute("UPDATE magic_tokens SET utilise = TRUE WHERE token = %s", (token,))
        conn.commit()
        cursor.close()
        conn.close()
        return resultat["email"]
    cursor.close()
    conn.close()
    return None


token_url = st.query_params.get("token")
if token_url and not st.session_state.user_email:
    email_verifie = verifier_token(token_url)
    if email_verifie:
        st.session_state.user_email = email_verifie
        st.query_params.clear()
        st.rerun()


def rechercher_chunks(question, k=10):
    vecteur = model.encode([question], convert_to_numpy=True).astype("float32")
    distances, indices = index.search(vecteur, k)
    return [chunks[i] for i in indices[0]], distances[0]


def reranker_chunks(question, chunks_candidats, top_n=6):
    paires = [[question, c["texte"]] for c in chunks_candidats]
    scores = reranker.predict(paires)
    chunks_scores = list(zip(chunks_candidats, scores))
    chunks_scores.sort(key=lambda x: x[1], reverse=True)
    return [c for c, s in chunks_scores[:top_n]]


def calculer_confiance(distances):
    distance_moyenne = float(np.mean(distances))
    if distance_moyenne < 22:
        return "Élevée", 0.9, "🟢"
    elif distance_moyenne < 30:
        return "Moyenne", 0.6, "🟡"
    else:
        return "Faible (hors corpus probable)", 0.25, "🟠"


def repondre(question):
    chunks_candidats, distances = rechercher_chunks(question, k=10)
    chunks_trouves = reranker_chunks(question, chunks_candidats, top_n=6)
    niveau_confiance, score_barre, emoji = calculer_confiance(distances)
    contexte = "\n\n".join(f"[Source: {c['titre_article']}]\n{c['texte']}" for c in chunks_trouves)
    historique_texte = ""
    for item in st.session_state.historique[-3:]:
        historique_texte += f"Question précédente : {item[0]}\nRéponse précédente : {item[1]}\n\n"
    prompt = f"""Tu es un assistant qui répond à des questions sur des civilisations anciennes.
Voici l'historique récent de la conversation (utilise-le pour comprendre les questions de suivi comme "et pour X ?") :

{historique_texte if historique_texte else "(Aucun historique, c'est la première question)"}

Réponds à la NOUVELLE question en te basant UNIQUEMENT sur le contexte fourni ci-dessous.
Si la réponse ne se trouve pas dans le contexte, dis clairement que tu ne sais pas.

Contexte :
{contexte}

Nouvelle question : {question}

Réponse :"""
    response = client.chat.completions.create(model="openai/gpt-oss-20b", max_tokens=700, messages=[{"role": "user", "content": prompt}])
    sources_uniques = list(set(c["titre_article"] for c in chunks_trouves))
    return response.choices[0].message.content, sources_uniques, niveau_confiance, score_barre, emoji, chunks_trouves


@st.cache_data(show_spinner=False)
def recuperer_image(titre_article):
    recherches_forcees = {"El Jem": "Amphitheatre of El Jem"}
    terme_recherche = recherches_forcees.get(titre_article, titre_article)
    try:
        url = "https://commons.wikimedia.org/w/api.php"
        params = {"action": "query", "format": "json", "prop": "imageinfo", "generator": "search", "gsrsearch": terme_recherche, "gsrlimit": 1, "gsrnamespace": 6, "iiprop": "url"}
        r = requests.get(url, params=params, timeout=5, headers={"User-Agent": "ProjetQA-LLM/1.0"})
        data = r.json()
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            imageinfo = page.get("imageinfo")
            if imageinfo:
                return imageinfo[0]["url"]
    except Exception:
        pass
    try:
        url = f"https://fr.wikipedia.org/api/rest_v1/page/summary/{quote(titre_article)}"
        r = requests.get(url, timeout=5, headers={"User-Agent": "ProjetQA-LLM/1.0"})
        return r.json().get("thumbnail", {}).get("source")
    except Exception:
        return None


def reponse_generale(question):
    prompt = f"Réponds à cette question avec tes connaissances générales, de façon concise : {question}"
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b", max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


@st.cache_data(show_spinner=False)
def traduire_texte(texte, code_langue):
    if code_langue == "fr":
        return texte
    try:
        return GoogleTranslator(source="fr", target=code_langue).translate(texte)
    except Exception:
        return "Traduction indisponible pour le moment."


async def generer_audio_async(texte, voix):
    communicate = edge_tts.Communicate(texte, voix)
    audio_bytes = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]
    return audio_bytes


@st.cache_data(show_spinner=False)
def generer_audio(texte, code_langue):
    voix = VOIX_PAR_LANGUE.get(code_langue, "fr-FR-DeniseNeural")
    return asyncio.run(generer_audio_async(texte, voix))


def verifier_fidelite(reponse, chunks_utilises):
    phrases = [p.strip() for p in reponse.split(".") if len(p.strip()) > 10]
    if not phrases or not chunks_utilises:
        return 1.0, []
    resultats = []
    nb_supportees = 0
    for phrase in phrases:
        paires = [[c["texte"], phrase] for c in chunks_utilises]
        scores = nli_model.predict(paires)
        meilleur_entailment = float(max(s[1] for s in scores))
        supportee = meilleur_entailment > 0.5
        if supportee:
            nb_supportees += 1
        resultats.append((phrase, supportee, round(meilleur_entailment, 2)))
    return nb_supportees / len(phrases), resultats


def verifier_fidelite_api(reponse, chunks_utilises):
    phrases = [p.strip() for p in reponse.split(".") if len(p.strip()) > 10]
    if not phrases or not chunks_utilises:
        return 1.0, []
    hf_token = os.getenv("HF_TOKEN")
    headers = {"Authorization": f"Bearer {hf_token}"}
    api_url = "https://router.huggingface.co/hf-inference/models/MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
    resultats = []
    nb_supportees = 0
    for phrase in phrases:
        meilleur_score = 0.0
        for c in chunks_utilises:
            payload = {"inputs": c["texte"][:800], "parameters": {"candidate_labels": [phrase], "hypothesis_template": "{}"}}
            try:
                r = requests.post(api_url, headers=headers, json=payload, timeout=15)
                data = r.json()
                if isinstance(data, list) and len(data) > 0 and "score" in data[0]:
                    meilleur_score = max(meilleur_score, data[0]["score"])
            except Exception:
                pass
        supportee = meilleur_score > 0.5
        if supportee:
            nb_supportees += 1
        resultats.append((phrase, supportee, round(meilleur_score, 2)))
    return (nb_supportees / len(phrases) if phrases else 1.0), resultats


def afficher_traduction_et_audio(texte, cle):
    langues = {"Français (original)": "fr", "English": "en", "العربية": "ar", "Español": "es"}
    choix = st.selectbox("🌐 Langue", list(langues.keys()), key=f"lang_{cle}")
    code = langues[choix]
    if code != "fr":
        with st.spinner("Traduction en cours..."):
            texte_affiche = traduire_texte(texte, code)
        st.info(texte_affiche)
    else:
        texte_affiche = texte
    if st.button("🔊 Écouter", key=f"tts_{cle}"):
        with st.spinner("Génération audio..."):
            audio = generer_audio(texte_affiche, code)
        st.audio(audio, format="audio/mp3")


def afficher_verification_fidelite(reponse, chunks_utilises, cle):
    methode = st.radio("Méthode de vérification", ["Modèle local (rapide)", "API Hugging Face"], key=f"methode_{cle}", horizontal=True)
    if st.button("🔎 Vérifier la fidélité au contexte", key=f"fid_{cle}"):
        with st.spinner("Analyse phrase par phrase..."):
            if methode == "Modèle local (rapide)":
                taux, details = verifier_fidelite(reponse, chunks_utilises)
            else:
                taux, details = verifier_fidelite_api(reponse, chunks_utilises)
        couleur = "🟢" if taux >= 0.8 else "🟡" if taux >= 0.5 else "🟠"
        st.write(f"**{couleur} Fidélité au contexte : {taux*100:.0f}%** des phrases sont directement soutenues par les sources")
        for phrase, supportee, score in details:
            icone = "✅" if supportee else "⚠️"
            st.caption(f"{icone} {phrase}. *(score : {score})*")


def afficher_images(sources_uniques):
    images = [(s, recuperer_image(s)) for s in sources_uniques]
    images = [(s, url) for s, url in images if url]
    if images:
        st.write("**🖼️ Illustrations**")
        cols = st.columns(len(images))
        for col, (nom, url) in zip(cols, images):
            with col:
                st.image(url, caption=nom, use_container_width=True)


def afficher_carte(sources_uniques, cle):
    coords_sources = [(s, SITES_COORDS[s]) for s in sources_uniques if s in SITES_COORDS]
    if coords_sources:
        st.write("**📍 Localisation**")
        lat_moy = sum(c[1][0] for c in coords_sources) / len(coords_sources)
        lon_moy = sum(c[1][1] for c in coords_sources) / len(coords_sources)
        mini_carte = folium.Map(location=[lat_moy, lon_moy], zoom_start=4, tiles="CartoDB positron")
        for nom, (lat, lon) in coords_sources:
            folium.Marker(location=[lat, lon], popup=nom, tooltip=nom, icon=folium.Icon(color="orange", icon="info-sign")).add_to(mini_carte)
        st_folium(mini_carte, width=700, height=300, key=cle)


def afficher_fait_aleatoire():
    if st.sidebar.button("🎲 Anecdote historique aléatoire"):
        chunk = random.choice(chunks)
        intro = random.choice(FAITS_INTRO)
        extrait = chunk["texte"][:280].rsplit(" ", 1)[0] + "..."
        st.sidebar.markdown(
            f'<div class="fait-card"><strong>{intro}</strong><br>{extrait}<br><em>— {chunk["titre_article"]}</em></div>',
            unsafe_allow_html=True
        )


def generer_question_quiz():
    chunk = random.choice(chunks)
    prompt = f"""À partir de cet extrait, génère une question à choix multiples (4 options, une seule correcte).

Extrait sur "{chunk['titre_article']}" :
{chunk['texte'][:600]}

Réponds STRICTEMENT en JSON, sans texte autour :
{{"question": "...", "options": ["...", "...", "...", "..."], "index_correct": 0, "explication": "..."}}"""
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b", max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    try:
        texte = response.choices[0].message.content.strip()
        texte = texte.replace("```json", "").replace("```", "").strip()
        data = json.loads(texte)
        data["source"] = chunk["titre_article"]
        return data
    except Exception:
        return None


def afficher_quiz():
    st.sidebar.divider()
    st.sidebar.subheader(f"🎮 Quiz — Score : {st.session_state.quiz_score}/{st.session_state.quiz_total}")

    if st.sidebar.button("🎲 Nouvelle question"):
        with st.spinner("Génération de la question..."):
            st.session_state.quiz_actuel = generer_question_quiz()

    q = st.session_state.quiz_actuel
    if q:
        st.sidebar.write(f"**{q['question']}**")
        choix = st.sidebar.radio("Choisis ta réponse :", q["options"], key=f"quiz_radio_{id(q)}")

        if st.sidebar.button("✅ Valider"):
            st.session_state.quiz_total += 1
            index_choisi = q["options"].index(choix)
            if index_choisi == q["index_correct"]:
                st.session_state.quiz_score += 1
                st.sidebar.success(f"Bonne réponse ! {q['explication']}")
            else:
                bonne_reponse = q["options"][q["index_correct"]]
                st.sidebar.error(f"Faux — la bonne réponse était : {bonne_reponse}\n\n{q['explication']}")
            st.sidebar.caption(f"Source : {q['source']}")
            st.session_state.quiz_actuel = None


def generer_question_quiz_contextuel(chunks_source):
    chunk = random.choice(chunks_source)
    prompt = f"""À partir de cet extrait, génère une question à choix multiples (4 options, une seule correcte).

Extrait sur "{chunk['titre_article']}" :
{chunk['texte'][:600]}

Réponds STRICTEMENT en JSON, sans texte autour :
{{"question": "...", "options": ["...", "...", "...", "..."], "index_correct": 0, "explication": "..."}}"""
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b", max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    try:
        texte = response.choices[0].message.content.strip()
        texte = texte.replace("```json", "").replace("```", "").strip()
        data = json.loads(texte)
        data["source"] = chunk["titre_article"]
        return data
    except Exception:
        return None


def afficher_quiz_contextuel(chunks_source, cle):
    if st.button("🎮 Commencer un quiz sur ce sujet", key=f"quiz_start_{cle}"):
        with st.spinner("Génération de la question..."):
            resultat = generer_question_quiz_contextuel(chunks_source)
        if resultat is None:
            st.warning("La génération de la question a échoué (format inattendu). Réessaie en cliquant à nouveau.")
        st.session_state.quiz_par_question[cle] = resultat

    q = st.session_state.quiz_par_question.get(cle)
    if q:
        st.write(f"**{q['question']}**")
        choix = st.radio("Ta réponse :", q["options"], key=f"quiz_radio_ctx_{cle}")
        if st.button("✅ Valider", key=f"quiz_valid_{cle}"):
            index_choisi = q["options"].index(choix)
            if index_choisi == q["index_correct"]:
                st.success(f"Bonne réponse ! {q['explication']}")
            else:
                bonne = q["options"][q["index_correct"]]
                st.error(f"Faux — la bonne réponse était : {bonne}\n\n{q['explication']}")
            st.caption(f"Source : {q['source']}")
            del st.session_state.quiz_par_question[cle]


# --- Écran de connexion ---
if not st.session_state.user_email:
    st.markdown('<p class="main-title">🏛️ QA System — Mystères Historiques</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Connecte-toi avec un lien magique envoyé par email.</p>', unsafe_allow_html=True)
    st.markdown('<p class="ornament">❦ ⚜ ❦</p>', unsafe_allow_html=True)
    email_saisi = st.text_input("Ton adresse email")
    if st.button("📧 Envoyer le lien de connexion"):
        if "@" in email_saisi and "." in email_saisi:
            with st.spinner("Envoi en cours..."):
                succes = generer_et_envoyer_lien(email_saisi)
            if succes:
                st.success("Email envoyé ! Vérifie ta boîte de réception et clique sur le lien.")
        else:
            st.warning("Merci d'entrer une adresse email valide.")
    st.stop()


with st.sidebar:
    st.write(f"👤 Connecté : {st.session_state.user_email}")
    if st.button("🚪 Se déconnecter"):
        st.session_state.user_email = None
        st.rerun()
    st.divider()
    st.header("📚 Sujets disponibles")
    for sujet in SUJETS:
        st.write(f"• {sujet}")
    st.divider()
    afficher_fait_aleatoire()
    afficher_quiz()
    st.divider()
    st.header("🕘 Historique des questions")
    if st.session_state.historique:
        for i, item in enumerate(reversed(st.session_state.historique), 1):
            q_prec, r_prec = item[0], item[1]
            titre = f"{i}. {q_prec[:40]}..." if len(q_prec) > 40 else f"{i}. {q_prec}"
            with st.expander(titre):
                st.write(f"**Question :** {q_prec}")
                st.write(f"**Réponse :** {r_prec}")
    else:
        st.caption("Aucune question posée pour le moment.")
    st.divider()
    if st.button("🗑️ Effacer l'historique"):
        st.session_state.historique = []
        st.rerun()
    st.caption("Corpus : Wikipedia | Recherche : FAISS + Reranking | LLM : Groq | Fidélité : NLI")

st.markdown('<p class="main-title">🏛️ QA System — Mystères Historiques</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Pose une question, ou une question de suivi comme "et pour Machu Picchu ?"</p>', unsafe_allow_html=True)
st.markdown('<p class="ornament">❦ ⚜ ❦</p>', unsafe_allow_html=True)

for i, item in enumerate(st.session_state.historique):
    q_prec, r_prec, sources_prec, confiance_prec, score_prec, emoji_prec, chunks_prec = item
    with st.chat_message("user"):
        st.write(q_prec)
    with st.chat_message("assistant"):
        st.write(r_prec)
        afficher_traduction_et_audio(r_prec, cle=f"hist_{i}")
        afficher_verification_fidelite(r_prec, chunks_prec, cle=f"hist_{i}")
        col_a, col_b = st.columns(2)
        with col_a:
            st.write(f"**{emoji_prec} Confiance : {confiance_prec}**")
            st.progress(score_prec)
        with col_b:
            badges = "".join(f'<span class="source-badge">{s}</span>' for s in sources_prec)
            st.markdown(badges, unsafe_allow_html=True)
        if score_prec >= 0.6:
            afficher_images(sources_prec)
            afficher_carte(sources_prec, cle=f"map_historique_{i}")
        afficher_quiz_contextuel(chunks_prec, cle=f"hist_{i}")

question = st.chat_input("Pose ta question ici...")

if question:
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        with st.spinner("Recherche et reclassement des sources..."):
            reponse, sources_uniques, confiance, score_barre, emoji, chunks_trouves = repondre(question)
        st.write(reponse)
        afficher_traduction_et_audio(reponse, cle=f"new_{len(st.session_state.historique)}")
        afficher_verification_fidelite(reponse, chunks_trouves, cle=f"new_{len(st.session_state.historique)}")
        col_a, col_b = st.columns(2)
        with col_a:
            st.write(f"**{emoji} Confiance : {confiance}**")
            st.progress(score_barre)
        with col_b:
            badges = "".join(f'<span class="source-badge">{s}</span>' for s in sources_uniques)
            st.markdown(badges, unsafe_allow_html=True)
        if score_barre >= 0.6:
            afficher_images(sources_uniques)
            afficher_carte(sources_uniques, cle=f"map_nouvelle_{len(st.session_state.historique)}")
        afficher_quiz_contextuel(chunks_trouves, cle=f"new_{len(st.session_state.historique)}")
        if score_barre < 0.6:
            if st.button("🌐 Obtenir une réponse générale du LLM (hors corpus, non vérifiée)", key=f"hybride_{len(st.session_state.historique)}"):
                with st.spinner("Génération..."):
                    reponse_hors_corpus = reponse_generale(question)
                st.markdown(
                    f'<div class="hors-corpus">⚠️ <strong>Réponse hors corpus, non sourcée ni vérifiée</strong><br>{reponse_hors_corpus}</div>',
                    unsafe_allow_html=True
                )

    st.session_state.historique.append((question, reponse, sources_uniques, confiance, score_barre, emoji, chunks_trouves))