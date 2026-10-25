"""Demo newsroom cities besides Oulu (seeded by ``manage.py seed_cities``, run by bootstrap).

Each city is a geographic community the newsroom can run for, with five topic communities,
a few neighbours who live there, and member posts. Oulu's own communities and posts are in
``seed_demo`` and ``bootstrap``.

Posts are written in Finnish and English only: invented text in other reader languages is
never seeded. Readers get them in their own language through the normal post translation.
They are mostly questions and neighbourly offers, not claims of fact; questions also reach
the newsroom as reader questions.
"""

# (municipality code, slug, name, description)
CITIES = [
    ("240", "kemi", "Kemi", "Everyone in Kemi: local talk, neighbourly help and questions for the newsroom."),
    ("678", "raahe", "Raahe", "Everyone in Raahe: local talk, neighbourly help and questions for the newsroom."),
    ("205", "kajaani", "Kajaani", "Everyone in Kajaani: local talk, neighbourly help and questions for the newsroom."),
    ("261", "kittila", "Kittilä", "Everyone in Kittilä and Levi: local talk, help and questions for the newsroom."),
]

# Topic communities per city: (city slug, slug, name, description, audiences, interests, languages)
TOPICS = [
    ("kemi", "kemi-newcomers", "New in Kemi", "The first months in Kemi: Kela, housing, registering, finding your way.",
     ["newcomer"], ["services", "housing", "work", "health"], ["fi", "en", "uk", "ru"]),
    ("kemi", "kemi-families", "Families in Kemi", "Schools, daycare, health services and things to do with kids.",
     [], ["education", "health", "services"], ["fi", "en"]),
    ("kemi", "kemi-work", "Work in Kemi–Tornio", "Jobs, shifts and getting to work around Kemi and Tornio.",
     [], ["work", "transport"], ["fi", "en"]),
    ("kemi", "kemi-culture", "Culture & events in Kemi", "What's on in Kemi this week.",
     [], ["culture", "events"], ["fi", "en"]),
    ("kemi", "kemi-outdoors", "Outdoors & sports in Kemi", "Skiing, the sea ice, sports clubs and staying safe outdoors.",
     [], ["sports", "weather"], ["fi", "en"]),

    ("raahe", "raahe-newcomers", "New in Raahe", "Settling in to Raahe: housing, services and everyday questions.",
     ["newcomer"], ["services", "housing", "work"], ["fi", "en"]),
    ("raahe", "raahe-families", "Families in Raahe", "Schools, daycare and things to do with kids.",
     [], ["education", "health", "services"], ["fi", "en"]),
    ("raahe", "raahe-work", "Work in Raahe", "Jobs, shifts and carpools, from the steel works to services.",
     [], ["work", "transport"], ["fi", "en"]),
    ("raahe", "raahe-culture", "Culture & events in Raahe", "Old Raahe, music, clubs and what's on.",
     [], ["culture", "events"], ["fi", "en"]),
    ("raahe", "raahe-sports", "Sports & outdoors in Raahe", "Training partners, clubs and outdoor tips.",
     [], ["sports", "weather"], ["fi", "en"]),

    ("kajaani", "kajaani-newcomers", "New in Kajaani", "The first months in Kajaani: services, housing and language.",
     ["newcomer"], ["services", "housing", "health"], ["fi", "en", "ru"]),
    ("kajaani", "kajaani-students", "Students in Kajaani", "KAMK life: housing, cheap eats, bikes and events.",
     ["student"], ["education", "housing", "events", "transport"], ["fi", "en"]),
    ("kajaani", "kajaani-families", "Families in Kajaani", "Schools, daycare, hobbies and health services.",
     [], ["education", "health", "services"], ["fi", "en"]),
    ("kajaani", "kajaani-culture", "Culture & events in Kajaani", "Films, concerts and what's on this weekend.",
     [], ["culture", "events"], ["fi", "en"]),
    ("kajaani", "kajaani-outdoors", "Outdoors in Kajaani", "Skiing, trails and staying safe in the dark months.",
     [], ["sports", "weather"], ["fi", "en"]),

    ("kittila", "kittila-seasonal", "Seasonal workers in Levi", "Work, housing and getting around for the season.",
     ["seasonal_worker"], ["work", "housing", "transport", "weather"], ["fi", "en", "et", "sv"]),
    ("kittila", "kittila-newcomers", "New in Kittilä", "Registering, services and everyday life in Kittilä.",
     ["newcomer"], ["services", "housing", "health"], ["fi", "en"]),
    ("kittila", "kittila-work", "Jobs in Levi & Kittilä", "Who's hiring, tax cards and work questions.",
     [], ["work"], ["fi", "en"]),
    ("kittila", "kittila-events", "Events in Levi", "Meetups, staff evenings and what's on in the fells.",
     [], ["events", "culture"], ["fi", "en"]),
    ("kittila", "kittila-outdoors", "Outdoors & safety in Kittilä", "Fells, cold weather and staying safe.",
     [], ["weather", "sports"], ["fi", "en"]),
]

