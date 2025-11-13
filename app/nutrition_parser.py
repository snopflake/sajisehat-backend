import re
from typing import Optional, Dict


# --------- Helpers dasar --------- #

def _to_float(num_str: str) -> Optional[float]:
    if not num_str:
        return None
    num_str = num_str.replace(",", ".")
    try:
        return float(num_str)
    except ValueError:
        return None


def _all_numbers(line: str) -> list[float]:
    """Ambil semua angka di sebuah baris."""
    nums = []
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)", line):
        v = _to_float(m.group(1))
        if v is not None:
            nums.append(v)
    return nums


# --------- Cleaning teks dari OCR --------- #

def _clean_text(raw_text: str) -> str:
    """
    Bersihkan teks mentah dari OCR:
    - normalisasi ke lower
    - perbaiki pola '7 9' -> '7 g'
    - perbaiki 'takaran saji 209' -> 'takaran saji 20 g'
    - samakan variasi 'sajian/kemasan' -> 'sajian per kemasan'
    """
    text = raw_text.lower()

    # 1. ubah pola "7 9", "11 9" menjadi "7 g", "11 g"
    text = re.sub(r"(\d+)\s+9\b", r"\1 g", text)

    # 2. khusus takaran saji: "takaran saji 209" → "takaran saji 20 g"
    def fix_serving_match(m: re.Match) -> str:
        number_with_9 = m.group(1)  # misal "209"
        if len(number_with_9) >= 2:
            # buang digit terakhir (anggap itu 'g' yang salah baca)
            fixed_number = number_with_9[:-1]
        else:
            fixed_number = number_with_9
        return f"takaran saji {fixed_number} g"

    text = re.sub(r"takaran saji\s*(\d{2,3})9\b", fix_serving_match, text)

    # 3. variasi tulisan sajian per kemasan
    text = re.sub(r"sajian\s*/\s*kemasan", "sajian per kemasan", text)

    return text


# --------- Parser per komponen --------- #

