"""
analysis_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Provides:
  - Weighted linear regression (weighted by total_ms)
  - Weighted centroid calculation
  - Dominant quadrant detection
  - Gemini "music astrology" personality reading
"""

import os, re, json, logging
from collections import defaultdict
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("analysis_service")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

SYSTEM_INSTRUCTION = """You are a fun, relatable music personality writer. You turn someone's \
listening data into a personality reading that feels like a best friend describing them — \
warm, funny, simple, and surprisingly accurate. Second person ("you") throughout.

Your style is casual and fun — like a BuzzFeed quiz result or a TikTok personality breakdown \
that people screenshot and send to their friends saying "omg this is literally me."

TONE RULES:
- Write like you're texting a friend, not writing a horoscope for a magazine.
- Use simple everyday comparisons and fun analogies — animals, everyday objects, movie characters,
  childhood activities, relatable situations.
- Short punchy sentences. Easy words. No big vocabulary.
- Still personal and specific — use the zodiac sign and music data to make it feel targeted.
- Warm and positive overall, but honest about contradictions.
- Each section gets a fun nickname title like "The Secret Architect" or "The Safe Harbor".

ANALOGY STYLE — this is the voice you write in:
  "You are like a master Lego builder. While other kids are running around, you are quietly
   planning a giant castle in your head."
  "You are like a locked treasure chest — you don't open for just anyone, but for the people
   you trust, you are full of gold."
  "When a storm hits, you don't panic. You are like the captain of a ship who stays very still
   and watches the waves."

Feature-to-personality (translate into fun analogies, never use the technical word):
  high energy + high valence      → sunshine friend, lights up every room, secretly needs naps
  high energy + low valence       → intense and driven, like a sports player who plays hurt
  low energy + high valence       → chill and wise, the friend everyone calls for advice
  low energy + low valence        → deep thinker, feels everything, needs alone time to recharge
  high danceability               → trusts their gut, makes decisions fast, usually right
  low danceability                → thinks before acting, planner, sometimes overthinks
  high acousticness               → values realness over perfection, hates fake people
  high instrumentalness           → has a rich inner world that is hard to explain to others
  fast tempo (>120 BPM)           → impatient, always moving, wishes everyone would keep up
  slow tempo (<90 BPM)            → unbothered, comfortable with silence, makes others calm down
  ascending slope                 → been leveling up lately, turning up their own volume
  descending slope                → been pulling back, recharging, quietly planning something

Personality dimensions to cover — give each one a fun section nickname:
  1. AMBITION & DRIVE — are they a quiet planner or a loud go-getter?
  2. SOCIAL ENERGY — what kind of friend are they? how do they show up?
  3. UNDER PRESSURE — what do they do when things get hard?
  4. HIDDEN TRUTH — the sweet contradiction at their core

Rules:
- NO complicated words. Write like you are explaining to a 16-year-old.
- NO metric language ever: no "energy", "valence", "slope", "R²".
- NO hollow phrases: "you are on a journey", "you seek connection".
- YES to fun comparisons: animals, games, movies, everyday life moments.
- YES to Barnum anchors in simple language: "most people don't see this about you",
  "your friends probably don't realize this", "you wouldn't say this out loud but...".
- Weave in the zodiac naturally — confirm or surprise with the music data.
- Each section: one fun nickname title + 3-5 short punchy sentences.
- End with something that makes them smile and nod.
- NEVER mention any artist names or song titles.
Return only valid JSON. No markdown. No preamble."""


