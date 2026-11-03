"""Static knowledge about the corpus topics: English names, eras, map coordinates, kid emojis."""

ERAS = ["Prehistory", "Antiquity", "Middle Ages", "Modern era"]

# kind: "site" = the place itself; "place" = a place linked to the topic; None = no map pin
_T = {
    "Grande Pyramide de Gizeh": ("Great Pyramid of Giza", "🔺", "Antiquity", "c. 2560 BC", "Africa", 29.9792, 31.1342, "site", False),
    "Machu Picchu": ("Machu Picchu", "⛰️", "Middle Ages", "c. 1450", "South America", -13.1631, -72.5450, "site", False),
    "Stonehenge": ("Stonehenge", "⭕", "Prehistory", "c. 3000 BC", "Europe", 51.1789, -1.8262, "site", False),
    "Pompéi": ("Pompeii", "🌋", "Antiquity", "AD 79", "Europe", 40.7461, 14.4989, "site", False),
    "Civilisation maya": ("Maya civilization", "🗿", "Antiquity", "c. 250–900", "North America", 20.6843, -88.5678, "site", False),
    "Civilisation minoenne": ("Minoan civilization", "🐂", "Antiquity", "c. 2700–1450 BC", "Europe", 35.2977, 25.1628, "site", False),
    "Île de Pâques": ("Easter Island", "🗿", "Middle Ages", "c. 1250–1500", "Oceania", -27.1127, -109.3497, "site", False),
    "Pétra": ("Petra", "🏜️", "Antiquity", "c. 300 BC", "Asia", 30.3285, 35.4444, "site", False),
    "Angkor Vat": ("Angkor Wat", "🛕", "Middle Ages", "12th century", "Asia", 13.4125, 103.8670, "site", False),
    "Atlantide": ("Atlantis", "🌊", "Antiquity", "legend (Plato)", "Legend", None, None, None, False),
    "Nan Madol": ("Nan Madol", "🏝️", "Middle Ages", "c. 1200–1500", "Oceania", 6.8425, 158.3336, "site", False),
    "Göbekli Tepe": ("Göbekli Tepe", "🏺", "Prehistory", "c. 9500 BC", "Asia", 37.2231, 38.9224, "site", False),
    "Olmèques": ("Olmecs", "🗿", "Antiquity", "c. 1200–400 BC", "North America", 18.1000, -94.0333, "site", False),
    "Teotihuacan": ("Teotihuacan", "🔺", "Antiquity", "c. 100 BC–550", "North America", 19.6925, -98.8438, "site", False),
    "Colosse de Rhodes": ("Colossus of Rhodes", "🏛️", "Antiquity", "c. 280 BC", "Europe", 36.4477, 28.2242, "site", False),
    "Carthage": ("Carthage", "⚓", "Antiquity", "814 BC–AD 698", "Africa", 36.8531, 10.3233, "site", False),
    "Guerres puniques": ("Punic Wars", "⚔️", "Antiquity", "264–146 BC", "Africa", None, None, None, True),
    "Hannibal Barca": ("Hannibal Barca", "🐘", "Antiquity", "247–183 BC", "Africa", None, None, None, False),
    "Dougga": ("Dougga", "🏛️", "Antiquity", "Numidian and Roman", "Africa", 36.4222, 9.2192, "site", False),
    "El Jem": ("El Jem", "🏟️", "Antiquity", "c. AD 238", "Africa", 35.2969, 10.7072, "site", False),
    "Utique": ("Utica", "⚓", "Antiquity", "c. 1100 BC", "Africa", 37.0578, 10.0631, "site", False),
    "Kerkouane": ("Kerkouane", "🏺", "Antiquity", "6th–3rd century BC", "Africa", 36.9500, 11.1000, "site", False),
    "Kairouan": ("Kairouan", "🕌", "Middle Ages", "founded AD 670", "Africa", 35.6786, 10.0963, "site", False),
    "Grande Mosquée de Kairouan": ("Great Mosque of Kairouan", "🕌", "Middle Ages", "AD 670, rebuilt 9th century", "Africa", 35.6817, 10.0986, "site", False),
    "Dynastie hafside": ("Hafsid dynasty", "👑", "Middle Ages", "1229–1574", "Africa", 36.8065, 10.1815, "place", False),
    "Ifriqiya": ("Ifriqiya", "🧭", "Middle Ages", "7th–16th century", "Africa", 35.6786, 10.0963, "place", False),
    "Protectorat français de Tunisie": ("French protectorate of Tunisia", "🚩", "Modern era", "1881–1956", "Africa", 36.8092, 10.1346, "place", False),
    "Habib Bourguiba": ("Habib Bourguiba", "🎩", "Modern era", "1903–2000", "Africa", 35.7643, 10.8113, "place", False),
    "Mouvement national tunisien": ("Tunisian national movement", "✊", "Modern era", "1920–1956", "Africa", 36.8065, 10.1815, "place", False),
    "Indépendance de la Tunisie": ("Independence of Tunisia", "🎉", "Modern era", "20 March 1956", "Africa", 36.8065, 10.1815, "place", False),
    "Révolution tunisienne": ("Tunisian revolution", "🕊️", "Modern era", "2010–2011", "Africa", 35.0382, 9.4858, "place", True),
    # extra topics from the extended corpus plan (only used if they are added to the corpus)
    "Empire romain": ("Roman Empire", "🦅", "Antiquity", "27 BC–AD 476", "Europe", 41.9028, 12.4964, "place", False),
    "Athènes antique": ("Ancient Athens", "🏛️", "Antiquity", "c. 500–300 BC", "Europe", 37.9838, 23.7275, "place", False),
    "Sparte": ("Sparta", "🛡️", "Antiquity", "c. 900–200 BC", "Europe", 37.0810, 22.4234, "place", False),
    "Empire byzantin": ("Byzantine Empire", "⛪", "Middle Ages", "330–1453", "Europe", 41.0082, 28.9784, "place", False),
    "Grande Muraille de Chine": ("Great Wall of China", "🧱", "Antiquity", "from c. 220 BC", "Asia", 40.4319, 116.5704, "site", False),
    "Chute du mur de Berlin": ("Fall of the Berlin Wall", "🧱", "Modern era", "1989", "Europe", 52.5163, 13.3777, "place", False),
}

