import hashlib
import json
import os
import re
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_JSON = os.path.join(ROOT, "data.json")
OUTPUT_BASE = os.path.join(ROOT, "STUDENTS")

CERT_TEMPLATE = os.path.join(ROOT, "STUDENTS", "STUDENT_NAME", "Certificate_STUDENT_NAME", "CERTIFICATE.html")
MARKS_TEMPLATE = os.path.join(ROOT, "STUDENTS", "STUDENT_NAME", "Marks_STUDENT_NAME", "MARKS.html")

PLACEHOLDER_PATTERN = re.compile(r"__([A-Za-z0-9_./-]+)(?:__)?")

SUBJECTS = [
    {"code": "CS-01", "title": "Basic Computer"},
    {"code": "CS-02", "title": "Windows Application: MS Office"},
    {"code": "CS-03", "title": "Operating System"},
    {"code": "CS-04", "title": "Web Publisher: Internet Browsing"},
]

def number_to_words(number):
    ones = [
        "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
        "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
        "eighteen", "nineteen",
    ]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

    if number < 0:
        return "minus " + number_to_words(-number)
    if number < 20:
        return ones[number]
    if number < 100:
        return tens[number // 10] + ("-" + ones[number % 10] if number % 10 else "")
    if number < 1000:
        remainder = number % 100
        return ones[number // 100] + " hundred" + (" " + number_to_words(remainder) if remainder else "")
    return str(number)


def percentage_to_grade(percentage):
    if percentage >= 90:
        return "A+"
    if percentage >= 80:
        return "A"
    if percentage >= 70:
        return "B"
    if percentage >= 60:
        return "C"
    if percentage >= 50:
        return "D"
    return "E"


def generate_subject_marks(student, subject, subject_index, run_seed):
    identity = "|".join(
        [
            str(student.get("fullName", "")),
            str(student.get("rollNo", "")),
            str(student.get("id", "")),
            subject["code"],
            str(subject_index),
            str(run_seed),
        ]
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    theory = 50 + int(digest[0:2], 16) % 8
    practical = 30 + int(digest[2:4], 16) % 9
    return theory, practical


def enrich_student_data(student):
    student_data = dict(student)
    mark_rows = []
    total_marks = 0
    total_theory = 0
    total_practical = 0
    run_seed = time.time_ns()

    for idx, subject in enumerate(SUBJECTS, start=1):
        theory, practical = generate_subject_marks(student, subject, idx, run_seed)
        subtotal = theory + practical
        total_marks += subtotal
        total_theory += theory
        total_practical += practical
        mark_rows.append(
            f'<h3 class="data">{subject["code"]} {subject["title"]} {theory} {practical} {subtotal}</h3>'
        )

        # provide multiple placeholder key variants to match unchanged templates
        # common misspellings and variants used in templates
        student_data[f'Throy_Marks_sub{idx}'] = str(theory)
        student_data[f'Theroy_Marks_sub{idx}'] = str(theory)
        student_data[f'Practical_marks_sub{idx}'] = str(practical)
        student_data[f'Prectical_marks_sub{idx}'] = str(practical)
        student_data[f'total_marks_sub{idx}'] = str(subtotal)

    max_total = len(SUBJECTS) * 100
    percentage = round(total_marks / max_total * 100, 2)
    mark_rows.append(
        f'<h3 class="data">{total_theory} {total_practical} {total_marks}</h3>'
    )
    student_data["markRows"] = "\n".join(mark_rows)
    student_data["marks_total"] = str(total_marks)
    student_data["marks_total_words"] = number_to_words(total_marks).capitalize()
    student_data["marks_percentage"] = str(percentage)
    student_data["grade"] = percentage_to_grade(percentage)
    student_data["total_marks"] = str(total_marks)
    student_data["percentage"] = str(percentage)

    # extra total keys matching the original template naming
    student_data['total_Theory_marks_all_subjects'] = str(total_theory)
    student_data['total_Practical_marks_all_subjects'] = str(total_practical)
    student_data['grand_total'] = str(total_marks)
    student_data['percentage_in_words'] = number_to_words(int(round(percentage))).capitalize()

    return student_data


def parse_date_value(value):
    if isinstance(value, dict):
        if "$date" in value:
            value = value["$date"]
        elif "$oid" in value:
            return str(value["$oid"])

    if not isinstance(value, str):
        return str(value)

    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%d-%m-%Y")
    except ValueError:
        return value


def load_templates():
    if os.path.exists(CERT_TEMPLATE) and os.path.exists(MARKS_TEMPLATE):
        with open(CERT_TEMPLATE, "r", encoding="utf-8") as f:
            cert_html = f.read()
        with open(MARKS_TEMPLATE, "r", encoding="utf-8") as f:
            marks_html = f.read()
        return cert_html, marks_html

    raise FileNotFoundError(
        "Template HTML files not found. "
        f"Expected {CERT_TEMPLATE} and {MARKS_TEMPLATE}."
    )


def safe_key_name(name):
    return re.sub(r"[^A-Za-z0-9_-]", "_", name.strip()) or "student"


def get_value(student, key_path):
    if not key_path:
        return ""

    parts = re.split(r"[/.]", key_path)
    current = student
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return ""
    return current


def replace_placeholders(template, student):
    def replace(match):
        key = match.group(1)
        raw_value = get_value(student, key)
        if raw_value == "":
            # if we don't have the value, leave the original placeholder intact
            return match.group(0)
        return parse_date_value(raw_value)

    return PLACEHOLDER_PATTERN.sub(replace, template)


def parse_json_objects(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    if not text:
        return []

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
    except json.JSONDecodeError:
        pass

    objects = []
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(text):
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text):
            break
        if text[idx] == ',':
            idx += 1
            continue

        try:
            obj, pos = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            break
        objects.append(obj)
        idx += pos

    return objects


def build_student_files(student, cert_html, marks_html):
    student_name = safe_key_name(student.get("fullName", student.get("rollNo", "student")))
    student_dir = os.path.join(OUTPUT_BASE, student_name)
    cert_dir = os.path.join(student_dir, f"Certificate_{student_name}")
    marks_dir = os.path.join(student_dir, f"Marks_{student_name}")

    os.makedirs(cert_dir, exist_ok=True)
    os.makedirs(marks_dir, exist_ok=True)

    student_data = enrich_student_data(student)

    cert_out = os.path.join(cert_dir, "CERTIFICATE.html")
    marks_out = os.path.join(marks_dir, "MARKS.html")

    with open(cert_out, "w", encoding="utf-8") as f:
        f.write(replace_placeholders(cert_html, student_data))

    with open(marks_out, "w", encoding="utf-8") as f:
        f.write(replace_placeholders(marks_html, student_data))

    return cert_out, marks_out


def main():
    students = parse_json_objects(DATA_JSON)
    if not students:
        print(f"No student records found in {DATA_JSON}")
        return

    cert_html, marks_html = load_templates()
    created_files = []

    for student in students:
        cert_file, marks_file = build_student_files(student, cert_html, marks_html)
        created_files.append((cert_file, marks_file))

    for cert_file, marks_file in created_files:
        print(f"Created: {cert_file}")
        print(f"Created: {marks_file}")


if __name__ == "__main__":
    main()