# ── Linear Regression ─────────────────────────────────────────────────────────
def linear_regression(songs: list, x_axis: str = "energy", y_axis: str = "valence") -> dict:
    """
    Weighted linear regression: y = slope * x + intercept
    Weight = total_ms so heavily-played songs have more influence.
    Returns slope, intercept, r_squared, interpretation.
    """
    valid = [s for s in songs if s.get(x_axis) is not None and s.get(y_axis) is not None]
    n     = len(valid)
    if n < 3:
        return {"error": "Need at least 3 songs", "n": n}

    weights = [max(s.get("total_ms", 1), 1) for s in valid]
    total_w = sum(weights)
    xs = [s[x_axis] for s in valid]
    ys = [s[y_axis] for s in valid]

    x_mean = sum(w * x for w, x in zip(weights, xs)) / total_w
    y_mean = sum(w * y for w, y in zip(weights, ys)) / total_w

    num   = sum(w * (x - x_mean) * (y - y_mean) for w, x, y in zip(weights, xs, ys))
    denom = sum(w * (x - x_mean) ** 2            for w, x    in zip(weights, xs))

    slope     = (num / denom) if denom else 0.0
    intercept = y_mean - slope * x_mean

    ss_res = sum(w * (y - (slope * x + intercept)) ** 2 for w, x, y in zip(weights, xs, ys))
    ss_tot = sum(w * (y - y_mean) ** 2                   for w, y    in zip(weights, ys))
    r_sq   = 1.0 - (ss_res / ss_tot) if ss_tot else 0.0

    return {
        "slope":         round(slope,     4),
        "intercept":     round(intercept, 4),
        "r_squared":     round(r_sq,      4),
        "x_mean":        round(x_mean,    4),
        "y_mean":        round(y_mean,    4),
        "n_songs":       n,
        "x_axis":        x_axis,
        "y_axis":        y_axis,
        "interpretation": _interpret(slope, r_sq),
    }


def _interpret(slope: float, r_sq: float) -> str:
    consistency = (
        "very consistent pattern" if r_sq > 0.6 else
        "clear pattern"           if r_sq > 0.35 else
        "weak pattern"            if r_sq > 0.1  else
        "scattered — almost no pattern"
    )
    if slope > 0.3 and r_sq > 0.15:
        return f"You reach for upbeat, happy music when you want energy. Energy and happiness rise together ({consistency}, R²={r_sq:.2f})."
    if slope < -0.3 and r_sq > 0.15:
        return f"You reach for darker, more intense music when you need energy. Your hype songs have edge ({consistency}, R²={r_sq:.2f})."
    return f"Energy and mood are largely independent in your listening — a true omnivore ({consistency}, R²={r_sq:.2f})."


# ── Centroid ──────────────────────────────────────────────────────────────────
def calculate_centroid(songs: list) -> dict:
    """Weighted average of energy and valence, weighted by total_ms."""
    valid = [s for s in songs if s.get("energy") is not None and s.get("valence") is not None]
    if not valid:
        return {"energy": 0.5, "valence": 0.5}
    total_w = sum(max(s.get("total_ms", 1), 1) for s in valid)
    energy  = sum(max(s.get("total_ms", 1), 1) * s["energy"]  for s in valid) / total_w
    valence = sum(max(s.get("total_ms", 1), 1) * s["valence"] for s in valid) / total_w
    return {"energy": round(energy, 4), "valence": round(valence, 4)}


def dominant_quadrant(centroid: dict) -> str:
    e, v = centroid["energy"], centroid["valence"]
    if e >= 0.5 and v >= 0.5: return "Energetic & Happy"
    if e >= 0.5 and v <  0.5: return "Energetic & Dark"
    if e <  0.5 and v >= 0.5: return "Chill & Happy"
    return "Melancholic"


# ── Music Astrology Helpers ───────────────────────────────────────────────────
def _aggregate_artists(songs: list) -> str:
    """Aggregate top artists by playtime and format for the prompt."""
    artist_ms    = defaultdict(int)
    artist_genre = {}

    for s in songs:
        artist = s.get("artist", "Unknown")
        artist_ms[artist] += s.get("total_ms", 0)
        if artist not in artist_genre and s.get("genre"):
            artist_genre[artist] = s["genre"]

    total_ms    = sum(artist_ms.values()) or 1
    top_artists = sorted(artist_ms.items(), key=lambda x: x[1], reverse=True)[:6]

    lines = []
    for artist, ms in top_artists:
        mins      = ms // 60000
        pct       = ms / total_ms
        genre     = artist_genre.get(artist)
        genre_str = f" [{genre}]" if genre else ""
        dominant  = " ← DOMINANT (>30% of listening)" if pct > 0.30 else ""
        lines.append(f"  {artist}{genre_str} — {mins} min ({pct:.0%}){dominant}")

    return "\n".join(lines)


