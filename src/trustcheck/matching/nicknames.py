"""
TrustCheck Nickname Database.

Maps common names to their variants, nicknames, and alternative spellings.
This enables matching "Bob Smith" with "Robert Smith", "Mohammed" with "Muhammad", etc.
"""

# Western name nicknames and variants
WESTERN_NICKNAMES: dict[str, set[str]] = {
    # Male names
    "robert": {"bob", "bobby", "rob", "robbie", "bert", "robby"},
    "william": {"will", "bill", "billy", "willy", "willie", "liam"},
    "richard": {"rick", "ricky", "rich", "dick", "dickie", "ritchie"},
    "james": {"jim", "jimmy", "jamie", "jem"},
    "john": {"jack", "johnny", "jon", "jonny", "jock"},
    "michael": {"mike", "mikey", "mick", "mickey"},
    "david": {"dave", "davey", "davy"},
    "thomas": {"tom", "tommy", "thom"},
    "charles": {"charlie", "chuck", "chas", "charley"},
    "joseph": {"joe", "joey", "jo"},
    "edward": {"ed", "eddie", "eddy", "ned", "ted", "teddy"},
    "daniel": {"dan", "danny"},
    "matthew": {"matt", "matty"},
    "anthony": {"tony", "ant"},
    "christopher": {"chris", "kit", "topher"},
    "andrew": {"andy", "drew"},
    "nicholas": {"nick", "nicky", "nico"},
    "peter": {"pete", "petey"},
    "steven": {"steve", "stevie"},
    "stephen": {"steve", "stevie"},
    "benjamin": {"ben", "benny", "benji"},
    "alexander": {"alex", "al", "sandy", "xander"},
    "samuel": {"sam", "sammy"},
    "jonathan": {"jon", "jonny", "nathan"},
    "timothy": {"tim", "timmy"},
    "gregory": {"greg", "gregg"},
    "patrick": {"pat", "patty", "paddy"},
    "kenneth": {"ken", "kenny"},
    "raymond": {"ray", "raymund"},
    "lawrence": {"larry", "laurie"},
    "phillip": {"phil", "pip"},
    "philip": {"phil", "pip"},
    "gerald": {"gerry", "jerry"},
    "donald": {"don", "donny", "donnie"},
    "ronald": {"ron", "ronny", "ronnie"},
    "harold": {"harry", "hal"},
    "henry": {"harry", "hank", "hal"},
    "walter": {"walt", "wally"},
    "frederick": {"fred", "freddy", "freddie", "fritz"},
    "eugene": {"gene"},
    "albert": {"al", "bert", "bertie"},
    "ralph": {"rafe"},
    "arthur": {"art", "artie"},
    "vincent": {"vince", "vinny", "vin"},
    "theodore": {"ted", "teddy", "theo"},
    "zachary": {"zach", "zack"},
    "nathaniel": {"nate", "nat", "nathan"},
    "leonard": {"len", "lenny", "leo"},
    "jacob": {"jake", "jack"},
    "joshua": {"josh"},
    "gabriel": {"gabe"},
    "francis": {"frank", "frankie"},
    "frank": {"frankie"},
    "francis": {"fran", "frank", "frankie"},
    "douglas": {"doug", "dougie"},
    "clifford": {"cliff"},
    "alfred": {"al", "alf", "alfie"},
    "abraham": {"abe"},
    "ignatius": {"iggy"},
    "bartholomew": {"bart"},
    "maximilian": {"max", "maxie"},
    "cornelius": {"neil"},
    "reginald": {"reg", "reggie"},
    "archibald": {"archie"},
    "montgomery": {"monty"},
    # Female names
    "elizabeth": {"beth", "betty", "betsy", "liz", "lizzy", "liza", "eliza", "ellie", "elle", "libby"},
    "margaret": {"meg", "maggie", "peggy", "marge", "margie", "madge", "greta"},
    "jennifer": {"jen", "jenny", "jenn"},
    "jessica": {"jess", "jessie"},
    "katherine": {"kate", "kathy", "katie", "kay", "kitty", "kat"},
    "catherine": {"kate", "cathy", "katie", "kay", "kitty", "kat"},
    "patricia": {"pat", "patty", "tricia", "trish"},
    "rebecca": {"becky", "becca"},
    "virginia": {"ginny", "ginger"},
    "deborah": {"deb", "debbie", "debra"},
    "dorothy": {"dot", "dotty", "dottie"},
    "nancy": {"nan"},
    "barbara": {"barb", "barbie", "babs"},
    "susan": {"sue", "suzy", "susie"},
    "sandra": {"sandy", "sadie"},
    "alexandra": {"alex", "sandy", "lexi"},
    "victoria": {"vicky", "vickie", "tori"},
    "samantha": {"sam", "sammy"},
    "caroline": {"carol", "carrie"},
    "abigail": {"abby", "gail"},
    "jacqueline": {"jackie"},
    "josephine": {"jo", "josie"},
    "rosemary": {"rose", "rosie"},
    "christine": {"chris", "chrissy", "tina"},
    "christina": {"chris", "chrissy", "tina"},
    "madeleine": {"maddie", "maddy"},
    "madeline": {"maddie", "maddy"},
    "penelope": {"penny"},
    "priscilla": {"cilla"},
    "constance": {"connie"},
    "florence": {"flo", "flossie"},
    "beatrice": {"bea", "trixie"},
    "winifred": {"winnie"},
    "theodora": {"thea", "dora"},
    "antoinette": {"toni"},
}