# Neighbours who write the posts: (email, display name, language, situation, city slug, communities)
NEIGHBOURS = [
    ("sanna.kemi@example.com", "Sanna", "fi", "resident", "kemi", ["kemi-families", "kemi-outdoors"]),
    ("ahmed.kemi@example.com", "Ahmed", "en", "newcomer", "kemi", ["kemi-newcomers", "kemi-work", "kemi-outdoors"]),
    ("olga.kemi@example.com", "Olga", "en", "newcomer", "kemi", ["kemi-newcomers", "kemi-culture"]),
    ("olli.kemi@example.com", "Olli", "fi", "resident", "kemi", ["kemi-work", "kemi-outdoors"]),

    ("tiina.raahe@example.com", "Tiina", "fi", "resident", "raahe", ["raahe-work", "raahe-culture"]),
    ("rahul.raahe@example.com", "Rahul", "en", "newcomer", "raahe", ["raahe-newcomers", "raahe-work", "raahe-sports"]),
    ("lena.raahe@example.com", "Lena", "en", "newcomer", "raahe", ["raahe-families", "raahe-culture"]),
    ("mikko.raahe@example.com", "Mikko", "fi", "resident", "raahe", ["raahe-sports"]),

    ("heikki.kajaani@example.com", "Heikki", "fi", "resident", "kajaani", ["kajaani-newcomers", "kajaani-outdoors"]),
    ("amara.kajaani@example.com", "Amara", "en", "student", "kajaani",
     ["kajaani-students", "kajaani-outdoors", "kajaani-culture"]),
    ("viktor.kajaani@example.com", "Viktor", "en", "newcomer", "kajaani", ["kajaani-newcomers", "kajaani-culture"]),
    ("laura.kajaani@example.com", "Laura", "fi", "resident", "kajaani", ["kajaani-families"]),

    ("johanna.kittila@example.com", "Johanna", "fi", "resident", "kittila",
     ["kittila-work", "kittila-outdoors", "kittila-seasonal"]),
    ("tomas.kittila@example.com", "Tomas", "en", "seasonal_worker", "kittila",
     ["kittila-seasonal", "kittila-outdoors"]),
    ("kasia.kittila@example.com", "Kasia", "en", "seasonal_worker", "kittila",
     ["kittila-seasonal", "kittila-work", "kittila-newcomers", "kittila-events"]),
]

