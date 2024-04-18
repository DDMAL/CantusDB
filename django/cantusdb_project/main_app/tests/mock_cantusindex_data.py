#######################################################################################
### mocking requests.get("https://cantusindex.uwaterloo.ca/json-nextchants/001010") ###
#######################################################################################

mock_json_nextchants_001010_text: str = """
[
    {"cid":"006928","count":"10"},
    {"cid":"008349","count":"17"},
]
"""  # requests.get("https://cantusindex.uwaterloo.ca/json-nextchants/001010").text  # this doesn't include the BOM which we expect to see beginning response.text
# CI seems to present these, sorted by "count", in descending order.
# Here, they have been switched so we can ensure that our own sorting by number of occurrences is working properly
mock_json_nextchants_001010_content: bytes = bytes(
    mock_json_nextchants_001010_text,
    encoding="utf-8-sig",
)  # requests.get("https://cantusindex.uwaterloo.ca/json-nextchants/001010").content  # we expect request.content to be encoded in signed utf-8
mock_json_nextchants_001010_json: dict = [
    {"cid": "008349", "count": "17"},
    {"cid": "006928", "count": "10"},
]  # request = requests.get("https://cantusindex.uwaterloo.ca/json-nextchants/001010")
# request.encoding = "utf-8-sig"
# request.json


################################################################################
### mocking requests.get("https://cantusindex.uwaterloo.ca/json_cid/008349") ###
################################################################################

mock_json_cid_008349_text: str = """
{
    "info": {
        "field_ah_item": null,
        "field_ah_volume": null,
        "field_cao": "8349",
        "field_cao_concordances": "S",
        "field_feast": "Dominica in estate",
        "field_full_text": "Nocte surgentes vigilemus omnes semper in psalmis meditemur atque viribus totis domino canamus dulciter hymnos | Ut pio regi pariter canentes cum suis sanctis mereamur aulam ingredi caeli simul et beatam ducere vitam | Praestet hoc nobis deitas beata patris ac nati pariterque sancti spiritus cujus resonat per omnem gloria mundum | Amen",
        "field_fulltext_source": null,
        "field_genre": "H",
        "field_language": null,
        "field_notes": "The 1632 Urban VIII hymn revision is nearly identical to this version and so shares this Cantus ID.  Note the following differences: \"voci concordi\" (Urban VIII) instead of \"viribus totis\" in stanza 1 and \"perennem\" instead of \"beatam\" in stanza 2.",
        "field_related_chant_id": null,
        "field_similar_chant_id": null,
        "field_troped_chant_id": null
    },
    "chants": {
        "0": {
            "siglum": "P-BRs Ms. 032",
            "srclink": "https://pemdatabase.eu/source/47990",
            "chantlink": "https://pemdatabase.eu/musical-item/54477",
            "folio": "262r",
            "sequence": null,
            "incipit": "Nocte surgentes*",
            "feast": "Dom. 2 p. Pent.",
            "office": "M",
            "genre": "H",
            "position": "",
            "image": "https://pemdatabase.eu/image/71166",
            "mode": "*",
            "fulltext": "Nocte surgentes*",
            "melody": "",
            "db": "PEM"
        },
        "1": {
            "siglum": "P-Cua Liber Catenatus ",
            "srclink": "https://pemdatabase.eu/source/46520",
            "chantlink": "https://pemdatabase.eu/musical-item/94677",
            "folio": "001v",
            "sequence": null,
            "incipit": "Nocte surgentes vigilemus omnes semper in",
            "feast": "Dom. per annum",
            "office": "M",
            "genre": "H",
            "position": "",
            "image": "https://pemdatabase.eu/image/58092",
            "mode": "*",
            "fulltext": "Nocte surgentes vigilemus omnes semper in psalmis meditemur atque viribus totis domino canamus dulciter hymnos | Ut pio regi pariter canentes cum suis sanctis mereamur aulam ingredi caeli simul et beatam ducere vitam | Praestet hoc nobis deitas beata patris ac nati pariterque sancti spiritus cujus reboat per omnem gloria mundum | Amen",
            "melody": "",
            "db": "PEM"
        }
    }
}
"""
mock_json_cid_008349_content: bytes = bytes(
    mock_json_cid_008349_text,
    encoding="utf-8-sig",
)
mock_json_cid_008349_json: dict = {
    "info": {
        "field_ah_item": None,
        "field_ah_volume": None,
        "field_cao": "8349",
        "field_cao_concordances": "S",
        "field_feast": "Dominica in estate",
        "field_full_text": "Nocte surgentes vigilemus omnes semper in psalmis meditemur atque viribus totis domino canamus dulciter hymnos | Ut pio regi pariter canentes cum suis sanctis mereamur aulam ingredi caeli simul et beatam ducere vitam | Praestet hoc nobis deitas beata patris ac nati pariterque sancti spiritus cujus resonat per omnem gloria mundum | Amen",
        "field_fulltext_source": None,
        "field_genre": "H",
        "field_language": None,
        "field_notes": 'The 1632 Urban VIII hymn revision is nearly identical to this version and so shares this Cantus ID.  Note the following differences: "voci concordi" (Urban VIII) instead of "viribus totis" in stanza 1 and "perennem" instead of "beatam" in stanza 2.',
        "field_related_chant_id": None,
        "field_similar_chant_id": None,
        "field_troped_chant_id": None,
    },
    "chants": {
        "0": {
            "siglum": "P-BRs Ms. 032",
            "srclink": "https://pemdatabase.eu/source/47990",
            "chantlink": "https://pemdatabase.eu/musical-item/54477",
            "folio": "262r",
            "sequence": None,
            "incipit": "Nocte surgentes*",
            "feast": "Dom. 2 p. Pent.",
            "office": "M",
            "genre": "H",
            "position": "",
            "image": "https://pemdatabase.eu/image/71166",
            "mode": "*",
            "fulltext": "Nocte surgentes*",
            "melody": "",
            "db": "PEM",
        },
        "1": {
            "siglum": "P-Cua Liber Catenatus ",
            "srclink": "https://pemdatabase.eu/source/46520",
            "chantlink": "https://pemdatabase.eu/musical-item/94677",
            "folio": "001v",
            "sequence": None,
            "incipit": "Nocte surgentes vigilemus omnes semper in",
            "feast": "Dom. per annum",
            "office": "M",
            "genre": "H",
            "position": "",
            "image": "https://pemdatabase.eu/image/58092",
            "mode": "*",
            "fulltext": "Nocte surgentes vigilemus omnes semper in psalmis meditemur atque viribus totis domino canamus dulciter hymnos | Ut pio regi pariter canentes cum suis sanctis mereamur aulam ingredi caeli simul et beatam ducere vitam | Praestet hoc nobis deitas beata patris ac nati pariterque sancti spiritus cujus reboat per omnem gloria mundum | Amen",
            "melody": "",
            "db": "PEM",
        },
    },
}