# Arabic/Islamic name variants
ARABIC_NAME_VARIANTS: dict[str, set[str]] = {
    # Muhammad variants (very important - most common name)
    "muhammad": {"mohammed", "mohamed", "mohammad", "muhammed", "mohamad", "muhamed", "muhamad", "mehmet", "mahmud", "mahmoud", "mahmood", "mamadou", "mahommed", "mohamet"},
    "mohammed": {"muhammad", "mohamed", "mohammad", "muhammed", "mohamad", "muhamed", "muhamad", "mehmet"},
    "ahmed": {"ahmad", "ahmet", "ахмед", "ахмад"},
    "ahmad": {"ahmed", "ahmet"},
    "ali": {"aly"},
    "abdullah": {"abdallah", "abdulla", "abdellah", "abdollah"},
    "abdul": {"abdel", "abd"},
    "abdulrahman": {"abdurrahman", "abdelrahman", "abdul rahman", "abd al-rahman"},
    "abdulaziz": {"abdulazis", "abdelaziz", "abdul aziz", "abd al-aziz"},
    "abdulkarim": {"abdelkarim", "abdul karim", "abd al-karim"},
    "abdulmajid": {"abdelmajid", "abdul majid", "abd al-majid"},
    "ibrahim": {"ebrahim", "ibraheem", "abrahim", "abraham"},
    "ismail": {"ismaeel", "ismael", "ishmael"},
    "yusuf": {"youssef", "yousef", "yousuf", "yusef", "josef", "joseph"},
    "hassan": {"hasan", "hasson"},
    "hussein": {"hussain", "husain", "husein", "hossein", "hosein"},
    "omar": {"umar", "omer"},
    "osman": {"uthman", "othman"},
    "khalid": {"khaled"},
    "karim": {"kareem", "kerim"},
    "nasser": {"nasir", "nasr", "naser"},
    "salah": {"saleh", "salih"},
    "tariq": {"tarek", "tarik"},
    "jamal": {"gamal", "jemal"},
    "faisal": {"faysal", "feisal"},
    "rashid": {"rasheed"},
    "hamid": {"hameed"},
    "walid": {"waleed"},
    "fahd": {"fahad"},
    "saeed": {"said", "saeid"},
    "mansour": {"mansur", "mansor"},
    "mustafa": {"mustapha", "mostafa"},
    "zaid": {"zayed", "zayd"},
    "suleiman": {"sulaiman", "sulayman", "suleyman", "solomon"},
    "hakim": {"hakeem"},
    "latif": {"lateef"},
    "amin": {"ameen"},
    "aziz": {"azeez"},
    "bashar": {"basher", "bashir"},
    "bilal": {"belal"},
    "daud": {"daoud", "dawud", "dawoud", "david"},
    "fouad": {"fuad", "fawad"},
    "habib": {"habeeb"},
    "hadi": {"hadee"},
    "hafiz": {"hafeez"},
    "iqbal": {"eqbal"},
    "jalal": {"galal"},
    "jamil": {"jameel", "gameel"},
    "majid": {"majeed"},
    "malik": {"malek", "malak"},
    "marwan": {"merwan"},
    "mubarak": {"mubarek"},
    "muhsin": {"mohsen"},
    "munir": {"muneer"},
    "nabil": {"nabeel"},
    "nadim": {"nadeem"},
    "rafiq": {"rafik", "rafeek"},
    "rahim": {"raheem"},
    "rami": {"ramee"},
    "sabir": {"sabeer"},
    "samir": {"sameer"},
    "shakir": {"shakeer", "shaker"},
    "sharif": {"shareef", "sherif"},
    "taha": {"tahaa"},
    "wajid": {"wajeed"},
    "wasim": {"waseem"},
    "yasir": {"yasser", "yaser"},
    "zaki": {"zaky"},
    # Common female names
    "aisha": {"ayesha", "aishah", "aysha"},
    "fatima": {"fatimah", "fatma", "fatouma"},
    "khadija": {"khadijah", "khadega"},
    "maryam": {"mariam", "maryum", "miriam"},
    "layla": {"leila", "laila", "leyla"},
    "zainab": {"zeinab", "zaynab"},
    "hana": {"hanaa", "hannah"},
    "nadia": {"nadya"},
    "sara": {"sarah", "sahra"},
    "yasmin": {"jasmin", "yasmeen", "jasmine"},
}