# Member posts, newest first within each city: (author, community, text)
POSTS = [
    ("sanna.kemi@example.com", "kemi", "Tervetuloa kaikki uudet kemiläiset! Kysykää täällä rohkeasti, autetaan mielellään."),
    ("ahmed.kemi@example.com", "kemi-newcomers", "Does anyone know where I can get help with Kela forms in English in Kemi?"),
    ("olga.kemi@example.com", "kemi-newcomers", "I moved here last month. Is there an evening Finnish course for beginners?"),
    ("sanna.kemi@example.com", "kemi-families", "Tietääkö joku hyviä sisäleikkipaikkoja Kemissä pakkaspäiville?"),
    ("ahmed.kemi@example.com", "kemi-work", "Are there shift jobs at the port or the mills for people who don't speak Finnish yet?"),
    ("olli.kemi@example.com", "kemi-work", "Kimppakyyti Tornioon aamuvuoroon arkisin, onko muita samaan suuntaan? Bensat jaetaan."),
    ("olga.kemi@example.com", "kemi-culture", "Any tips for things to do in Kemi on a winter weekend?"),
    ("olli.kemi@example.com", "kemi-outdoors", "Meren jäät eivät vielä kanna. Odotetaan kunnon pakkasia ennen kuin lähdetään jäälle."),
    ("ahmed.kemi@example.com", "kemi-outdoors", "Where do people go cross-country skiing near the centre?"),

    ("tiina.raahe@example.com", "raahe", "Hyvää syksyä naapurit! Täällä voi kysyä ja vinkata kaikesta Raaheen liittyvästä."),
    ("rahul.raahe@example.com", "raahe-newcomers", "Just moved to Raahe for work. Where do people usually find a rental flat here?"),
    ("rahul.raahe@example.com", "raahe-work", "Is there a carpool from the centre to the steel works for the early shift?"),
    ("tiina.raahe@example.com", "raahe-work", "Töitä etsiville: kannattaa seurata myös kaupungin omia avoimia työpaikkoja."),
    ("lena.raahe@example.com", "raahe-families", "Are there any English-speaking playgroups for toddlers in Raahe?"),
    ("tiina.raahe@example.com", "raahe-culture", "Vanha Raahe on kaunis myös talvella. Kannattaa lähteä kävelylle, kun valot syttyvät."),
    ("lena.raahe@example.com", "raahe-culture", "Is there a choir or music group that welcomes beginners?"),
    ("mikko.raahe@example.com", "raahe-sports", "Haen kuntosalikaveria iltavuorojen jälkeen. Kiinnostaako ketään?"),
    ("rahul.raahe@example.com", "raahe-sports", "Does anyone play badminton or cricket in Raahe? Looking for people to play with."),

    ("heikki.kajaani@example.com", "kajaani", "Tervetuloa Kajaanin yhteisöön! Täällä autetaan toisia arjen asioissa."),
    ("amara.kajaani@example.com", "kajaani-students", "First year at KAMK here. Any tips for cheap places to eat near campus?"),
    ("amara.kajaani@example.com", "kajaani-students", "Is anyone selling a used bike? I need one to get to campus."),
    ("viktor.kajaani@example.com", "kajaani-newcomers", "How long does it usually take to get a health centre appointment as a new resident?"),
    ("heikki.kajaani@example.com", "kajaani-newcomers", "Jos tarvitset apua suomen kielen kanssa, voin auttaa kahvikupin ääressä keskustassa."),
    ("laura.kajaani@example.com", "kajaani-families", "Onko vinkkejä lasten harrastuksiin, joihin ei tarvitse osata suomea? Kysyn ystävän puolesta."),
    ("viktor.kajaani@example.com", "kajaani-culture", "Is there a place in Kajaani to watch films in English?"),
    ("heikki.kajaani@example.com", "kajaani-outdoors", "Muistakaa heijastin pimeillä iltalenkeillä!"),
    ("amara.kajaani@example.com", "kajaani-outdoors", "Where can I rent skis for a weekend?"),

    ("johanna.kittila@example.com", "kittila", "Tervetuloa kauden tekijät ja uudet asukkaat! Kysykää täällä, autetaan."),
    ("tomas.kittila@example.com", "kittila-seasonal",
     "Arriving for the winter season next month. Do most employers here provide housing, or should I look myself?"),
    ("tomas.kittila@example.com", "kittila-seasonal", "Is there a bus between Levi and Kittilä village in the evenings?"),
    ("kasia.kittila@example.com", "kittila-work", "Looking for kitchen work in Levi for the season. Any restaurants hiring English speakers?"),
    ("johanna.kittila@example.com", "kittila-work", "Muistakaa pyytää verokortti ennen ensimmäistä palkkaa, muuten palkasta pidätetään paljon veroa."),
    ("kasia.kittila@example.com", "kittila-newcomers", "Where do I register my address if I'm only here for the season?"),
    ("johanna.kittila@example.com", "kittila-outdoors", "Tunturissa sää muuttuu nopeasti. Kertokaa aina jollekin, minne olette menossa."),
    ("tomas.kittila@example.com", "kittila-outdoors", "What do people wear at -30 °C? It's my first winter in Lapland."),
    ("kasia.kittila@example.com", "kittila-events", "Any meetups for seasonal workers this winter? Would be nice to meet people outside work."),
]
