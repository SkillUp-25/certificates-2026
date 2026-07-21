import json
from fill_html import parse_json_objects, enrich_student_data
students = parse_json_objects('data.json')
if students:
    d = enrich_student_data(students[0])
    print(json.dumps(d, indent=2))
else:
    print('no students')
