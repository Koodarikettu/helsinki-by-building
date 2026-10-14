"""Quests: short walks through the city as riddles. Three kinds of step, mixed within a quest:

  find    a riddle; the player finds the building on the map and clicks it. Hints first draw a circle around it,
          then say more; "Show me" flies there for no crosses.
  year    the map flies to a building and hides its age (colours and card); the player guesses the year it was built.
  choice  the map flies to a building; the player picks one of three answers.

Every claim rests on a source that s09_quests.py checks: a Wikipedia article that must contain the given strings.
Where a step names a year, that year must also be the map's year for the building, so the card the player opens
next tells the same story.

`at` says where the step happens:
  "wd:<lang>:<article>"   the building(s) whose Wikidata item has that article (linked by VTJ-PRT, P3824)
  "addr:<address>"        a street address, through the city's address points (as the archive photos are placed)
`checks`: [(article, [strings])]: each article must contain each string (case-insensitive).
`clue`: "today" (the building's Commons photo), or an archive photo from the Helsinki City Museum {"id", "year"}.
Levels: 1 easy, 2 medium, 3 hard.
"""


def T(en, fi):
    return dict(en=en, fi=fi)


def find(at, riddle, hints, reveal, checks=(), clue=None, mode=None):
    return dict(kind="find", at=at, riddle=riddle, hints=hints, reveal=reveal, checks=list(checks), clue=clue, mode=mode)


def year(at, ask, answer, reveal, checks):
    return dict(kind="year", at=at, ask=ask, year=answer, reveal=reveal, checks=list(checks))


def choice(at, ask, options, reveal, checks=()):
    """options: the right answer first; the page shuffles them."""
    return dict(kind="choice", at=at, ask=ask, options=options, reveal=reveal, checks=list(checks))


def archive(id, year):
    return dict(id=id, year=year)