################################################################################
### mocking requests.get("https://cantusindex.uwaterloo.ca/json_cid/006928") ###
################################################################################

mock_json_cid_006928_text: str = """
{
    "info": {
        "field_ah_item": null,
        "field_ah_volume": null,
        "field_cao": "6928",
        "field_cao_concordances": "CGBEMVHRDFSL",
        "field_feast": "Dom. Septuagesimae",
        "field_full_text": "In principio fecit deus caelum et terram et creavit in ea hominem ad imaginem et similitudinem suam",
        "field_fulltext_source": null,
        "field_genre": "R",
        "field_language": null,
        "field_notes": null,
        "field_related_chant_id": null,
        "field_similar_chant_id": null,
        "field_troped_chant_id": null
    },
    "chants": {
        "0": {
            "siglum": "P-BRs Ms. 032",
            "srclink": "https://pemdatabase.eu/source/47990",
            "chantlink": "https://pemdatabase.eu/musical-item/51656",
            "folio": "119r",
            "sequence": null,
            "incipit": "In principio creauit deus celum et ",
            "feast": "Dom. Septuagesimae",
            "office": "M",
            "genre": "R",
            "position": "1",
            "image": "https://pemdatabase.eu/image/71015",
            "mode": "1",
            "fulltext": "In principio creauit deus celum et terram et fecit in ea hominem ad imaginem et similitudinem suam",
            "melody": "",
            "db": "PEM"
        },
        "1": {
            "siglum": "P-AR Res. Ms. 021",
            "srclink": "https://pemdatabase.eu/source/62867",
            "chantlink": "https://pemdatabase.eu/musical-item/65240",
            "folio": "063r",
            "sequence": null,
            "incipit": "In principio*",
            "feast": "Dom. Septuagesimae",
            "office": "V",
            "genre": "R",
            "position": "",
            "image": "https://pemdatabase.eu/image/63266",
            "mode": "1",
            "fulltext": "In principio*",
            "melody": "",
            "db": "PEM"
        }
    }
}
"""
mock_json_cid_006928_content: bytes = bytes(
    mock_json_cid_006928_text,
    encoding="utf-8-sig",
)
mock_json_cid_006928_json: dict = {
    "info": {
        "field_ah_item": None,
        "field_ah_volume": None,
        "field_cao": "6928",
        "field_cao_concordances": "CGBEMVHRDFSL",
        "field_feast": "Dom. Septuagesimae",
        "field_full_text": "In principio fecit deus caelum et terram et creavit in ea hominem ad imaginem et similitudinem suam",
        "field_fulltext_source": None,
        "field_genre": "R",
        "field_language": None,
        "field_notes": None,
        "field_related_chant_id": None,
        "field_similar_chant_id": None,
        "field_troped_chant_id": None,
    },
    "chants": {
        "0": {
            "siglum": "P-BRs Ms. 032",
            "srclink": "https://pemdatabase.eu/source/47990",
            "chantlink": "https://pemdatabase.eu/musical-item/51656",
            "folio": "119r",
            "sequence": None,
            "incipit": "In principio creauit deus celum et ",
            "feast": "Dom. Septuagesimae",
            "office": "M",
            "genre": "R",
            "position": "1",
            "image": "https://pemdatabase.eu/image/71015",
            "mode": "1",
            "fulltext": "In principio creauit deus celum et terram et fecit in ea hominem ad imaginem et similitudinem suam",
            "melody": "",
            "db": "PEM",
        },
        "1": {
            "siglum": "P-AR Res. Ms. 021",
            "srclink": "https://pemdatabase.eu/source/62867",
            "chantlink": "https://pemdatabase.eu/musical-item/65240",
            "folio": "063r",
            "sequence": None,
            "incipit": "In principio*",
            "feast": "Dom. Septuagesimae",
            "office": "V",
            "genre": "R",
            "position": "",
            "image": "https://pemdatabase.eu/image/63266",
            "mode": "1",
            "fulltext": "In principio*",
            "melody": "",
            "db": "PEM",
        },
    },
}