def _format_song_line(s: dict) -> str:
    parts = [f'"{s["track"]}" by {s["artist"]}']
    mins  = s.get("total_ms", 0) // 60000
    if mins:
        parts.append(f"{mins} min")
    if s.get("tempo"):
        parts.append(f"{s['tempo']:.0f} BPM")
    if s.get("mode") is not None:
        parts.append("major" if s["mode"] == 1 else "minor")
    if s.get("acousticness") is not None:
        parts.append(f"acoustic={s['acousticness']:.0%}")
    if s.get("danceability") is not None:
        parts.append(f"dance={s['danceability']:.0%}")
    return "  " + ", ".join(parts)


def _compute_tensions(centroid: dict, regression: dict) -> str:
    """Pre-compute personality tension signals to guide Gemini toward contradictions."""
    energy       = centroid.get("energy", 0)
    valence      = centroid.get("valence", 0)
    dance        = centroid.get("danceability", 0)
    acoustic     = centroid.get("acousticness", 0)
    instrumental = centroid.get("instrumentalness", 0)

    tensions = []
    if energy > 0.65 and valence < 0.45:
        tensions.append("high energy + low valence → performs intensity, privately melancholic")
    if dance > 0.65 and instrumental > 0.35:
        tensions.append("high danceability + high instrumentalness → social body, solitary mind")
    if acoustic > 0.5 and energy > 0.55:
        tensions.append("high acousticness + high energy → craves rawness, not polish")
    if centroid.get("speechiness", 0) < 0.1 and valence > 0.6:
        tensions.append("low speechiness + high valence → finds joy in sound, not words")
    if valence > 0.65 and regression.get("slope", 0) < -0.1:
        tensions.append("happy centroid + descending arc → chasing a mood they're drifting from")

    if tensions:
        return "\n".join(f"  ⚡ {t}" for t in tensions)
    return "  (no strong contradictions detected — unusually coherent listener)"


