#######################################################################################
### mocking requests.get("https://cantusindex.uwaterloo.ca/json-nextchants/001010") ###
#######################################################################################

mock_json_nextchants_001010_text: str = """
[
    {"cid":"008349", "count": "12"},
    {"cid":"006928", "count": "17"},
    {"cid":"008411c","count":"4"},
    {"cid":"008390","count":"3"},
    {"cid":"007713","count":"2"},
    {"cid":"909030","count":"1"}
]
"""  # requests.get("https://cantusindex.uwaterloo.ca/json-nextchants/001010").text
# this doesn't include the BOM which we expect to see beginning response.text
# CI seems to present these, sorted by "count", in descending order.
# Here, they have been switched around so we can ensure that our own
# sorting by number of occurrences is working properly
mock_json_nextchants_001010_content: bytes = bytes(
    mock_json_nextchants_001010_text,
    encoding="utf-8-sig",
)  # requests.get("https://cantusindex.uwaterloo.ca/json-nextchants/001010").content
# we expect request.content to be encoded in signed utf-8
mock_json_nextchants_001010_json: list[dict] = [
    {"cid": "008349", "count": "12"},
    {"cid": "006928", "count": "17"},
    {"cid": "008411c", "count": "4"},
    {"cid": "008390", "count": "3"},
    {"cid": "007713", "count": "2"},
    {"cid": "909030", "count": "1"},
]  # request = requests.get("https://cantusindex.uwaterloo.ca/json-nextchants/001010")
# request.encoding = "utf-8-sig"
# request.json


################################################################################
### mocking requests.get("https://cantusindex.uwaterloo.ca/json-cid/008349") ###
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
### mocking requests.get("https://cantusindex.uwaterloo.ca/json-cid/006928") ###
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

#################################################################################
### mocking requests.get("https://cantusindex.uwaterloo.ca/json-cid/008411c") ###
#################################################################################

mock_json_cid_008411c_text: str = """
{
    "info": {
        "field_ah_item": null,
        "field_ah_volume": null,
        "field_cao": null,
        "field_cao_concordances": "SL",
        "field_feast": "Mariae Magdalenae",
        "field_full_text": "Hujus obtentu deus alme nostris parce jam culpis vitiis revulsis quo tibi puri resonet per aevum pectoris hymnus",
        "field_fulltext_source": null,
        "field_genre": "HV",
        "field_language": null,
        "field_notes": null,
        "field_related_chant_id": null,
        "field_similar_chant_id": null,
        "field_troped_chant_id": null
    },
    "chants": {
        "1": {
            "siglum": "P-ARRam ACA/E/002/Lv 002",
            "srclink": "https://pemdatabase.eu/source/103757",
            "chantlink": "https://pemdatabase.eu/musical-item/113818",
            "folio": "r",
            "sequence": null,
            "incipit": "Hujus abtendu deus*",
            "feast": "Mariae Magdalenae",
            "office": "M",
            "genre": "H",
            "position": "",
            "image": "https://pemdatabase.eu/image/103759",
            "mode": "*",
            "fulltext": "Hujus abtendu deus*",
            "melody": "",
            "db": "PEM"
        },
        "0": {
            "siglum": "P-Ln RES. 253 P.",
            "srclink": "https://pemdatabase.eu/source/97935",
            "chantlink": "https://pemdatabase.eu/musical-item/107270",
            "folio": "189r",
            "sequence": null,
            "incipit": "Harum obtentu deus alme nostris parce",
            "feast": "Comm. plurimorum Virginum",
            "office": "V",
            "genre": "HV",
            "position": "",
            "image": "https://pemdatabase.eu/image/102010",
            "mode": "*",
            "fulltext": "Harum obtentu deus alme nostris parce jam culpis vitia revulsis quo tibi puri resonemus almum pectoris hymnus | Gloria patri genitoque proli et tibi compar utriusque semper super alme deus unus omni tempore saeculi",
            "melody": "",
            "db": "PEM"
        }
    }
}
"""
mock_json_cid_008411c_content: bytes = bytes(
    mock_json_cid_008411c_text,
    encoding="utf-8-sig",
)
mock_json_cid_008411c_json: dict = {
    "info": {
        "field_ah_item": None,
        "field_ah_volume": None,
        "field_cao": None,
        "field_cao_concordances": "SL",
        "field_feast": "Mariae Magdalenae",
        "field_full_text": "Hujus obtentu deus alme nostris parce jam culpis vitiis revulsis quo tibi puri resonet per aevum pectoris hymnus",
        "field_fulltext_source": None,
        "field_genre": "HV",
        "field_language": None,
        "field_notes": None,
        "field_related_chant_id": None,
        "field_similar_chant_id": None,
        "field_troped_chant_id": None,
    },
    "chants": {
        "1": {
            "siglum": "P-ARRam ACA/E/002/Lv 002",
            "srclink": "https://pemdatabase.eu/source/103757",
            "chantlink": "https://pemdatabase.eu/musical-item/113818",
            "folio": "r",
            "sequence": None,
            "incipit": "Hujus abtendu deus*",
            "feast": "Mariae Magdalenae",
            "office": "M",
            "genre": "H",
            "position": "",
            "image": "https://pemdatabase.eu/image/103759",
            "mode": "*",
            "fulltext": "Hujus abtendu deus*",
            "melody": "",
            "db": "PEM",
        },
        "0": {
            "siglum": "P-Ln RES. 253 P.",
            "srclink": "https://pemdatabase.eu/source/97935",
            "chantlink": "https://pemdatabase.eu/musical-item/107270",
            "folio": "189r",
            "sequence": None,
            "incipit": "Harum obtentu deus alme nostris parce",
            "feast": "Comm. plurimorum Virginum",
            "office": "V",
            "genre": "HV",
            "position": "",
            "image": "https://pemdatabase.eu/image/102010",
            "mode": "*",
            "fulltext": "Harum obtentu deus alme nostris parce jam culpis vitia revulsis quo tibi puri resonemus almum pectoris hymnus | Gloria patri genitoque proli et tibi compar utriusque semper super alme deus unus omni tempore saeculi",
            "melody": "",
            "db": "PEM",
        },
    },
}

