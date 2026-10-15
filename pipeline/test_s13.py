"""Self-check for finding where people lived: uv run python -m pipeline.test_s13"""
import re

from .s13_residents import found_in, in_buildings, lived, sentences, surname_stem

address = re.compile(r"\b(?P<street>Bulevardi|Kauppakatu|Fredrikinkatu)\s+(?P<num>\d{1,3}[a-zåäö]?)\b")
text = ("Jean Sibelius syntyi Hämeenlinnassa 8. joulukuuta 1865. Vuonna 1889 hän muutti Helsinkiin. "
        "Hän asui Bulevardi 5:ssä vuoteen 1890. J. L. Runeberg ei asunut täällä. "
        "Sibeliuksen perhe asui myöhemmin Fredrikinkatu 12:ssa Helsingissä. "
        "Hän asui Turussa Kauppakatu 5:ssä. Hänet haudattiin Helsingissä, Bulevardi 9 lähellä. "
        "Kauppakatu 3 Helsingissä oli kauppa.")
assert sentences("Teos valmistui 1920. Hän muutti. J. L. Runeberg asui.") == [" Teos valmistui 1920.", "Hän muutti.", "J. L. Runeberg asui."]
assert surname_stem("Jean Sibelius") == "sibeli" and surname_stem("Aleksis Kivi") == "kiv"
assert lived("suomalainen arkkitehti (1898–1976)") == "suomalainen arkkitehti" and lived(None) == ""
assert found_in(text, surname_stem("Jean Sibelius"), address) == [
    ("Bulevardi 5", "Hän asui Bulevardi 5:ssä vuoteen 1890."),  # Helsinki named in the sentence before
    ("Fredrikinkatu 12", "Sibeliuksen perhe asui myöhemmin Fredrikinkatu 12:ssa Helsingissä."),
]  # not Turku's Kauppakatu, not a burial, not a sentence about no one

# A building's own article: the people linked where it says who lived in the house; not its architect, a neighbour,
# someone's kin, or a sentence about another house
article = {"K1": ("Lallukka", "'''Lallukka''' on talo. Talossa asuivat mm. [[Eino Leino]] ja [[Akseli Gallen-Kallela|Gallen-Kallela]]. "
                  "[[Lars Sonck]] suunnitteli talon, jossa asui [[Juhani Aho]]. Siellä asui myös [[Aino Ackté]], [[Albert Edelfelt]]in tytär. "
                  "[[Edvin Laine]] asui naapuritalossa. [[Urho Kekkonen]] muutti Tamminiemeen, jossa hän asui. "
                  "Talon asukkaisiin kuului [[Nikolai Bobrikov]]in leikannut kirurgi [[Richard Faltin]]. "
                  "Talossa oli [[Juhani Aho]]n koti, ja siellä asui myös [[Tarja Halonen]]. "
                  "Talossa asuivat sisarukset [[Annie Edelfelt|Annie]], joiden isä oli arkkitehti [[Carl Albert Edelfelt]] ja veli [[Albert Edelfelt|Albert]].")}
assert [t for _, t, _ in in_buildings(article)] == ["Eino Leino", "Akseli Gallen-Kallela", "Aino Ackté", "Richard Faltin",
                                                    "Juhani Aho", "Tarja Halonen", "Annie Edelfelt"], in_buildings(article)
assert in_buildings(article)[0][2] == "Talossa asuivat mm. Eino Leino ja Gallen-Kallela."
print("ok")