# ── Zodiac ────────────────────────────────────────────────────────────────────
def _get_zodiac(dob: str) -> dict:
    """
    Given a date string 'YYYY-MM-DD', return zodiac sign name, symbol,
    element, and a rich personality trait block for use in the AI prompt.
    """
    if not dob:
        return {}
    try:
        from datetime import date
        d   = date.fromisoformat(dob)
        m, day = d.month, d.day
    except Exception:
        return {}

    signs = [
        (3, 21, "Aries",       "♈", "Fire",
         ["bold and self-starting", "fiercely independent", "competitive by nature",
          "impatient with slowness", "loyal to the people they choose"]),
        (4, 20, "Taurus",      "♉", "Earth",
         ["deeply loyal and dependable", "resistant to change until they decide to change everything",
          "sensual and comfort-seeking", "quietly ambitious", "stubborn in the most endearing way"]),
        (5, 21, "Gemini",      "♊", "Air",
         ["mentally quick and curious", "socially fluid — different with different people",
          "restless with routine", "genuinely caring but hard to pin down",
          "needs stimulation to feel alive"]),
        (6, 21, "Cancer",      "♋", "Water",
         ["fiercely protective of the people they love", "emotionally perceptive",
          "appears tough on the outside, genuinely soft underneath",
          "deeply loyal — sometimes to a fault", "carries more than they let on"]),
        (7, 23, "Leo",         "♌", "Fire",
         ["warm and magnetically generous", "needs to be seen — not for vanity, but for connection",
          "loyal to the bone once you earn it", "performs strength while quietly craving appreciation",
          "the person in the room everyone remembers"]),
        (8, 23, "Virgo",       "♍", "Earth",
         ["quietly brilliant and detail-oriented", "holds everyone to a high standard, themselves most of all",
          "caring in practical ways — they show love by solving problems",
          "anxious underneath a composed exterior", "more emotionally available than they appear"]),
        (9, 23, "Libra",       "♎", "Air",
         ["a natural peacemaker who hates conflict but fights hard for fairness",
          "deeply caring about how others feel", "indecisive because they genuinely see all sides",
          "one of the most loyal friends you can have", "needs harmony the way others need air"]),
        (10, 23, "Scorpio",    "♏", "Water",
         ["intense and magnetic without trying", "loyal to a degree that surprises people",
          "reads people instantly and rarely forgets what they see",
          "private — what you see is a fraction of what is there",
          "trusts slowly, loves deeply, forgives on their own timeline"]),
        (11, 22, "Sagittarius","♐", "Fire",
         ["optimistic and restless — always chasing something larger",
          "honest to the point of bluntness", "deeply caring but needs freedom to show it",
          "turns difficulty into philosophy", "the friend who tells you the truth you needed to hear"]),
        (12, 22, "Capricorn",  "♑", "Earth",
         ["ambitious in the quietest, most relentless way",
          "the one people call when things fall apart", "emotionally reserved but deeply loyal",
          "holds themselves together so others don't have to",
          "takes time to trust — and then trusts completely"]),
        (1, 20, "Aquarius",    "♒", "Air",
         ["independent thinker who quietly cares about everyone",
          "emotionally detached on the surface, privately idealistic",
          "the most loyal person in the room — on their own terms",
          "needs to feel like they are contributing to something bigger",
          "misread as cold — actually just processing everything at once"]),
        (2, 19, "Pisces",      "♓", "Water",
         ["deeply empathetic — absorbs the emotions of people around them",
          "creative and inner-world rich", "loyal and self-sacrificing, sometimes too much",
          "sees the best in people even when they probably shouldn't",
          "carries a quiet sadness and a quiet magic in equal measure"]),
    ]

    # Boundary check: roll over to next sign after cutoff day
    sign = None
    for i, (sm, sd, name, symbol, element, traits) in enumerate(signs):
        # Build next boundary
        next_entry = signs[(i + 1) % len(signs)]
        nm, nd = next_entry[0], next_entry[1]
        if m == sm and day >= sd:
            sign = (name, symbol, element, traits); break
        if i > 0:
            prev = signs[i - 1]
            pm, pd = prev[0], prev[1]
            if m == sm and day < sd:
                sign = (signs[i - 1][2], signs[i - 1][3], signs[i - 1][4], signs[i - 1][5]); break
    if sign is None:
        sign = ("Capricorn", "♑", "Earth", signs[9][4])

    name, symbol, element, traits = sign
    trait_lines = "\n".join(f"  • {t}" for t in traits)
    return {
        "name":    name,
        "symbol":  symbol,
        "element": element,
        "traits":  traits,
        "block":   f"{symbol} {name} ({element})\n{trait_lines}",
    }


