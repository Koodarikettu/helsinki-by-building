"""Helsinki periods. Boundaries follow the city's history and growth, not decades."""
PERIODS = [
    # (key, label, start, end, colour). Amsterdam's ten colours in the same order: oxblood brick for the oldest,
    # through ochre and green, to slate and violet. Finnish labels are in web/app.js (FI_UI).
    ("p1", "–1808 Swedish era",                         1000, 1808, "#4a1410"),
    ("p2", "1809–1869 Empire Helsinki",                 1809, 1869, "#8c1c13"),
    ("p3", "1870–1899 Historicism and the railway",     1870, 1899, "#c0462b"),
    ("p4", "1900–1917 Art Nouveau and National Romanticism", 1900, 1917, "#d97a2b"),
    ("p5", "1918–1939 Classicism and functionalism",    1918, 1939, "#e5b13a"),
    ("p6", "1940–1959 Reconstruction and the Olympics", 1940, 1959, "#8e9f3c"),
    ("p7", "1960–1979 Suburbs and prefab concrete",     1960, 1979, "#3f8f6b"),
    ("p8", "1980–1999 Postmodernism and infill",        1980, 1999, "#2c7391"),
    ("p9", "2000–2014 Ruoholahti, Arabianranta, Viikki", 2000, 2014, "#3a4f9a"),
    ("p10", "2015– Jätkäsaari, Kalasatama, Pasila",     2015, 2100, "#6a3f8f"),
]

def period_index(year: int) -> int:
    for i, (_, _, a, b, _) in enumerate(PERIODS):
        if a <= year <= b:
            return i
    return 0
