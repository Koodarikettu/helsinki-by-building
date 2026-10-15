"""Labels for the register's coded fields, (Finnish, English).

KAYTTARK  c_kayttark: Statistics Finland, Rakennusluokitus 1994, level 3, in Finnish and English:
          https://data.stat.fi/api/classifications/v2/classifications/rakennus_1_19940101/classificationItems?content=data&meta=max&lang=fi&format=json
          (and lang=en). Helsinki's metadata names it as the field's classification:
          https://kartta.hel.fi/avoindata/dokumentit/2017-01-10_Rakennusaineisto_avoindata_metatiedot.pdf
RAKEAINE  c_rakeaine, JULKISIVU c_julkisivu: Helsinki's own lists RA_KANTRAKAINE and RA_JULKISIVUMAT, in Finnish only:
          https://kartta.hel.fi/avoindata/dokumentit/2017-01-10_Rakennusaineisto_avoindata_koodistot.pdf
          English from the national Ryhti lists on koodistot.suomi.fi (kantavanrakenteenrakennusaine,
          julkisivunrakennusaine), matched by Finnish label; Ryhti numbers its codes differently.
TYYPPI    tyyppi, the base map's building type, for buildings without a register class. English is ours.
LAMMONLAHDE c_poltaine, LAMMITYSTAPA c_lammtapa: Helsinki's lists RA_LAMMONLAHDE and RA_LAMMITYSTAPA in the same
          document; English is ours. HEAT groups the sources for the map's colouring, 0 where none is recorded.
"""
KAYTTARK = {
    "011": ("Yhden asunnon talot", "One-dwelling houses"),
    "012": ("Kahden asunnon talot", "Two-dwelling houses"),
    "013": ("Muut erilliset pientalot", "Other detached and semi-detached houses"),
    "021": ("Rivitalot", "Rowhouses"),
    "022": ("Ketjutalot", "Terraced houses"),
    "032": ("Luhtitalot", "Balcony-access blocks"),
    "039": ("Muut asuinkerrostalot", "Other blocks of flats"),
    "041": ("Vapaa-ajan asuinrakennukset", "Free-time residential buildings"),
    "111": ("Myymälähallit", "Shopping halls"),
    "112": ("Liike- ja tavaratalot, kauppakeskukset", "Shops, department stores and shopping centres"),
    "119": ("Muut myymälärakennukset", "Other wholesale and retail trade buildings"),
    "121": ("Hotellit yms.", "Hotels, etc."),
    "123": ("Loma-, lepo- ja virkistyskodit", "Holiday, rest and recreation homes"),
    "124": ("Vuokrattavat lomamökit ja -osakkeet", "Rental holiday cottages and flats"),
    "129": ("Muut majoitusliikerakennukset", "Other hotel buildings"),
    "131": ("Asuntolat yms.", "Residences for communities, etc."),
    "139": ("Muut asuntolarakennukset", "Other residential buildings for communities"),
    "141": ("Ravintolat yms.", "Restaurants and other similar buildings"),
    "151": ("Toimistorakennukset", "Office buildings"),
    "161": ("Rautatie- ja linja-autoasemat, lento- ja satamaterminaalit", "Rail and bus stations, air and harbour terminals"),
    "162": ("Kulkuneuvojen suoja- ja huoltorakennukset", "Vehicle depots and service buildings"),
    "163": ("Pysäköintitalot", "Car parks"),
    "164": ("Tietoliikenteen rakennukset", "Communications buildings"),
    "169": ("Muut liikenteen rakennukset", "Other transport and communications buildings"),
    "211": ("Keskussairaalat", "General hospitals"),
    "213": ("Muut sairaalat", "Other hospitals"),
    "214": ("Terveyskeskukset", "Health centres"),
    "215": ("Terveydenhuollon erityislaitokset", "Specialised health care buildings"),
    "219": ("Muut terveydenhuoltorakennukset", "Other health care buildings"),
    "221": ("Vanhainkodit", "Old-age homes"),
    "222": ("Lasten- ja koulukodit", "Children's homes, reform schools"),
    "223": ("Kehitysvammaisten hoitolaitokset", "Care homes for people with intellectual disabilities"),  # official EN wording is dated
    "229": ("Muut huoltolaitosrakennukset", "Other social welfare buildings"),
    "231": ("Lasten päiväkodit", "Children's day care centres"),
    "239": ("Muualla luokittelemattomat sosiaalitoimen rakennukset", "Social service buildings n.e.c."),
    "241": ("Vankilat", "Prisons"),
    "311": ("Teatterit, ooppera-, konsertti- ja kongressitalot", "Theatres, opera houses, concert halls and congress centres"),
    "312": ("Elokuvateatterit", "Cinema halls"),
    "322": ("Kirjastot ja arkistot", "Libraries and archives"),
    "323": ("Museot ja taidegalleriat", "Museums and art galleries"),
    "324": ("Näyttelyhallit", "Exhibition halls"),
    "331": ("Seura- ja kerhorakennukset yms.", "Association and club buildings, etc."),
    "341": ("Kirkot, kappelit, luostarit ja rukoushuoneet", "Churches, chapels, monasteries, convents and prayerhouses"),
    "342": ("Seurakuntatalot", "Parish halls"),
    "349": ("Muut uskonnollisten yhteisöjen rakennukset", "Other buildings of religious communities"),
    "351": ("Jäähallit", "Indoor ice rinks"),
    "352": ("Uimahallit", "Indoor swimming pools"),
    "353": ("Tennis-, squash- ja sulkapallohallit", "Indoor tennis, squash and badminton courts"),
    "354": ("Monitoimihallit ja muut urheiluhallit", "Gymnasia and other sports halls"),
    "359": ("Muut urheilu- ja kuntoilurakennukset", "Other buildings for sports and physical exercise"),
    "369": ("Muut kokoontumisrakennukset", "Other assembly buildings"),
    "511": ("Yleissivistävien oppilaitosten rakennukset", "General education buildings"),
    "521": ("Ammatillisten oppilaitosten rakennukset", "Vocational education buildings"),
    "531": ("Korkeakoulurakennukset", "University buildings"),
    "532": ("Tutkimuslaitosrakennukset", "Research institute buildings"),
    "541": ("Järjestöjen, liittojen, työnantajien yms. opetusrakennukset", "Educational buildings of organisations, unions, employers, etc."),
    "549": ("Muualla luokittelemattomat opetusrakennukset", "Educational buildings n.e.c."),
    "611": ("Voimalaitosrakennukset", "Power stations"),
    "613": ("Yhdyskuntatekniikan rakennukset", "Public utility buildings"),
    "691": ("Teollisuushallit", "Manufacturing plants"),
    "692": ("Teollisuus- ja pienteollisuustalot", "Workshops for industry and small-scale industry"),
    "699": ("Muut teollisuuden tuotantorakennukset", "Other industrial production buildings"),
    "711": ("Teollisuusvarastot", "Industrial warehouses"),
    "712": ("Kauppavarastot", "Commercial warehouses"),
    "719": ("Muut varastorakennukset", "Other warehouses"),
    "721": ("Paloasemat", "Fire stations"),
    "722": ("Väestönsuojat", "Civil defence shelters"),
    "729": ("Muut palo- ja pelastustoimen rakennukset", "Other fire fighting and rescue service buildings"),
    "811": ("Navetat, sikalat, kanalat yms.", "Cowsheds, pighouses, hen-houses, etc."),
    "819": ("Eläinsuojat, ravihevostallit, maneesit yms.", "Animal shelters, harness horse stables, maneges, etc."),
    "891": ("Viljankuivaamot ja viljan säilytysrakennukset", "Grain drying and storage buildings"),
    "892": ("Kasvihuoneet", "Greenhouses"),
    "893": ("Turkistarhat", "Fur farms"),
    "899": ("Muut maa-, metsä- ja kalatalouden rakennukset", "Other buildings in agriculture, forestry and fishing"),
    "931": ("Saunarakennukset", "Sauna buildings"),
    "941": ("Talousrakennukset", "Outbuildings"),
    "999": ("Muualla luokittelemattomat rakennukset", "Buildings n.e.c."),
}