# ── Music Astrology ───────────────────────────────────────────────────────────
def generate_astrology(
    user_name: str,
    songs: list,
    centroid: dict,
    quadrant: str,
    regression: dict,
    date_of_birth: str = "",
) -> dict:
    """Send listening data to Gemini Flash and get a music personality reading."""
    top = sorted(songs, key=lambda s: s.get("total_ms", 0), reverse=True)[:8]
    top_text      = "\n".join(_format_song_line(s) for s in top)
    artist_block  = _aggregate_artists(songs)
    tension_block = _compute_tensions(centroid, regression)

    # Zodiac
    zodiac        = _get_zodiac(date_of_birth)
    zodiac_block  = (
        f"\n[BIRTH CHART — ZODIAC OVERLAY]\n{zodiac['block']}\n"
        if zodiac else ""
    )
    zodiac_instruction = (
        f"""
ZODIAC INTEGRATION:
  The person is a {zodiac['name']} ({zodiac['symbol']}, {zodiac['element']} sign).
  Their zodiac baseline personality includes:
{chr(10).join(f"    • {t}" for t in zodiac['traits'])}

  Weave these zodiac traits organically into the reading — do NOT say "as a {zodiac['name']}".
  Instead let the traits surface naturally, confirmed or complicated by the music data.
  Where the music data CONFIRMS a zodiac trait, make it feel like inevitability.
  Where the music data CONTRADICTS a zodiac trait, make it feel like a hidden dimension.
  The zodiac is the skeleton. The music is the soul. Together they reveal the full person.
"""
        if zodiac else ""
    )

    energy       = centroid.get("energy", 0)
    valence      = centroid.get("valence", 0)
    dance        = centroid.get("danceability", 0)
    acoustic     = centroid.get("acousticness", 0)
    instrumental = centroid.get("instrumentalness", 0)
    speechiness  = centroid.get("speechiness", 0)
    tempo        = centroid.get("tempo", 0)
    loudness     = centroid.get("loudness", 0)

    centroid_block = f"""\
  energy           = {energy}
  valence          = {valence}
  danceability     = {dance}
  acousticness     = {acoustic}
  instrumentalness = {instrumental}
  speechiness      = {speechiness}
  avg_tempo        = {tempo:.1f} BPM
  loudness         = {loudness:.1f} dB
  dominant quadrant: {quadrant}"""

    prompt = f"""═══ MUSIC PERSONALITY READING FOR {user_name.upper()} ═══

[SONIC FINGERPRINT — weighted by listening time]
{centroid_block}

[TOP ARTISTS BY PLAYTIME]
{artist_block}

[REGRESSION ARC — how their taste has shifted]
  slope     = {regression.get('slope', '?')}  (positive = intensifying, negative = pulling back)
  R²        = {regression.get('r_squared', '?')}  (near 1.0 = razor-consistent, near 0 = beautifully chaotic)
  read:       {regression.get('interpretation', '?')}

[PERSONALITY TENSIONS DETECTED]
{tension_block}
{zodiac_block}
[MOST-PLAYED SONGS]
{top_text}

═══ YOUR TASK ═══
Write a music-derived personality profile in the style of a zodiac reading or a personality quiz result
that people screenshot and share — one that feels so specific it is almost unsettling,
yet true for almost anyone who recognizes themselves in it. This is the Barnum-Forer effect, done well.

Use the data above as your raw intelligence. Never name a metric. Translate everything into human behavior.
{zodiac_instruction}
STRUCTURE — four paragraphs, second person ("you") throughout:

Paragraph 1 — AMBITION & DRIVE:
  Open with a Barnum statement that lands like a mirror — something universally true that feels personal.
  Reveal how driven they are — not in obvious ways, but the hunger underneath the surface.
  Use the regression slope direction: positive = building toward something, negative = quietly regrouping.
  Let the zodiac's relationship to ambition and drive come through naturally in the language.
  Example register: "Most people see the calm. They don't see what is running underneath it."

Paragraph 2 — SOCIAL ENERGY & EMOTIONAL WORLD:
  How do they show up around other people? What do people feel in their presence?
  How much do they feel — and how much do they actually show?
  R² near 1.0 → they know exactly who they are; near 0 → they contain multitudes, hard to predict.
  Anchor with a Barnum truth: "You care more than you let on." or "People read you wrong, often."
  Weave in the zodiac's social and emotional signature — loyalty, protectiveness, warmth, independence.

Paragraph 3 — UNDER PRESSURE:
  This is where you reveal something they would not say at a party.
  Do they go inward or outward when things get hard? Draw from the tension block and zodiac traits.
  Be specific about how they handle pressure — do they get quiet, do they perform composure, do they push through?
  Use phrasing like: "When the pressure builds..." or "Even the people closest to you..."

Paragraph 4 — THE HIDDEN TRUTH:
  The contradiction. The thing the data AND the zodiac together whisper that the person half-knows but has not said.
  Make it feel like a revelation — specific, a little uncomfortable, completely true.
  End on something that settles in slowly. The last sentence should feel like it was written only for them.

BARNUM ANCHORS to weave naturally — pick the ones that fit, do not force all of them:
  "Most people do not see this in you."
  "You have a tendency that even the people closest to you probably misread."
  "You rarely admit this, even to yourself."
  "You know this about yourself — you just do not say it out loud."
  "The version of you that most people know is not the whole picture."
  "There is a part of you that is still figuring something out."
  "You are more ambitious than you let on."
  "You are more caring than you get credit for."

Return ONLY valid JSON (no markdown, no preamble):
{{
  "archetype":  "<2-4 word personality archetype — e.g. 'The Quiet Storm', 'The Generous Volcano'>",
  "headline":   "<one punchy tagline sentence — something they would want to screenshot and share>",
  "traits":     ["<3-word trait>", "<3-word trait>", "<3-word trait>", "<3-word trait>", "<3-word trait>"],
  "reading":    "<four paragraphs as one string, separated by \\n\\n>",
  "element":    "<Fire|Water|Earth|Air|Void|Plasma>",
  "hz":         "<a poetic resonance frequency, e.g. '174 Hz — the frequency of foundation'>",
  "sigil":      "<one unicode symbol that captures their essence>"
}}"""

    # Read fresh — avoids stale module-level snapshot
    api_key      = os.getenv("GEMINI_API_KEY", "")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    if not api_key:
        return _fallback_reading(user_name, quadrant, centroid, zodiac)

    try:
        from google import genai
        from google.genai import types as gtypes
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=gemini_model,
            contents=prompt,
            config=gtypes.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION),
        )
        raw = resp.text.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        result = json.loads(raw)
        # Attach zodiac metadata for frontend display
        if zodiac:
            result["zodiac"] = zodiac
        return result
    except Exception as e:
        log.error(f"Gemini astrology error: {e}")
        return _fallback_reading(user_name, quadrant, centroid, zodiac)