################################################################################
### mocking requests.get("https://cantusindex.uwaterloo.ca/json-cid/008390") ###
################################################################################

mock_json_cid_008390_text: str = """
{
    "info": {
        "field_ah_item": null,
        "field_ah_volume": null,
        "field_cao": "8390",
        "field_cao_concordances": "SL",
        "field_feast": "Comm. plurimorum Martyrum",
        "field_full_text": "Sanctorum meritis inclyta gaudia pangamus socii gestaque fortia gliscit animus promere cantibus victorum genus optimum",
        "field_fulltext_source": "A-HE (Heiligenkreuz im Wienerwald) 20, fol. 240v-241r",
        "field_genre": "H",
        "field_language": null,
        "field_notes": "Full text submitted by Veronika Mr\u00e1\u010dkov\u00e1 | cf. 008390.1 for the 1632 Urban VIII revision of this hymn, which begins the same but contains multiple differences",
        "field_related_chant_id": null,
        "field_similar_chant_id": null,
        "field_troped_chant_id": null
    },
    "chants": {
        "0": {
            "siglum": "P-BRs Ms. 028",
            "srclink": "https://pemdatabase.eu/source/48438",
            "chantlink": "https://pemdatabase.eu/musical-item/44336",
            "folio": "017r",
            "sequence": null,
            "incipit": "Sanctorum meritis*",
            "feast": "Nat. Innocentium",
            "office": "V2",
            "genre": "H",
            "position": "",
            "image": "https://pemdatabase.eu/image/85920",
            "mode": "*",
            "fulltext": "Sanctorum meritis*",
            "melody": "",
            "db": "PEM"
        }
	}
}
"""
mock_json_cid_008390_content: bytes = bytes(
    mock_json_cid_008390_text,
    encoding="utf-8-sig",
)
mock_json_cid_008390_json: dict = {
    "info": {
        "field_ah_item": None,
        "field_ah_volume": None,
        "field_cao": "8390",
        "field_cao_concordances": "SL",
        "field_feast": "Comm. plurimorum Martyrum",
        "field_full_text": "Sanctorum meritis inclyta gaudia pangamus socii gestaque fortia gliscit animus promere cantibus victorum genus optimum",
        "field_fulltext_source": "A-HE (Heiligenkreuz im Wienerwald) 20, fol. 240v-241r",
        "field_genre": "H",
        "field_language": None,
        "field_notes": "Full text submitted by Veronika Mr\u00e1\u010dkov\u00e1 | cf. 008390.1 for the 1632 Urban VIII revision of this hymn, which begins the same but contains multiple differences",
        "field_related_chant_id": None,
        "field_similar_chant_id": None,
        "field_troped_chant_id": None,
    },
    "chants": {
        "0": {
            "siglum": "P-BRs Ms. 028",
            "srclink": "https://pemdatabase.eu/source/48438",
            "chantlink": "https://pemdatabase.eu/musical-item/44336",
            "folio": "017r",
            "sequence": None,
            "incipit": "Sanctorum meritis*",
            "feast": "Nat. Innocentium",
            "office": "V2",
            "genre": "H",
            "position": "",
            "image": "https://pemdatabase.eu/image/85920",
            "mode": "*",
            "fulltext": "Sanctorum meritis*",
            "melody": "",
            "db": "PEM",
        }
    },
}