RAKEAINE = {1: ("Betoni tai kevytbetoni", "Concrete"), 2: ("Tiili", "Brick"), 3: ("Teräs", "Steel"),
            4: ("Puu", "Wood"), 5: ("Muu", "Other")}

JULKISIVU = {1: ("Betoni", "Concrete"), 2: ("Tiili", "Brick"), 3: ("Metallilevy", "Metal sheet"), 4: ("Kivi", "Stone"),
             5: ("Puu", "Wood"), 6: ("Lasi", "Glass"), 7: ("Muu", "Other")}

TYYPPI = {
    "Asuinrakennus": ("Asuinrakennus", "Residential building"),
    "Varastorakennus": ("Varastorakennus", "Storehouse"),
    "Vaja": ("Vaja", "Shed"),
    "Talousrakennus": ("Talousrakennus", "Outbuilding"),
    "Autotalli": ("Autotalli", "Garage"),
    "Vapaa-ajan rakennus": ("Vapaa-ajan rakennus", "Leisure building"),
    "Muu rakennus": ("Muu rakennus", "Other building"),
    "Liikerakennus": ("Liikerakennus", "Commercial building"),
    "Muuntamo": ("Muuntamo", "Transformer station"),
    "Sauna": ("Sauna", "Sauna"),
    "Tehdas": ("Tehdas", "Factory"),
    "Käymälä": ("Käymälä", "Toilet building"),
    "Parakki": ("Parakki", "Portable building"),
    "Räystäs (stereo)": ("Rakennus, ulkoraja räystäältä", "Building, outlined at the eaves"),
    "Pienteollisuusrakennus": ("Pienteollisuusrakennus", "Light industrial building"),
    "Opetusrakennus": ("Opetusrakennus", "Educational building"),
    "Asuin- ja liikerakennus": ("Asuin- ja liikerakennus", "Residential and commercial building"),
    "Päiväkoti": ("Päiväkoti", "Day care centre"),
    "Huoltorakennus": ("Huoltorakennus", "Service building"),
    "Kauppa tai kioski": ("Kauppa tai kioski", "Shop or kiosk"),
    "Pumppaamo": ("Pumppaamo", "Pumping station"),
    "Toimistorakennus": ("Toimistorakennus", "Office building"),
    "Paikoitustalo": ("Paikoitustalo", "Car park"),
    "Palvelutalo": ("Palvelutalo", "Service housing"),
    "Halli": ("Halli", "Hall"),
    "Sairaala": ("Sairaala", "Hospital"),
    "Pukusuoja": ("Pukusuoja", "Changing hut"),
    "Kirkko": ("Kirkko", "Church"),
    "Vartiorakennus": ("Vartiorakennus", "Guardhouse"),
    "Lämpökeskus": ("Lämpökeskus", "Heating plant"),
    "Asemarakennus": ("Asemarakennus", "Station building"),
    "Huoltoasema": ("Huoltoasema", "Petrol station"),
    "Ostoskeskus": ("Ostoskeskus", "Shopping centre"),
    "Lato": ("Lato", "Barn"),
    "Väestönsuoja": ("Väestönsuoja", "Civil defence shelter"),
}