def _parse_serving_size_gram(lines) -> Optional[float]:
    """
    Cari 'takaran saji' dan angka gram.
    Support:
      - "takaran saji 11 g"
      - "takaran saji\n15 g"
    """
    joined = "\n".join(lines)

    # 1) regex multi-baris: angka boleh di baris bawah
    m = re.search(
        r"takaran\s+saji[^\d]{0,40}(\d+(?:[.,]\d+)?)\s*(g|gram|ml)\b",
        joined,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m:
        v = _to_float(m.group(1))
        if v is not None:
            return v

    # 2) fallback: scan per baris, dengan sedikit heuristik
    pattern_line = r"takaran saji[^0-9]{0,10}(\d+(?:[.,]\d+)?)\s*(g|gram|ml)\b"

    for i, line in enumerate(lines):
        if "takaran saji" not in line:
            continue

        # 2a. coba langsung di baris yang sama
        m2 = re.search(pattern_line, line, flags=re.IGNORECASE)
        if m2:
            return _to_float(m2.group(1))

        # 2b. kalau tidak ketemu, lihat 1 baris setelahnya
        if i + 1 < len(lines):
            next_line = line + " " + lines[i + 1]
            m3 = re.search(pattern_line, next_line, flags=re.IGNORECASE)
            if m3:
                return _to_float(m3.group(1))

        # 2c. fallback terakhir: angka pertama di baris
        nums = _all_numbers(line)
        if nums:
            value = nums[0]
            # heuristik ringan: kalau >100 dan diakhiri 9 (209, 309), buang 9
            if value > 100:
                s_int = int(value)
                s_str = str(s_int)
                if s_str.endswith("9") and len(s_str) > 1:
                    return float(s_str[:-1])
            return value

    return None


def _parse_servings_per_pack(lines) -> Optional[int]:
    """
    Cari 'sajian per kemasan' / 'sajian/kemasan' / 'servings per pack' / 'porsi per kemasan'
    lalu ambil angka di depannya.
    Support angka desimal (misal 4.5) → dibulatkan terdekat.
    """
    joined = " ".join(lines)

    pattern = (
        r"(\d+(?:[.,]\d+)?)\s*"
        r"(sajian\s*(?:per|/)?\s*kemasan|servings\s+per\s+pack|porsi\s*(?:per|/)?\s*kemasan)"
    )

    m = re.search(pattern, joined, flags=re.IGNORECASE)
    if m:
        v = _to_float(m.group(1))
        if v is not None:
            return int(round(v))

    # fallback sangat konservatif: cek per baris kalau ada kata kunci kuat
    for line in lines:
        if "sajian" in line and "kemasan" in line:
            nums = _all_numbers(line)
            if nums:
                return int(round(nums[0]))

    return None


def _parse_sugar_per_serving(lines) -> Optional[float]:
    """
    Cari baris yang mengandung 'gula', 'gula total', atau 'sukrosa'.
    - Hanya hitung angka yang diikuti unit g/gram.
    - Kalau ada beberapa angka di baris itu, ambil ANGKA TERAKHIR (biasanya per sajian).
    - Baris yang juga mengandung 'garam' / 'natrium' diabaikan di fallback,
      supaya tidak salah ambil 80 mg Natrium.
    """
    sugar_keywords = ("gula", "sugar", "sukrosa", "sucrose")

    for line in lines:
        if not any(k in line for k in sugar_keywords):
            continue

        # 1) coba cari semua angka yang punya unit g/gram
        matches = re.findall(
            r"(\d+(?:[.,]\d+)?)\s*(g|gram)\b",
            line,
            flags=re.IGNORECASE,
        )
        values = [_to_float(m[0]) for m in matches if _to_float(m[0]) is not None]

        if values:
            # kalau ada banyak angka (tabel 2 kolom), ambil yang terakhir
            return values[-1]

        # 2) kalau tidak ada angka+g, jangan paksa dari angka lain,
        #    karena berisiko salah (contoh: '... Gula Garam (Natrium) 80 mg')
        continue

    return None


def _parse_sugar_per_pack(lines) -> Optional[float]:
    """
    Cari baris dengan 'gula total per kemasan' / 'total sugar per pack'
    dan ambil angka setelahnya.
    (Jarang ada di contoh, jadi seringnya None).
    """
    pattern = (
        r"(gula total per kemasan|total sugar per pack)[^0-9]{0,20}"
        r"(\d+(?:[.,]\d+)?)\s*(g|gram)?"
    )
    for line in lines:
        m = re.search(pattern, line, flags=re.IGNORECASE)
        if m:
            return _to_float(m.group(2))
    return None


# --------- Main function --------- #

def parse_nutrition(raw_text: str) -> Dict:
    """
    Parsing teks label gizi (Indonesia)
    menjadi dictionary nutrisi.
    Fokus ke: takaran saji, jumlah sajian, gula.
    Lebih mengutamakan 'kalau ragu, biarkan null' daripada salah angka.
    """
    cleaned = _clean_text(raw_text or "")
    lines = cleaned.splitlines()

    # 1. Takaran saji
    serving_size_gram = _parse_serving_size_gram(lines)

    # 2. Jumlah sajian per kemasan
    servings_per_pack = _parse_servings_per_pack(lines)

    # 3. Gula per sajian
    sugar_per_serving_gram = _parse_sugar_per_serving(lines)

    # 4. Gula per kemasan
    sugar_per_pack_gram = _parse_sugar_per_pack(lines)

    # 5. Kalau gula per kemasan tidak ada, tapi punya gula per sajian + jumlah sajian
    if (
        sugar_per_pack_gram is None
        and sugar_per_serving_gram is not None
        and servings_per_pack
    ):
        sugar_per_pack_gram = sugar_per_serving_gram * servings_per_pack

    # product_name biarkan None (user isi manual di app)
    product_name = None

    return {
        "raw_text": raw_text,
        "product_name": product_name,
        "serving_size_gram": serving_size_gram,
        "servings_per_pack": servings_per_pack,
        "sugar_per_serving_gram": sugar_per_serving_gram,
        "sugar_per_pack_gram": sugar_per_pack_gram,
    }