QUESTS = [
    # ---------------------------------------------------------------- easy
    dict(id="senaatintori", level=1,
         title=T("Around the Senate Square", "Senaatintorin ympärillä"),
         intro=T("Five buildings on and near the city's grandest square. A gentle start.",
                 "Viisi rakennusta kaupungin komeimman torin laidalla ja lähellä. Rauhallinen alku."),
         steps=[
             find("wd:fi:Helsingin tuomiokirkko",
                  T("Start with one of the city's best-known symbols: a church whose roof is lined with statues of "
                    "the apostles.",
                    "Aloita yhdestä kaupungin tunnetuimmista symboleista: kirkosta, jonka katolla seisovat "
                    "apostolien patsaat."),
                  [T("It stands on the edge of the Senate Square.", "Se seisoo Senaatintorin laidalla.")],
                  T("Helsinki Cathedral, first called St Nicholas' Church. Carl Ludvig Engel designed it; it was "
                    "completed in 1852.",
                    "Helsingin tuomiokirkko, alun perin Nikolainkirkko. Sen suunnitteli Carl Ludvig Engel, ja se "
                    "valmistui vuonna 1852."),
                  checks=[("fi:Helsingin tuomiokirkko", ["apostolipatsaineen", "Senaatintorin laidalla",
                                                          "Nikolainkirkko", "Carl Ludvig Engelin suunnittelema",
                                                          "Kirkko valmistui vuonna 1852"])],
                  clue="today"),
             year("addr:Aleksanterinkatu 16",
                  T("On the Senate Square, at the corner of Aleksanterinkatu and Katariinankatu, the merchant Johan "
                    "Sederholm built a stone house. It is the oldest building in the inner city. When was it finished?",
                    "Senaatintorilla Aleksanterinkadun ja Katariinankadun kulmassa on kauppaneuvos Johan Sederholmin "
                    "rakennuttama kivitalo, kantakaupungin vanhin rakennus. Minä vuonna se valmistui?"),
                  1757,
                  T("1757. Sederholm had it built in 1756–1757: two storeys, a large attic and a vaulted cellar.",
                    "1757. Sederholm rakennutti talon vuosina 1756–1757: kaksi kerrosta, iso ullakko ja suuri "
                    "kellariholvi."),
                  checks=[("fi:Sederholmin talo", ["vuonna 1757 valmistunut kivitalo", "Aleksanterinkadun ja "
                                                   "Katariinankadun kulmassa", "kantakaupungin vanhin rakennus",
                                                   "vuosina 1756-1757", "suuri kellariholvi"])]),
             choice("wd:fi:Valtioneuvoston linna",
                    T("This palace fills its whole block beside the square. It was built for the Senate. Who "
                      "designed it?",
                      "Tämä palatsi täyttää koko korttelinsa torin laidalla. Se rakennettiin senaattia varten. Kuka "
                      "sen suunnitteli?"),
                    [T("Carl Ludvig Engel", "Carl Ludvig Engel"), T("Theodor Höijer", "Theodor Höijer"),
                     T("Eliel Saarinen", "Eliel Saarinen")],
                    T("Carl Ludvig Engel. The Senate worked here from 1822 to 1918; since then it has been the "
                      "Government Palace.",
                      "Carl Ludvig Engel. Senaatti toimi rakennuksessa vuodet 1822–1918; nykyään se on "
                      "Valtioneuvoston linna."),
                    checks=[("fi:Valtioneuvoston linna", ["Rakennus kattaa koko", "arkkitehti Carl Ludvig Engel",
                                                          "Suomen senaattia varten", "vuodet 1822–1918"])]),
             find("wd:fi:Helsingin yliopiston päärakennus",
                  T("Engel also designed the building the university moved into when it came to Helsinki. Find "
                    "its main building on the square.",
                    "Engel suunnitteli myös rakennuksen, johon yliopisto muutti tultuaan Helsinkiin. Etsi sen "
                    "päärakennus torin laidalta."),
                  [T("It faces the Government Palace across the Senate Square.",
                     "Se on Valtioneuvoston linnaa vastapäätä Senaatintorin toisella puolella.")],
                  T("The main building of the University of Helsinki, an Empire building by Carl Ludvig Engel.",
                    "Helsingin yliopiston päärakennus, Carl Ludvig Engelin suunnittelema empirerakennus."),
                  checks=[("fi:Helsingin yliopiston päärakennus", ["Carl Ludvig Engelin suunnittelema empirerakennus",
                                                                   "akatemia oli siirrettävä Helsinkiin"])]),
             year("wd:fi:Uspenskin katedraali",
                  T("East of the square, on the rocks of Katajanokka, stands a red-brick church. When was it "
                    "consecrated?",
                    "Torin itäpuolella Katajanokan kalliolla on punatiilinen kirkko. Minä vuonna se vihittiin "
                    "käyttöön?"),
                  1868,
                  T("1868, after six years of building. Its bricks came from the fortress of Bomarsund on Åland, "
                    "which was being torn down.",
                    "1868, kuuden vuoden rakennustöiden jälkeen. Tiilet tuotiin Ahvenanmaalta Bomarsundin "
                    "purettavasta linnoituksesta."),
                  checks=[("fi:Uspenskin katedraali", ["Punatiilinen kirkko", "Katajanokan kalliolla",
                                                       "vuosina 1862–1868", "lokakuuta 1868",
                                                       "Bomarsundin purettavasta linnoituksesta"])]),
         ]),
    # ---------------------------------------------------------------- medium
    dict(id="rautatientori", level=2,
         title=T("From the Railway Square to Töölönlahti", "Rautatientorilta Töölönlahdelle"),
         intro=T("Granite, stone and glass: a century of public buildings on one walk.",
                 "Graniittia, kiveä ja lasia: vuosisata julkisia rakennuksia yhdellä kävelyllä."),
         steps=[
             find("wd:fi:Helsingin päärautatieasema",
                  T("Stone giants holding lamps guard its door, and a clock tower rises above it.",
                    "Sen ovea vartioivat lyhtyjä kantavat kivijätit, ja sen yllä kohoaa kellotorni."),
                  [T("The trains leave from behind it.", "Sen takaa lähtevät junat.")],
                  T("The Central Railway Station. Eliel Saarinen designed the granite building; the Lantern Bearers "
                    "are by the sculptor Emil Wikström.",
                    "Helsingin päärautatieasema. Graniittisen asemarakennuksen suunnitteli Eliel Saarinen, ja "
                    "Lyhdynkantajat-patsaat ovat kuvanveistäjä Emil Wikströmin."),
                  checks=[("fi:Helsingin päärautatieasema", ["Eliel Saarisen", "graniittinen asemarakennus",
                                                             "kellotornistaan", "Emil Wikströmin Lyhdynkantajat-patsaista"])],
                  clue="today"),
             year("wd:fi:Ateneumin taidemuseo",
                  T("On the Railway Square, an art museum of the Finnish National Gallery fills a neo-Renaissance "
                    "palace. When was the building completed?",
                    "Rautatientorin laidalla on Kansallisgalleriaan kuuluva taidemuseo uusrenessanssipalatsissa. "
                    "Minä vuonna rakennus valmistui?"),
                  1887,
                  T("1887, designed by Theodor Höijer. The museum of contemporary art also worked here, from 1991 "
                    "to 1998.",
                    "1887, Theodor Höijerin suunnittelemana. Myös nykytaiteen museo toimi Ateneumissa vuosina "
                    "1991–1998."),
                  checks=[("fi:Ateneumin taidemuseo", ["osa Kansallisgalleriaa", "Theodor Höijerin suunnittelema",
                                                       "uusrenessanssirakennus valmistui 1887",
                                                       "Nykytaiteen museo toimi Ateneumissa 1991–1998"])]),
             find("addr:Läntinen Teatterikuja 1",
                  T("Across the square stands a theatre built of grey granite: the oldest professional theatre in "
                    "the Finnish language.",
                    "Torin toisella laidalla on harmaasta graniitista rakennettu teatteri, vanhin suomenkielinen "
                    "ammattiteatteri."),
                  [T("It faces the Ateneum across the Railway Square.",
                     "Se on Ateneumia vastapäätä Rautatientorin toisella puolella.")],
                  T("The Finnish National Theatre. Its national romantic house by Onni Törnqvist-Tarjanne is built "
                    "of grey granite from Uusikaupunki.",
                    "Suomen Kansallisteatteri. Onni Törnqvist-Tarjanteen suunnittelema kansallisromanttinen talo on "
                    "rakennettu Uudenkaupungin harmaasta graniitista."),
                  checks=[("fi:Suomen Kansallisteatteri", ["vanhin suomenkielinen ammattiteatteri",
                                                           "Rautatientorin varrelle",
                                                           "Onni Törnqvist-Tarjanteen suunnittelema kansallisromanttinen talo",
                                                           "Uudenkaupungin harmaasta graniitista"])]),
             year("addr:Mannerheiminaukio 2",
                  T("A museum of contemporary art designed by the American architect Steven Holl. When was it "
                    "completed?",
                    "Yhdysvaltalaisen arkkitehdin Steven Hollin suunnittelema nykytaiteen museo. Minä vuonna se "
                    "valmistui?"),
                  1998,
                  T("1998. Until then the museum of contemporary art worked in the Ateneum.",
                    "1998. Siihen asti nykytaiteen museo toimi Ateneumissa."),
                  checks=[("fi:Kiasma", ["nykytaiteen museo", "Steven Hollin suunnittelema Kiasma-rakennus valmistui 1998",
                                         "Museo toimi aluksi Ateneum-rakennuksessa"])]),
             find("addr:Töölönlahdenkatu 4",
                  T("Last, the youngest public building of the walk: the city's central library, opened in December "
                    "2018.",
                    "Lopuksi kävelyn nuorin julkinen rakennus: kaupungin keskustakirjasto, joka avattiin joulukuussa "
                    "2018."),
                  [T("It stands on the edge of the Kansalaistori square, near Töölönlahti.",
                     "Se on Kansalaistorin laidalla Töölönlahden läheisyydessä.")],
                  T("Oodi, the Helsinki Central Library, opened on 5 December 2018. The Finnish firm ALA won the "
                    "international design competition.",
                    "Helsingin keskustakirjasto Oodi avattiin 5. joulukuuta 2018. Kansainvälisen "
                    "suunnittelukilpailun voitti Arkkitehtitoimisto ALA."),
                  checks=[("fi:Helsingin keskustakirjasto Oodi", ["Kansalaistorin laidalla",
                                                                  "Töölönlahden läheisyydessä",
                                                                  "Arkkitehtitoimisto ALA",
                                                                  "joulukuuta 2018"])]),
         ]),
    # ---------------------------------------------------------------- hard
    dict(id="vanhat-kuvat", level=3,
         title=T("Old photographs", "Vanhoja valokuvia"),
         intro=T("Five buildings that the Helsinki City Museum's photographers captured in the 1800s. Find each from its "
                 "old photo.",
                 "Viisi rakennusta, jotka Helsingin kaupunginmuseon kuvaajat ikuistivat 1800-luvulla. Etsi kukin vanhan "
                 "kuvan perusteella."),
         steps=[
             find("wd:fi:Kaivohuone",
                  T("Spa guests in front of a wooden pavilion. The spa itself stood on the shore nearby.",
                    "Kylpylävieraita puisen paviljongin edessä. Itse kylpylä oli lähellä merenrannassa."),
                  [T("It stands in Kaivopuisto, on Iso Puistotie.", "Se on Kaivopuistossa Ison Puistotien varrella.")],
                  T("Kaivohuone, a wooden building by Carl Ludvig Engel. It opened together with the seaside spa on "
                    "5 June 1838.",
                    "Kaivohuone, Carl Ludvig Engelin suunnittelema puurakennus. Se avattiin yhdessä merenrannan "
                    "kylpylän kanssa 5. kesäkuuta 1838."),
                  checks=[("fi:Kaivohuone", ["Kaivopuistossa Ison Puistotien varrella",
                                             "puurakennuksen on suunnitellut arkkitehti Carl Ludvig Engel",
                                             "merenrannassa sijainneen kylpylän", "kesäkuuta 1838"])],
                  clue=archive("hkm.ADA0EE26-D07A-4AC1-ACAE-897B1985300F", 1870)),
             find("wd:fi:Ritarihuone",
                  T("A neo-Gothic house built so that the nobility had a place to meet for the Diet.",
                    "Uusgoottilainen talo, joka rakennettiin aateliston kokoontumispaikaksi valtiopäiviä varten."),
                  [T("It stands in Kruununhaka.", "Se on Kruununhaassa.")],
                  T("The House of Nobility, designed by Georg Theodor von Chiewitz.",
                    "Ritarihuone, arkkitehti Georg Theodor von Chiewitzin suunnittelema."),
                  checks=[("fi:Ritarihuone", ["uusgoottilainen valtiopäivärakennus", "Kruununhaassa",
                                              "Suomen aatelisto tarvitsi kokoontumispaikan",
                                              "suunnitellut arkkitehti Georg Theodor von Chiewitz"])],
                  clue=archive("hkm.E356CB51-9283-4017-99C7-110D34AC64EE", 1870)),
             find("wd:fi:Svenska Teatern",
                  T("“Nya theatern”, the new theatre, photographed in the year it opened, after a fire had destroyed "
                    "the one before it.",
                    "”Nya theatern”, uusi teatteri, kuvattuna avajaisvuonnaan sen jälkeen, kun tulipalo oli tuhonnut "
                    "edellisen."),
                  [T("It stands at the west end of the Esplanade park, between its two streets.",
                     "Se on Esplanadin puiston länsipäässä, Etelä- ja Pohjoisesplanadin välissä.")],
                  T("Svenska Teatern, rebuilt by the Russian architect Nicolas Benois and opened in 1866. His "
                    "auditorium and foyer survive almost as they were.",
                    "Svenska Teatern. Venäläinen arkkitehti Nicolas Benois suunnitteli uuden rakennuksen, joka vihittiin "
                    "käyttöön vuonna 1866. Benois’n salonki ja lämpiö ovat säilyneet lähes alkuperäisinä."),
                  checks=[("fi:Svenska Teatern", ["Esplanadin puiston länsipäässä", "tuhoutui tulipalossa",
                                                  "vuonna 1866 käyttöön vihittiin", "venäläinen arkkitehti Nicolas Benois",
                                                  "salonki ja lämpiö"])],
                  clue=archive("hkm.1B604709-EE8D-4989-A91B-FCC2DB27CB08", 1866)),
             find("wd:fi:Presidentinlinna",
                  T("When this photo was taken it was the emperor's palace in Helsinki. Before that it had been a "
                    "merchant family's house.",
                    "Kuvan aikaan tämä oli keisarillinen palatsi Helsingissä. Sitä ennen se oli kauppiassuvun talo."),
                  [T("It stands on the edge of the Market Square.", "Se on Kauppatorin laidalla.")],
                  T("The Presidential Palace. Pehr Granstedt designed it in 1814 as a merchant house; the Senate bought "
                    "it in 1837 as the emperors' palace, and it was refitted for the President in 1921.",
                    "Presidentinlinna. Pehr Granstedt suunnitteli sen vuonna 1814 kauppiastaloksi; senaatti osti sen "
                    "vuonna 1837 keisarien palatsiksi, ja presidentinlinnaksi se kunnostettiin vuonna 1921."),
                  checks=[("fi:Presidentinlinna", ["keisarillinen palatsi Helsingissä", "Kauppatorin laidalla",
                                                   "Pehr Granstedt suunnitteli talon alkujaan 1814",
                                                   "kauppiastaloksi ja asunnoksi", "Suomen senaatti osti talon vuonna 1837",
                                                   "Presidentinlinnaksi rakennus kunnostettiin vuonna 1921"])],
                  clue=archive("hkm.8E8A5479-3ED9-4C04-8E47-241335593A00", 1891)),
             find("wd:fi:Säätytalo",
                  T("Built for the three estates without nobility, which had waited for a house of their own. Today "
                    "governments are negotiated here after elections.",
                    "Rakennettiin kolmelle aatelittomalle säädylle, jotka olivat odottaneet omia tiloja. Nykyään täällä "
                    "neuvotellaan hallitus eduskuntavaalien jälkeen."),
                  [T("It stands on Snellmaninkatu, opposite the Bank of Finland.",
                     "Se on Snellmaninkadulla vastapäätä Suomen Pankkia.")],
                  T("The House of the Estates by Gustaf Nyström, inaugurated in January 1891. When the one-chamber "
                    "parliament replaced the Diet in 1906, it was too small for the plenary sessions.",
                    "Säätytalo, Gustaf Nyströmin suunnittelema, vihittiin käyttöön tammikuussa 1891. Kun yksikamarinen "
                    "eduskunta korvasi säätyvaltiopäivät 1906, rakennus oli liian pieni sen täysistunnoille."),
                  checks=[("fi:Säätytalo", ["Kolme aatelitonta säätyä", "hallitusneuvottelut",
                                            "Snellmaninkadulla, vastapäätä Suomen Pankkia", "Gustaf Nyströmin suunnittelema",
                                            "vihittiin käyttöön tammikuussa 1891", "yksikamarinen eduskunta",
                                            "täysistuntoihin rakennus oli liian pieni"])],
                  clue=archive("hkm.A7779587-BF2D-43F4-B4DB-924EFAB39C19", 1893)),
         ]),
]
