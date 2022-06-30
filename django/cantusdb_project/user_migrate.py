import csv
from itertools import count
import lxml.html as lh
import requests

with open('exportFile.csv','r') as csvinput:
    with open('exportFileOutput.csv', 'w') as csvoutput:
        writer = csv.writer(csvoutput, lineterminator='\n')
        reader = csv.reader(csvinput)

        # header
        writer.writerow(['uid', 'old role', 'new role', 'name', 'surname', 'institution', 'town', 'country'])

        for row in reader:
            old_role = row[1]
            if old_role == "administrator":
                row.append("project manager")
            elif old_role == "anonymous user":
                row.append("")
            elif old_role == "authenticated user":
                row.append("")
            elif old_role == "contributor":
                row.append("contributor")
            elif old_role == "Debra":
                row.append("project manager")
            elif old_role == "editor":
                row.append("editor")
            elif old_role == "power":
                row.append("editor")
            elif old_role == "proofreader":
                row.append("editor")
            elif old_role == "SIMSSA contributor":
                row.append("contributor")

            id = row[0]
            url = f"https://cantus.uwaterloo.ca/user/{id}"
            response = requests.get(url)
            doc = lh.fromstring(response.content)

            try:
                name = doc.find_class("field-name-field-name")[0].find_class("field-item")[0].text_content()
            except:
                name = ""
            try:
                surname = doc.find_class("field-name-field-surname")[0].find_class("field-item")[0].text_content()
            except:
                surname = ""
            try:
                institution = doc.find_class("field-name-field-institution")[0].find_class("field-item")[0].text_content()
            except:
                institution = ""
            try:
                town = doc.find_class("field-name-field-town")[0].find_class("field-item")[0].text_content()
            except:
                town = ""
            try:
                country = doc.find_class("field-name-field-country")[0].find_class("field-item")[0].text_content()
            except:
                country = ""
               
            row.append(name)
            row.append(surname)
            row.append(institution)
            row.append(town)
            row.append(country)

            writer.writerow(row)
