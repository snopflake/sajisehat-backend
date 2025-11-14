# app/nutrition_parser.py
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
    text = (raw_text or "").lower()

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
      - "takaran saji 1 4 g"  (OCR mis-split '14 g')
      - "takaran saji\n1 4 g"
    """
    if not lines:
        return None

    joined_all = "\n".join(lines)

    # --- 1) regex multi-baris: angka utuh diikuti unit ---
    m = re.search(
        r"takaran\s+saji[^\d]{0,40}(\d+(?:[.,]\d+)?)\s*(g|gram|ml)\b",
        joined_all,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m:
        v = _to_float(m.group(1))
        if v is not None:
            return v

    # helper: gabung dua digit kecil jadi puluhan
    def _join_two_small_digits(nums: list[float]) -> Optional[float]:
        if len(nums) >= 2 and all(n < 10 for n in nums[:2]):
            tens = int(nums[0])
            ones = int(nums[1])
            return float(10 * tens + ones)
        return None

    for i, line in enumerate(lines):
        if "takaran saji" not in line:
            continue

        # gabungkan baris ini + baris berikutnya (kalau ada)
        if i + 1 < len(lines):
            combined = line + " " + lines[i + 1]
        else:
            combined = line

        # --- 2) coba pola 'takaran saji ... 1 4 g' langsung di gabungan ---
        m2 = re.search(
            r"takaran\s+saji[^\d]{0,40}(\d)\s+(\d)\s*(g|gram|ml)?\b",
            combined,
            flags=re.IGNORECASE,
        )
        if m2:
            tens = int(m2.group(1))
            ones = int(m2.group(2))
            return float(10 * tens + ones)

        # --- 3) coba pola normal di gabungan baris ---
        m3 = re.search(
            r"takaran\s+saji[^0-9]{0,10}(\d+(?:[.,]\d+)?)\s*(g|gram|ml)?\b",
            combined,
            flags=re.IGNORECASE,
        )
        if m3:
            v = _to_float(m3.group(1))
            if v is not None:
                return v

        # --- 4) fallback: lihat semua angka di gabungan baris ---
        nums_combined = _all_numbers(combined)
        if nums_combined:
            # 4a. kalau dua angka pertama kecil (<10), gabung jadi puluhan
            joined_val = _join_two_small_digits(nums_combined)
            if joined_val is not None:
                return joined_val

            # 4b. kalau angka pertama sudah >= 10, pakai langsung (mis. 14, 22, 30)
            if nums_combined[0] >= 10:
                return nums_combined[0]

            # 4c. terakhir banget, pakai nilai pertama apa adanya (mis. kasus aneh 5 g)
            return nums_combined[0]

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
    Cari nilai gula per sajian.
    Strategi:
      1) Cari pola global: "gula total ... 9 g" (boleh lintas baris).
      2) Kalau belum ketemu, fallback ke pencarian per-baris
         seperti sebelumnya (dengan dukungan next-line).
    """
    if not lines:
        return None

    # ---------- 1) Pencarian global di sekitar kata "gula" ----------
    joined = "\n".join(lines)

    # Contoh yang ingin ditangkap:
    # - "Gula total 9 g"
    # - "Gula total\n9 g"
    # - "Gula total : 9 g"
    m = re.search(
        r"gula(?:\s+total)?[^\d]{0,40}(\d+(?:[.,]\d+)?)\s*(g|gram|mg)?",
        joined,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m:
        val = _to_float(m.group(1))
        unit = (m.group(2) or "").lower()

        if val is not None:
            if unit == "mg":
                # konversi mg -> g
                return val / 1000.0
            # kalau tidak ada unit / 'g' / 'gram', anggap gram
            return val

    # ---------- 2) Fallback per-baris (lebih konservatif) ----------
    sugar_keywords = ("gula", "sugar", "sukrosa", "sucrose")

    for i, line in enumerate(lines):
        if not any(k in line for k in sugar_keywords):
            continue

        # Gabungkan dengan baris berikutnya, jaga-jaga angka terpisah
        candidate = line
        if i + 1 < len(lines):
            candidate = line + " " + lines[i + 1]

        matches = re.findall(
            r"(\d+(?:[.,]\d+)?)\s*(g|gram|mg)?",
            candidate,
            flags=re.IGNORECASE,
        )
        if not matches:
            continue

        # Prioritaskan yang punya unit, ambil angka terakhir
        chosen_val = None
        for num_str, unit in matches:
            v = _to_float(num_str)
            if v is None:
                continue
            unit = (unit or "").lower()
            if unit in ("g", "gram", ""):
                chosen_val = v  # as gram
            elif unit == "mg":
                chosen_val = v / 1000.0  # mg -> g

        if chosen_val is not None:
            return chosen_val

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


# --------- Main function (refactor untuk pakai data dari Roboflow) --------- #

def parse_nutrition(
    raw_text: str,
    *,
    text_takaran: str | None = None,
    text_sajian: str | None = None,
    text_gula: str | None = None,
) -> Dict:
    """
    Parsing teks label gizi (Indonesia) menjadi dictionary nutrisi.

    Parameter:
      - raw_text      : teks OCR UNION (misalnya hasil crop_union_bbox) -> fallback global.
      - text_takaran  : teks OCR khusus area 'takaran_saji' (Roboflow ROI).
      - text_sajian   : teks OCR khusus area 'sajian_per_kemasan'.
      - text_gula     : teks OCR khusus area 'gula'.

    Strategi:
      1. Kalau ada text_takaran / text_sajian / text_gula, kita parsing dari situ dulu.
      2. Kalau belum ketemu, baru fallback parsing dari raw_text union.
    """

    # --- CLEAN & split global text (union) ---
    cleaned_global = _clean_text(raw_text or "")
    lines_global = cleaned_global.splitlines() if cleaned_global else []

    # --- CLEAN & split segment teks (kalau ada) ---
    cleaned_takaran = _clean_text(text_takaran) if text_takaran else ""
    lines_takaran = cleaned_takaran.splitlines() if cleaned_takaran else []

    cleaned_sajian = _clean_text(text_sajian) if text_sajian else ""
    lines_sajian = cleaned_sajian.splitlines() if cleaned_sajian else []

    cleaned_gula = _clean_text(text_gula) if text_gula else ""
    lines_gula = cleaned_gula.splitlines() if cleaned_gula else []

    # -----------------------------
    # 1. Takaran saji (gram)
    # -----------------------------
    serving_size_gram = None

    # a) Prioritas dari ROI takaran_saji (Roboflow)
    if lines_takaran:
        serving_size_gram = _parse_serving_size_gram(lines_takaran)

    # b) Fallback dari teks global
    if serving_size_gram is None and lines_global:
        serving_size_gram = _parse_serving_size_gram(lines_global)

    # -----------------------------
    # 2. Sajian per kemasan
    # -----------------------------
    servings_per_pack = None

    # a) Prioritas dari ROI sajian_per_kemasan
    if lines_sajian:
        servings_per_pack = _parse_servings_per_pack(lines_sajian)

    # b) Fallback dari teks global
    if servings_per_pack is None and lines_global:
        servings_per_pack = _parse_servings_per_pack(lines_global)

    # -----------------------------
    # 3. Gula per sajian & per kemasan
    # -----------------------------
    sugar_per_serving_gram = None
    sugar_per_pack_gram = None

    # a) Prioritas dari ROI 'gula'
    if lines_gula:
        sugar_per_serving_gram = _parse_sugar_per_serving(lines_gula)
        sugar_per_pack_gram = _parse_sugar_per_pack(lines_gula)

    # b) Fallback dari teks global
    if sugar_per_serving_gram is None and lines_global:
        sugar_per_serving_gram = _parse_sugar_per_serving(lines_global)
    if sugar_per_pack_gram is None and lines_global:
        sugar_per_pack_gram = _parse_sugar_per_pack(lines_global)

    # c) Turunan: kalau gula per kemasan None, tapi punya gula per sajian + jumlah sajian
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