################################################################################
### mocking requests.get("https://cantusindex.uwaterloo.ca/json-cid/007713") ###
################################################################################

mock_json_cid_007713_text: str = """
{
    "info": {
        "field_ah_item": null,
        "field_ah_volume": null,
        "field_cao": "7713",
        "field_cao_concordances": "CGBEMVHRDFSL",
        "field_feast": "Nat. Innocentium",
        "field_full_text": "Sub altare dei audivi voces occisorum dicentium quare non defendis sanguinem nostrum et acceperunt divinum responsum adhuc sustinete modicum tempus donec impleatur numerus fratrum vestrorum",
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
            "siglum": "P-BRs Ms. 028",
            "srclink": "https://pemdatabase.eu/source/48438",
            "chantlink": "https://pemdatabase.eu/musical-item/44288",
            "folio": "013r",
            "sequence": null,
            "incipit": "Sub altare dei audivi voces occisorum ",
            "feast": "Nat. Innocentium",
            "office": "M",
            "genre": "R",
            "position": "1.1",
            "image": "https://pemdatabase.eu/image/85916",
            "mode": "7",
            "fulltext": "Sub altare dei audivi voces occisorum dicentium quare non defendis sanguinem nostrum et acceperunt divinum responsum adhuc sustinete modicum tempus donec impleatur numerus fratrum vestrorum",
            "melody": "",
            "db": "PEM"
        }
    }
}
"""
mock_json_cid_007713_content: bytes = bytes(
    mock_json_cid_007713_text,
    encoding="utf-8-sig",
)
mock_json_cid_007713_json: dict = {
    "info": {
        "field_ah_item": None,
        "field_ah_volume": None,
        "field_cao": "7713",
        "field_cao_concordances": "CGBEMVHRDFSL",
        "field_feast": "Nat. Innocentium",
        "field_full_text": "Sub altare dei audivi voces occisorum dicentium quare non defendis sanguinem nostrum et acceperunt divinum responsum adhuc sustinete modicum tempus donec impleatur numerus fratrum vestrorum",
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
            "siglum": "P-BRs Ms. 028",
            "srclink": "https://pemdatabase.eu/source/48438",
            "chantlink": "https://pemdatabase.eu/musical-item/44288",
            "folio": "013r",
            "sequence": None,
            "incipit": "Sub altare dei audivi voces occisorum ",
            "feast": "Nat. Innocentium",
            "office": "M",
            "genre": "R",
            "position": "1.1",
            "image": "https://pemdatabase.eu/image/85916",
            "mode": "7",
            "fulltext": "Sub altare dei audivi voces occisorum dicentium quare non defendis sanguinem nostrum et acceperunt divinum responsum adhuc sustinete modicum tempus donec impleatur numerus fratrum vestrorum",
            "melody": "",
            "db": "PEM",
        },
    },
}

################################################################################
### mocking requests.get("https://cantusindex.uwaterloo.ca/json-cid/909030") ###
################################################################################