# Russian/Slavic name variants
SLAVIC_NAME_VARIANTS: dict[str, set[str]] = {
    "alexander": {"aleksandr", "aleksander", "oleksandr", "alexandr", "sasha"},
    "alexei": {"alexey", "aleksei", "aleksey", "alyosha"},
    "andrei": {"andrey", "andrej"},
    "boris": {"borys"},
    "dmitri": {"dmitry", "dmitriy", "dmytro"},
    "igor": {"ihor"},
    "ivan": {"iwan", "jan"},
    "mikhail": {"mikhael", "mikail", "misha"},
    "nikolai": {"nikolay", "mykola", "nicholai"},
    "pavel": {"pavlo"},
    "pyotr": {"petr", "peter", "petro"},
    "sergei": {"sergey", "serhiy", "serge"},
    "viktor": {"victor", "wiktor"},
    "vladimir": {"volodymyr", "wladimir", "vlad"},
    "yuri": {"yury", "yuriy", "jurij"},
    "vasili": {"vasily", "vasiliy", "basil"},
    "grigori": {"grigory", "grigoriy", "gregory"},
    "maxim": {"maksim"},
    "oleg": {"oleh"},
    "roman": {"romaan"},
    "stanislav": {"stanislau"},
    "yaroslav": {"jaroslav"},
    # Female names
    "anastasia": {"nastya", "nastasia"},
    "ekaterina": {"katerina", "katya", "catherine"},
    "elena": {"yelena", "helen", "helena"},
    "irina": {"iryna"},
    "maria": {"mariya", "marya"},
    "natalya": {"natalia", "natasha"},
    "olga": {"olha"},
    "svetlana": {"svitlana"},
    "tatiana": {"tatyana", "tanya"},
    "valentina": {"valya"},
    "yulia": {"julia", "yuliya"},
}


def build_reverse_lookup() -> dict[str, str]:
    """Build a reverse lookup from variant to canonical name."""
    reverse: dict[str, str] = {}

    for variants_dict in [WESTERN_NICKNAMES, ARABIC_NAME_VARIANTS, SLAVIC_NAME_VARIANTS]:
        for canonical, variants in variants_dict.items():
            # Canonical maps to itself
            reverse[canonical.lower()] = canonical.lower()
            # Each variant maps to canonical
            for variant in variants:
                reverse[variant.lower()] = canonical.lower()

    return reverse


# Pre-computed reverse lookup
_REVERSE_LOOKUP = build_reverse_lookup()


def get_canonical_name(name: str) -> str:
    """Get the canonical form of a name if it's a known variant."""
    return _REVERSE_LOOKUP.get(name.lower(), name.lower())


def get_name_variants(name: str) -> set[str]:
    """
    Get all known variants of a name.

    Returns the original name plus any known nicknames/variants.
    """
    name_lower = name.lower()
    variants: set[str] = {name_lower}

    # Check each dictionary
    for variants_dict in [WESTERN_NICKNAMES, ARABIC_NAME_VARIANTS, SLAVIC_NAME_VARIANTS]:
        # Check if name is a canonical name
        if name_lower in variants_dict:
            variants.update(variants_dict[name_lower])

        # Check if name is a variant (find its canonical and get all variants)
        for canonical, var_set in variants_dict.items():
            if name_lower in var_set or name_lower == canonical:
                variants.add(canonical)
                variants.update(var_set)

    return variants


def expand_name_with_variants(full_name: str) -> set[str]:
    """
    Expand a full name with all possible variant combinations.

    E.g., "Muhammad Ali" -> {"Muhammad Ali", "Mohammed Ali", "Mohamed Ali", ...}
    """
    words = full_name.split()
    if not words:
        return {full_name}

    # Get variants for each word
    word_variants: list[set[str]] = []
    for word in words:
        variants = get_name_variants(word)
        # Always include the original
        variants.add(word.lower())
        word_variants.append(variants)

    # Combine variants (limit to avoid explosion)
    from itertools import product

    results: set[str] = set()

    # Limit combinations
    max_per_word = 5
    limited_variants = [list(v)[:max_per_word] for v in word_variants]

    for combo in product(*limited_variants):
        results.add(" ".join(combo))
        if len(results) >= 50:  # Hard limit
            break

    return results


def names_are_variants(name1: str, name2: str) -> bool:
    """
    Check if two names (or any of their words) are known variants of each other.
    """
    # Check full names
    canonical1 = get_canonical_name(name1)
    canonical2 = get_canonical_name(name2)

    if canonical1 == canonical2:
        return True

    # Check individual words
    words1 = set(name1.lower().split())
    words2 = set(name2.lower().split())

    for w1 in words1:
        c1 = get_canonical_name(w1)
        for w2 in words2:
            c2 = get_canonical_name(w2)
            if c1 == c2 and c1 != w1 and c2 != w2:
                # Both map to the same canonical and neither is the canonical itself
                # (meaning they're variants)
                return True

    # Check if any words are in each other's variant sets
    for w1 in words1:
        variants1 = get_name_variants(w1)
        for w2 in words2:
            if w2 in variants1:
                return True

    return False
