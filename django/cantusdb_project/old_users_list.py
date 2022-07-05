import csv
import lxml.html as lh
import requests

with open('oldcantususer_uid_role.csv','r') as csvinput:
    with open('oldcantususer_uid_role_detailed.csv', 'w') as csvoutput:
        with open('id_username_email.csv','r') as csvinput_username_email:

            writer = csv.writer(csvoutput, lineterminator='\n')
            reader = csv.reader(csvinput)
            reader_username_email = csv.reader(csvinput_username_email)

            # header
            writer.writerow(['uid', 'old role', 'new role', 'name', 'surname', 'institution', 'town', 'country', 'username', 'email'])

            for row, row_username_email in zip(reader, reader_username_email):
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
                
                username = row_username_email[1]
                email = row_username_email[2]
                
                row.append(name)
                row.append(surname)
                row.append(institution)
                row.append(town)
                row.append(country)
                row.append(username)
                row.append(email)

                writer.writerow(row)