LAMMONLAHDE = {1: ("Kauko- tai aluelämpö", "District heating"), 2: ("Kevyt polttoöljy", "Light fuel oil"),
               3: ("Raskas polttoöljy", "Heavy fuel oil"), 4: ("Sähkö", "Electricity"), 5: ("Kaasu", "Gas"),
               6: ("Kivihiili, koksi tms.", "Coal, coke or the like"), 7: ("Puu", "Wood"), 8: ("Turve", "Peat"),
               9: ("Maalämpö tms.", "Ground-source heat or the like"), 10: ("Muu", "Other")}

LAMMITYSTAPA = {1: ("Vesikeskuslämmitys", "Central heating, water"), 2: ("Ilmakeskuslämmitys", "Central heating, air"),
                3: ("Suora sähkölämmitys", "Direct electric heating"), 4: ("Uunilämmitys", "Stoves"),
                5: ("Ei kiinteää lämmityslaitetta", "No fixed heating")}

# The colouring's groups: (sources, Finnish, English). Oil of both kinds is one; wood, coal, gas, peat and the rest,
# some 2,200 buildings together, share the last, so that five colours stay apart for colour-blind eyes too.
HEAT = [((1,), "Kaukolämpö", "District heating"), ((4,), "Sähkö", "Electricity"), ((9,), "Maalämpö", "Ground-source heat"),
        ((2, 3), "Öljy", "Oil"), ((5, 6, 7, 8, 10), "Puu, hiili, kaasu tai muu", "Wood, coal, gas or other")]