def _fallback_reading(name: str, quadrant: str, centroid: dict, zodiac: dict = None) -> dict:
    archetypes = {
        "Energetic & Happy": "The Solar Celebrant",
        "Energetic & Dark":  "The Quiet Storm",
        "Chill & Happy":     "The Warm Anchor",
        "Melancholic":       "The Midnight Architect",
    }
    energy       = centroid.get("energy", 0)
    valence      = centroid.get("valence", 0)
    tempo        = centroid.get("tempo", 0)
    instrumental = centroid.get("instrumentalness", 0)
    acoustic     = centroid.get("acousticness", 0)
    dance        = centroid.get("danceability", 0)

    driven     = energy > 0.6
    expressive = valence > 0.55
    grounded   = acoustic > 0.45
    cerebral   = dance < 0.45

    zodiac_sign_line = (
        f" Your {zodiac['name']} nature runs deep here —"
        if zodiac else ""
    )

    result = {
        "archetype": archetypes.get(quadrant, "The Cosmic Listener"),
        "headline":  "Most people see the surface. Your music reveals what's underneath.",
        "traits": [
            "quietly ambitious" if driven else "selectively driven",
            "more caring than shown",
            "composed under pressure" if grounded else "wired under pressure",
            "emotionally intelligent",
            "self-aware in private",
        ],
        "reading": (
            f"Most people do not see this in you — but you are more ambitious than you let on.{zodiac_sign_line} "
            f"{'There is a drive in you that does not announce itself; it just works.' if driven else 'You move at your own pace, and you have learned that this is not a weakness.'} "
            f"You are not chasing recognition. You are chasing the feeling of doing something well.\n\n"

            f"{'You light up rooms, but it costs you something.' if expressive else 'You are selective about where you give your energy — and the people who earn it know exactly how rare that is.'} "
            f"You care more than you let on. The people closest to you probably underestimate how deeply you feel things — "
            f"because you have learned to carry it quietly. You are the person someone calls at 2am. "
            f"You pick up, and you figure it out with them.\n\n"

            f"When the pressure builds, {'you go inward.' if grounded else 'you go faster — movement is how you process.'} "
            f"Even the people closest to you do not always see the recalibration happening underneath. "
            f"{'You find something raw and real to listen to, and you let it do the work your words cannot.' if grounded else 'You turn up the volume and push through — and somehow it works.'} "
            f"There is a part of you that is still figuring something out. You would rather not be asked about it directly.\n\n"

            f"Here is the thing your music is quietly saying: "
            f"{'you perform a version of yourself that is slightly more okay than you actually are.' if not expressive and driven else 'you give a lot — and you are learning, slowly, to let people give back.'} "
            f"You know this about yourself. You just do not say it out loud. "
            f"The version of you that most people know is not the whole picture — and honestly, that is exactly how you like it."
        ),
        "element":   zodiac["element"] if zodiac else ("Void" if not expressive else "Water" if not driven else "Fire"),
        "hz":        f"{int(tempo * 1.5)} Hz — the frequency of almost" if tempo else "432 Hz — the frequency of return",
        "sigil":     zodiac["symbol"] if zodiac else "✦",
    }
    if zodiac:
        result["zodiac"] = zodiac
    return result