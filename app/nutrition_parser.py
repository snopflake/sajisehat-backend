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
    Cari takaran saji (gram) dari teks OCR.

    Strategi:
      1. Gabungkan semua teks, cari substring mulai 'takaran saji'
         sampai sebelum 'sajian per kemasan' (kalau ada).
      2. Di window itu:
         - Prioritas: angka utuh yang diikuti 'g/gram/ml'.
         - Kalau tidak ada: gabung digit-digit kecil (1 4 -> 14).
      3. Kalau masih gagal, fallback ke scanning per baris.
    """
    if not lines:
        return None

    full = "\n".join(lines).lower()

    # -------- 1) Window: dari "takaran saji" sampai "sajian per kemasan" --------
    idx = full.find("takaran saji")
    if idx != -1:
        end_idx = full.find("sajian per kemasan", idx)
        if end_idx == -1:
            end_idx = idx + 200  # batas aman 2-3 baris ke depan

        window = full[idx:end_idx]

        # 1a. Cari angka utuh + unit
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(g|gram|ml)\b", window)
        if m:
            v = _to_float(m.group(1))
            if v is not None:
                return v

        # 1b. Kalau belum dapat, ambil semua angka di window
        nums = _all_numbers(window)
        if nums:
            # kasus umum: "1 4 g" → [1,4]
            if len(nums) >= 2 and all(n < 10 for n in nums[:2]):
                return float(10 * int(nums[0]) + int(nums[1]))

            # kasus seperti "1 1 4 g" → [1,1,4]
            if len(nums) >= 3 and nums[0] == 1 and nums[1] == 1 and nums[2] < 10:
                return float(10 * int(nums[1]) + int(nums[2]))

            # kalau angka pertama sudah >=10, pakai langsung
            if nums[0] >= 10:
                return nums[0]

    # -------- 2) Fallback: cek per baris yang mengandung "takaran saji" --------
    for i, line in enumerate(lines):
        l = line.lower()
        if "takaran saji" not in l:
            continue

        combo = l
        if i + 1 < len(lines):
            combo = l + " " + lines[i + 1].lower()

        m2 = re.search(r"(\d+(?:[.,]\d+)?)\s*(g|gram|ml)\b", combo)
        if m2:
            v = _to_float(m2.group(1))
            if v is not None:
                return v

        nums = _all_numbers(combo)
        if nums:
            if len(nums) >= 2 and all(n < 10 for n in nums[:2]):
                return float(10 * int(nums[0]) + int(nums[1]))
            if nums[0] >= 10:
                return nums[0]
            return nums[0]

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
    Cari nilai gula (gula total) per sajian.
    Fokus:
      - Hanya pakai angka yang muncul di sekitar kata 'gula'.
      - Support pola:
          'Gula total 9 g'
          'Gula total : 9'
          'Gula total\n9 g'
      - Kalau ada beberapa angka (mis: gula, sukrosa, laktosa),
        ambil angka PERTAMA sebagai gula total.
    """
    if not lines:
        return None

    # ---------- 1) Pencarian global pakai window di sekitar 'gula' ----------
    joined = "\n".join(lines).lower()

    # 1a. 'gula total ... 9 g' atau tanpa 'total'
    for pattern in [
        r"gula\s+total[^\d]{0,80}(\d+(?:[.,]\d+)?)\s*(g|gram|mg)?",
        r"\bgula\b[^\d]{0,80}(\d+(?:[.,]\d+)?)\s*(g|gram|mg)?",
    ]:
        m = re.search(pattern, joined, flags=re.DOTALL | re.IGNORECASE)
        if m:
            val = _to_float(m.group(1))
            unit = (m.group(2) or "").lower()
            if val is not None:
                if unit == "mg":
                    return val / 1000.0
                # kalau tidak ada unit / 'g' / 'gram', anggap gram
                return val

    # ---------- 2) Fallback per-baris (lebih detail) ----------
    for i, line in enumerate(lines):
        line_l = line.lower()
        if "gula" not in line_l and "sugar" not in line_l:
            continue

        # Gabungkan dengan baris berikutnya (angka sering turun ke bawah)
        combo = line_l
        if i + 1 < len(lines):
            combo = line_l + " " + lines[i + 1].lower()

        # Ambil semua angka + optional unit (g/gram/mg)
        matches = re.findall(
            r"(\d+(?:[.,]\d+)?)\s*(g|gram|mg)?",
            combo,
            flags=re.IGNORECASE,
        )
        if not matches:
            continue

        # Pilih ANGKA PERTAMA yang muncul di sekitar 'gula'
        num_str, unit = matches[0]
        val = _to_float(num_str)
        if val is None:
            continue

        unit = (unit or "").lower()
        if unit == "mg":
            return val / 1000.0
        # default: gram
        return val

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

        # 🔥 Fallback ekstra:
        # kalau masih None, pakai angka paling masuk akal dari text_gula mentah
        if sugar_per_serving_gram is None and text_gula:
            cleaned_gula_raw = _clean_text(text_gula)
            nums = _all_numbers(cleaned_gula_raw)
            # filter angka yang wajar sebagai gula per sajian (0 < x < 60 g)
            candidates = [v for v in nums if 0 < v < 60]
            if candidates:
                # ambil yang terbesar → biasanya "Gula total" (9 g) dari [9, 4, 3]
                sugar_per_serving_gram = max(candidates)

    # b) Fallback dari teks global (union)
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