mock_json_cid_909030_text: str = """
{
    "info": {
        "field_ah_item": null,
        "field_ah_volume": null,
        "field_cao": null,
        "field_cao_concordances": null,
        "field_feast": "Invitatoria",
        "field_full_text": "Venite exsultemus domino jubilemus deo salutari nostro praeoccupemus faciem ejus in confessione et in psalmis jubilemus ei | Quoniam deus magnus dominus et rex magnus super omnes deos quoniam non repellet dominus plebem suam quia in manu ejus sunt omnes fines terrae et altitudines montium ipse conspicit | Quoniam ipsius est mare et ipse fecit illud et aridam fundaverunt manus ejus venite adoremus et procidamus ante deum ploremus coram domino qui fecit nos quia ipse est dominus deus noster nos autem populus ejus et oves pascuae ejus | Hodie si vocem ejus audieritis nolite obdurare corda vestra sicut in exacerbatione secundum diem tentationis in deserto ubi tentaverunt me patres vestri probaverunt et viderunt opera mea | Quadraginta annis proximus fui generationi huic et dixi semper hi errant corde ipsi vero non cognoverunt vias meas quibus juravi in ira mea si introibunt in requiem meam | Gloria patri et filio et spiritui sancto sicut erat in principio et nunc et semper et in saecula saeculorum amen",
        "field_fulltext_source": null,
        "field_genre": "IP",
        "field_language": null,
        "field_notes": null,
        "field_related_chant_id": null,
        "field_similar_chant_id": null,
        "field_troped_chant_id": null
    },
    "chants": {
        "0": {
            "siglum": "P-Cug MM 0045",
            "srclink": "https://pemdatabase.eu/source/46513",
            "chantlink": "https://pemdatabase.eu/musical-item/50730",
            "folio": "029r",
            "sequence": null,
            "incipit": "Venite exsultemus domino jubilemus deo salutari",
            "feast": "De festis duplicibus",
            "office": "M",
            "genre": "IP",
            "position": "",
            "image": "https://pemdatabase.eu/image/84007",
            "mode": "",
            "fulltext": "Venite exsultemus domino jubilemus deo salutari nostro praeoccupemus faciem ejus in confessione et in psalmis jubilemus ei | Quoniam deus magnus | Quoniam ipsius est mare et ipse fecit illud et aridam fundaverunt manus ejus venite adoremus et procidamus ante deum ploremus coram domino qui fecit nos quia ipse est dominus deus noster nos autem populus ejus et oves pascuae ejus | Hodie si vocem | Quadraginta annis proximus fui generationi huic et dixi semper hi errant corde ipsi vero non cognoverunt vias meas quibus juravi in ira mea si introibunt in requiem meam | Gloria",
            "melody": "",
            "db": "PEM"
		}
    }
}
"""
mock_json_cid_909030_content: bytes = bytes(
    mock_json_cid_909030_text,
    encoding="utf-8-sig",
)
mock_json_cid_909030_json: dict = {
    "info": {
        "field_ah_item": None,
        "field_ah_volume": None,
        "field_cao": None,
        "field_cao_concordances": None,
        "field_feast": "Invitatoria",
        "field_full_text": "Venite exsultemus domino jubilemus deo salutari nostro praeoccupemus faciem ejus in confessione et in psalmis jubilemus ei | Quoniam deus magnus dominus et rex magnus super omnes deos quoniam non repellet dominus plebem suam quia in manu ejus sunt omnes fines terrae et altitudines montium ipse conspicit | Quoniam ipsius est mare et ipse fecit illud et aridam fundaverunt manus ejus venite adoremus et procidamus ante deum ploremus coram domino qui fecit nos quia ipse est dominus deus noster nos autem populus ejus et oves pascuae ejus | Hodie si vocem ejus audieritis nolite obdurare corda vestra sicut in exacerbatione secundum diem tentationis in deserto ubi tentaverunt me patres vestri probaverunt et viderunt opera mea | Quadraginta annis proximus fui generationi huic et dixi semper hi errant corde ipsi vero non cognoverunt vias meas quibus juravi in ira mea si introibunt in requiem meam | Gloria patri et filio et spiritui sancto sicut erat in principio et nunc et semper et in saecula saeculorum amen",
        "field_fulltext_source": None,
        "field_genre": "IP",
        "field_language": None,
        "field_notes": None,
        "field_related_chant_id": None,
        "field_similar_chant_id": None,
        "field_troped_chant_id": None,
    },
    "chants": {
        "0": {
            "siglum": "P-Cug MM 0045",
            "srclink": "https://pemdatabase.eu/source/46513",
            "chantlink": "https://pemdatabase.eu/musical-item/50730",
            "folio": "029r",
            "sequence": None,
            "incipit": "Venite exsultemus domino jubilemus deo salutari",
            "feast": "De festis duplicibus",
            "office": "M",
            "genre": "IP",
            "position": "",
            "image": "https://pemdatabase.eu/image/84007",
            "mode": "",
            "fulltext": "Venite exsultemus domino jubilemus deo salutari nostro praeoccupemus faciem ejus in confessione et in psalmis jubilemus ei | Quoniam deus magnus | Quoniam ipsius est mare et ipse fecit illud et aridam fundaverunt manus ejus venite adoremus et procidamus ante deum ploremus coram domino qui fecit nos quia ipse est dominus deus noster nos autem populus ejus et oves pascuae ejus | Hodie si vocem | Quadraginta annis proximus fui generationi huic et dixi semper hi errant corde ipsi vero non cognoverunt vias meas quibus juravi in ira mea si introibunt in requiem meam | Gloria",
            "melody": "",
            "db": "PEM",
        }
    },
}