TOPICS = {}
for fr, (en, emoji, era, year, region, lat, lon, kind, sensitive) in _T.items():
    TOPICS[fr] = {
        "en": en, "emoji": emoji, "era": era, "year": year, "region": region,
        "lat": lat, "lon": lon, "kind": kind, "sensitive": sensitive,
        "tunisia": fr in {"Carthage", "Guerres puniques", "Hannibal Barca", "Dougga", "El Jem", "Utique", "Kerkouane", "Kairouan",
                          "Grande Mosquée de Kairouan", "Dynastie hafside", "Ifriqiya", "Protectorat français de Tunisie",
                          "Habib Bourguiba", "Mouvement national tunisien", "Indépendance de la Tunisie", "Révolution tunisienne"},
    }

# additional English names for topics of the extended plan (display only)
EXTRA_NAMES = {
    "Jules César": "Julius Caesar", "Alexandre le Grand": "Alexander the Great", "Empire perse": "Persian Empire",
    "Grèce antique": "Ancient Greece", "Égypte antique": "Ancient Egypt", "Cléopâtre": "Cleopatra",
    "Dynastie Han": "Han dynasty", "Qin Shi Huang": "Qin Shi Huang", "Charlemagne": "Charlemagne",
    "Empire carolingien": "Carolingian Empire", "Croisades": "Crusades", "Gengis Khan": "Genghis Khan",
    "Empire mongol": "Mongol Empire", "Saladin": "Saladin", "Guerre de Cent Ans": "Hundred Years' War",
    "Jeanne d'Arc": "Joan of Arc", "Empire ottoman": "Ottoman Empire", "Renaissance italienne": "Italian Renaissance",
    "Route de la soie": "Silk Road", "Grandes découvertes": "Age of Discovery", "Christophe Colomb": "Christopher Columbus",
    "Empire aztèque": "Aztec Empire", "Empire inca": "Inca Empire", "Traite négrière transatlantique": "Transatlantic slave trade",
    "Révolution française": "French Revolution", "Napoléon Bonaparte": "Napoleon Bonaparte",
    "Révolution industrielle": "Industrial Revolution", "Colonisation de l'Afrique": "Colonization of Africa",
    "Louis XIV": "Louis XIV", "Marie-Antoinette": "Marie Antoinette", "Révolution américaine": "American Revolution",
    "Déclaration d'indépendance des États-Unis": "United States Declaration of Independence",
    "Première Guerre mondiale": "World War I", "Seconde Guerre mondiale": "World War II", "Adolf Hitler": "Adolf Hitler",
    "Guerre froide": "Cold War", "Décolonisation": "Decolonization", "Révolution russe": "Russian Revolution",
    "Mao Zedong": "Mao Zedong", "Mahatma Gandhi": "Mahatma Gandhi", "Guerre de Sécession": "American Civil War",
    "Abraham Lincoln": "Abraham Lincoln", "Otto von Bismarck": "Otto von Bismarck",
    "Unification de l'Allemagne": "Unification of Germany",
}

TITRES_EN = {fr: m["en"] for fr, m in TOPICS.items()}
TITRES_EN.update(EXTRA_NAMES)


def nom_en(titre):
    return TITRES_EN.get(titre, titre)


def meta(titre):
    return TOPICS.get(titre, {"en": nom_en(titre), "emoji": "📜", "era": None, "year": None, "region": None,
                              "lat": None, "lon": None, "kind": None, "sensitive": False, "tunisia": False})
