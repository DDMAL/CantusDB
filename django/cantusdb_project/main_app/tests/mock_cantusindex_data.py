import ujson

#######################################################################################
### mocking requests.get("https://cantusindex.uwaterloo.ca/json-nextchants/001010") ###
#######################################################################################

mock_json_nextchants_001010_text: str = """
[
    {"cid":"008349", "count": "12","info":{"field_genre":"H", "field_full_text": "Nocte surgentes vigilemus omnes semper in psalmis meditemur atque viribus totis domino canamus dulciter hymnos | Ut pio regi pariter canentes cum suis sanctis mereamur aulam ingredi caeli simul et beatam ducere vitam | Praestet hoc nobis deitas beata patris ac nati pariterque sancti spiritus cujus resonat per omnem gloria mundum | Amen"}},
    {"cid":"006928", "count": "17","info":{"field_genre": "R", "field_full_text": "In principio fecit deus caelum et terram et creavit in ea hominem ad imaginem et similitudinem suam"}},
    {"cid":"008411c","count":"4","info":{"field_genre": "HV", "field_full_text": "Hujus obtentu deus alme nostris parce jam culpis vitiis revulsis quo tibi puri resonet per aevum pectoris hymnus"}},
    {"cid":"008390","count":"3","info":{"field_genre": "H", "field_full_text": "Sanctorum meritis inclyta gaudia pangamus socii gestaque fortia gliscit animus promere cantibus victorum genus optimum"}},
    {"cid":"007713","count":"2","info":{"field_genre": "R", "field_full_text": "Sub altare dei audivi voces occisorum dicentium quare non defendis sanguinem nostrum et acceperunt divinum responsum adhuc sustinete modicum tempus donec impleatur numerus fratrum vestrorum"}},
    {"cid":"909030","count":"1","info":{"field_genre": "IP", "field_full_text": "Venite exsultemus domino jubilemus deo salutari nostro praeoccupemus faciem ejus in confessione et in psalmis jubilemus ei | Quoniam deus magnus dominus et rex magnus super omnes deos quoniam non repellet dominus plebem suam quia in manu ejus sunt omnes fines terrae et altitudines montium ipse conspicit | Quoniam ipsius est mare et ipse fecit illud et aridam fundaverunt manus ejus venite adoremus et procidamus ante deum ploremus coram domino qui fecit nos quia ipse est dominus deus noster nos autem populus ejus et oves pascuae ejus | Hodie si vocem ejus audieritis nolite obdurare corda vestra sicut in exacerbatione secundum diem tentationis in deserto ubi tentaverunt me patres vestri probaverunt et viderunt opera mea | Quadraginta annis proximus fui generationi huic et dixi semper hi errant corde ipsi vero non cognoverunt vias meas quibus juravi in ira mea si introibunt in requiem meam | Gloria patri et filio et spiritui sancto sicut erat in principio et nunc et semper et in saecula saeculorum amen"}}
]
"""
# should be contained in:
# >>> requests.get("https://cantusindex.uwaterloo.ca/json-nextchants/001010").text
# this doesn't include the BOM which we expect to see beginning response.text
# CI seems to present these, sorted by "count", in descending order.
# Here, they have been switched around so we can ensure that our own
# sorting by number of occurrences is working properly

mock_json_nextchants_001010_content: bytes = bytes(
    mock_json_nextchants_001010_text,
    encoding="utf-8-sig",
)  # requests.get("https://cantusindex.uwaterloo.ca/json-nextchants/001010").content
# we expect request.content to be encoded in signed utf-8. I.e., this step adds the BOM
mock_json_nextchants_001010_json: list[dict] = ujson.loads(
    mock_json_nextchants_001010_text
)
# should be equivalent to:
# >>> request = requests.get("https://cantusindex.uwaterloo.ca/json-nextchants/001010")
# >>> request.encoding = "utf-8-sig"
# >>> request.json()


#######################################################################################
### mocking requests.get("https://cantusindex.uwaterloo.ca/json-nextchants/a07763") ###
#######################################################################################

mock_json_nextchants_a07763_text: str = "\r\n"
mock_json_nextchants_a07763_content: bytes = bytes(
    mock_json_nextchants_a07763_text,
    encoding="utf-8-sig",
)

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
        "field_notes": null,
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
mock_json_cid_008349_json: dict = ujson.loads(mock_json_cid_008349_text)

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
mock_json_cid_006928_json: dict = ujson.loads(mock_json_cid_006928_text)

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
mock_json_cid_008411c_json: dict = ujson.loads(mock_json_cid_008411c_text)

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
mock_json_cid_008390_json: dict = ujson.loads(mock_json_cid_008390_text)

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
mock_json_cid_007713_json: dict = ujson.loads(mock_json_cid_007713_text)

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
mock_json_cid_909030_json: dict = ujson.loads(mock_json_cid_909030_text)


##########################################################################
### mocking requests.get("https://cantusindex.org/json-merged-chants") ###
##########################################################################

# Smaller sample of the full content.
mock_get_merged_cantus_ids_text: str = """
[
    {"old": "g00831", "new": "920023", "date": "0000-00-00"},
    {"old": "920027a", "new": "920027", "date": "0000-00-00"},
    {"old": "g01393.1", "new": "g01393", "date": "0000-00-00"},
    {"old": "g00693a.1", "new": "g00693a", "date": "0000-00-00"},
    {"old": "g00838", "new": "008310", "date": "0000-00-00"},
    {"old": "g01132", "new": "503001", "date": "0000-00-00"},
    {"old": "g00681", "new": "g00678c", "date": "0000-00-00"},
    {"old": "g00682", "new": "g00678d", "date": "0000-00-00"},
    {"old": "g00683", "new": "g00678e", "date": "0000-00-00"},
    {"old": "g00684", "new": "g00678f", "date": "0000-00-00"},
    {"old": "g00685", "new": "g00678g", "date": "0000-00-00"},
    {"old": "g02384", "new": "g02374b", "date": "0000-00-00"},
    {"old": "g02494", "new": "g02373c", "date": "2016-08-25"},
    {"old": "g00980", "new": "001287", "date": "2016-08-25"},
    {"old": "g00241", "new": "g00240a", "date": "2016-12-29"},
    {"old": "g01340", "new": "g01339a", "date": "2016-12-30"},
    {"old": "g00476", "new": "g00475a", "date": "2016-12-30"},
    {"old": "g00047", "new": "g00046a", "date": "2016-12-30"},
    {"old": "g02487", "new": "g00029a", "date": "2016-12-30"},
    {"old": "g00413", "new": "g00412a", "date": "2017-01-02"}
]
"""
# We add the expected BOM in the response when using the old
# Cantus Index domain that we have to handle correctly.
utf8_bom: bytes = b"\xef\xbb\xbf\xef\xbb\xbf"
mock_get_merged_cantus_ids_content: bytes = utf8_bom + bytes(
    mock_get_merged_cantus_ids_text,
    encoding="utf-8",
)


#########################################################################
### mocking requests.get("https://cantusindex.org/json-text/qui+est") ###
#########################################################################
mock_get_ci_text_search_quiest_text: str = """
[
    {
        "cid": "001774",
        "fulltext": "Caro et sanguis non revelavit tibi sed pater meus qui est in caelis",
        "genre": "A"
    },
    {
        "cid": "002191",
        "fulltext": "Dicebat Jesus turbis Judaeorum et principibus sacerdotum qui est ex deo verba dei audit responderunt Judaei et dixerunt ei nonne bene dicimus nos quia Samaritanus es tu et daemonium habes respondit Jesus ego daemonium non habeo sed honorifico patrem meum et vos inhonorastis me",
        "genre": "A"
    },
    {
        "cid": "002303",
        "fulltext": "Dixit Jesus turbis quis ex vobis arguet me de peccato si veritatem dico quare vos non creditis mihi qui est ex deo verba dei audit propterea vos non auditis quia ex deo non estis",
        "genre": "A"
    },
    {
        "cid": "003257",
        "fulltext": "In medio et in circuitu sedis dei quattuor animalia senas alas habentia oculis undique plena non cessant nocte ac die dicere sanctus sanctus sanctus dominus deus omnipotens qui erat et qui est et qui venturus est",
        "genre": "A"
    },
    {
        "cid": "003857",
        "fulltext": "Natus est nobis hodie salvator qui est Christus dominus in civitate David",
        "genre": "A"
    },
    {
        "cid": "003870",
        "fulltext": "Nemo ascendit in caelum nisi qui de caelo descendit filius hominis qui est in caelo alleluia",
        "genre": "A"
    },
    {
        "cid": "004470",
        "fulltext": "Qui est ex deo verba dei audit vos non auditis quia ex deo non estis",
        "genre": "A"
    },
    {
        "cid": "004741",
        "fulltext": "Sancti vero martyres Crispinus et Crispinianus audacter regi impio responderunt dicentes pro Christi amore nos venisse fatemur qui est deus verus in trinitate unus cui servimus in fide ac dilectione devoti",
        "genre": "A"
    },
    {
        "cid": "004771",
        "fulltext": "Sanctus autem Cucuphas ad praesidem dixit ego deum alium nescio praeter dominum qui est verus deus quem corde credo ore confiteor et omni studio praedico",
        "genre": "A"
    },
    {
        "cid": "004796",
        "fulltext": "Sanctus sanctus sanctus dominus deus omnipotens qui erat et qui est et qui venturus est",
        "genre": "A"
    },
    {
        "cid": "004910",
        "fulltext": "Si quis mihi ministraverit honorificabit eum pater meus qui est in caelis dicit dominus",
        "genre": "A"
    },
    {
        "cid": "200554",
        "fulltext": "Beatus es Simon Bar Jona quia caro et sanguis non revelavit tibi sed pater meus qui est in celsis dicit dominus",
        "genre": "A"
    },
    {
        "cid": "201972",
        "fulltext": "Gloriam deo in excelsis populi concinunt qui est semper mirabilis in suis sanctis et quos hodie ecclesia mater transmisit ad caelestia regna",
        "genre": "A"
    },
    {
        "cid": "203255",
        "fulltext": "Nil territa supplicio sic loquitur Fabricio tua ficta sculptilia sunt barathri daemonia caelos fecit solus deus qui est rex et sponsus meus",
        "genre": "A"
    },
    {"cid": "204438", "fulltext": "Sancti dei omnes qui estis (...)", "genre": "A"},
    {
        "cid": "204637",
        "fulltext": "Si veritatem dico quare non creditis mihi qui est ex deo verba dei audit",
        "genre": "A"
    },
    {
        "cid": "206961",
        "fulltext": "Sanctus pater Benedictus elevatis in aera oculis vidit spiritum germane sororis sancte videlicet Scholasticae virginis mirabiliter ascendentem ad deum qui est mirabilis dominus in altis",
        "genre": "A"
    },
    {
        "cid": "a00438",
        "fulltext": "Angeli eorum semper vident faciem patris mei qui est in caelis",
        "genre": "A"
    },
    {
        "cid": "203255.1",
        "fulltext": "Nil territa supplicio sic loquitur Fabricio deorum tuorum numina sunt barathri daemonia caelos deus fecit unus qui est rex et sponsus meus",
        "genre": "A"
    },
    {
        "cid": "g00069.1",
        "fulltext": "Responsum accepit Simeon pro eo qui Christum rogabat nigiter a spiritu sancto brandemis aetate dignitate quoque non visurum se mortem nisi videret Christum domini natum Maria virgine et cum inducerent puerum in templum parentes illius exsultant meo accepit eum in ulnas suas et benedixit deum et dixit cum laetitiam mensa nunc dimittis domine servum tuum in pace quia meruit conspicem Christum qui est rex regum et dominus in enim",
        "genre": "A"
    },
    {
        "cid": "002303.1",
        "fulltext": "Dixit dominus Jesus turbis judaeorum et principibus sacerdotum quis ex vobis arguet me de peccato si veritatem dico quare vos non creditis mihi qui est ex deo verba dei audit propterea vos non auditis quia ex deo non estis",
        "genre": "A"
    },
    {
        "cid": "004485a",
        "fulltext": "Si quis mihi ministraverit honorificabit eum pater meus qui est in caelis",
        "genre": "AV"
    },
    {
        "cid": "g02235",
        "fulltext": "Alleluia Beatus es Simon Petre quia caro et sanguis non revelavit tibi sed pater meus qui est in caelis",
        "genre": "Al"
    },
    {
        "cid": "g02604",
        "fulltext": "Alleluia Tu es Simon Bar Jona quia caro et sanguis non revelavit verbum patris sed ipse pater qui est in caelis",
        "genre": "Al"
    },
    {
        "cid": "g02762",
        "fulltext": "Alleluia Natus est nobis hodie salvator qui est Christus dominus in civitate David ",
        "genre": "Al"
    },
    {
        "cid": "g00029a",
        "fulltext": "Beatus es Simon Petre quia caro et sanguis non revelabit tibi sed pater meus qui est in caelis",
        "genre": "AlV"
    },
    {
        "cid": "g01299e",
        "fulltext": "Si quis mihi ministraverit honorificabit eum pater meus qui est in caelis",
        "genre": "CmV"
    },
    {
        "cid": "g01293n",
        "fulltext": "Si quis mihi ministraverit honorificabit eum pater meus qui est in caelis",
        "genre": "CmV"
    },
    {
        "cid": "g00217",
        "fulltext": "Si exprobramini in nomine Christi beati eritis quoniam quod est honoris gloriae et virtutis dei et qui est ejus spiritus super vos requiescet",
        "genre": "GrV"
    },
    {
        "cid": "a00902",
        "fulltext": "Cives caelestis patriae regi regum concinite qui est supremus opifex civitatis uranicae in cujus aedificio talis exstat fundatio",
        "genre": "H"
    },
    {
        "cid": "a03400",
        "fulltext": "Jam suae Christus hospitae dule parat convivium dum Marthae bene meritae caeleste confert gaudium | Quam ubertim inebriat de se pascit et satiat pro choro discumbentium sanctorum dans consortium | Divinitatis glorias Christi cernens quem paverat beatas agit gratias quod eam sic remunerat | O mira dei largitas quae centuplum repraemiat o ingens liberalitas quae mercedem sic ampliat | Christo Martha obsequitur intenta ministerio sed hanc Christus prosequitur aeternitatis bravio | Illi sit laus et gloria qui est sanctorum praemium qui Marthae per suffragium det nobis caeli solium",
        "genre": "H"
    },
    {
        "cid": "ah20140",
        "fulltext": "Mirabile mysterium Deus creator omnium per incorruptam virginem nostrum suscepit hominem et nata mater Patre est qui natus matre pater est | Credit Eva diabolo Maria credit angelo per illam mors introiit per istam vita rediit perdiderat hec condita hec restauravit perdita | Cedrus alta de Libano sub nostrae vallis ysopo cum visitavit Jericho cipressus fit ex platano cinnamomum ex balsamo benedicamus Domino | Usiae gigas geminae assumpto Deus homine alvo conceptus feminae non ex virili semine natus est rex ab homine Jesus est dictus nomine | De spinis uva legitur de stella lux exortitur de petra fons elicitur de virga flos egreditur de monte lapis lapsus est de lapide mons factus est | Qui fuit erit et qui est qui loquebatur praesens est nobiscum est rex Israel qui dicitur Emmanuel nos ergo multifarias Deo dicamus gratias",
        "genre": "H"
    },
    {
        "cid": "100345",
        "fulltext": "Venite cuncti qui estis vocati antiquam Simeonem imitantes qui desiderabat redemptorem suum in templo domini praesentari",
        "genre": "I"
    },
    {
        "cid": "g01178",
        "fulltext": "Dum clamarem ad dominum exaudivit vocem meam ab his qui appropinquant mihi et humiliavit eos qui est ante saecula et manet in aeternum jacta cogitatum tuum in domino et ipse te enutriet",
        "genre": "In"
    },
    {
        "cid": "g02699",
        "fulltext": "Viderunt ingressus tuos deus ingressus dei mei regis mei qui est in sancto",
        "genre": "In"
    },
    {
        "cid": "g00488c",
        "fulltext": "Haec enim dicit dominus spiritus meus qui est in te verba mea",
        "genre": "InV"
    },
    {
        "cid": "g03280",
        "fulltext": "Beatus es Simon Petre quia caro et sanguis non revelavit tibi sed pater meus qui est in caelis",
        "genre": "Of"
    },
    {
        "cid": "g02676",
        "fulltext": "Beatus es Simon Petre quia caro et sanguis non revelavit tibi sed pater meus qui est in caelis dicit dominus",
        "genre": "OfV"
    },
    {
        "cid": "g00035a",
        "fulltext": "Beatus es Simon Petre quia caro et sanguis non revelavit tibi sed pater meus qui est in caelis dicit dominus",
        "genre": "OfV"
    },
    {
        "cid": "920054",
        "fulltext": "In finem in carminibus intellectus David | Exaudi deus orationem meam et ne despexeris deprecationem meam | Intende mihi et exaudi me contristatus sum in exercitatione mea et conturbatus sum | A voce inimici et a tribulatione peccatoris quoniam declinaverunt in me iniquitates et in ira molesti erant mihi | Cor meum conturbatum est in me et formido mortis cecidit super me | Timor et tremor venerunt super me et contexerunt me tenebrae | Et dixi quis dabit mihi pennas sicut columbae et volabo et requiescam | Ecce elongavi fugiens et mansi in solitudine | Exspectabam eum qui salvum me fecit a pusillanimitate spiritus et tempestate | Praecipita domine divide linguas eorum quoniam vidi iniquitatem et contradictionem in civitate | Die ac nocte circumdabit eam super muros ejus iniquitas et labor in medio ejus | Et injustitia et non defecit de plateis ejus usura et dolus | Quoniam si inimicus meus maledixisset mihi sustinuissem utique et si is qui oderat me super me magna locutus fuisset abscondissem me forsitan ab eo | Tu vero homo unanimis dux meus et notus meus | Qui simul mecum dulces capiebas cibos in domo dei ambulavimus cum consensu | Veniat mors super illos et descendant in infernum viventes quoniam nequitiae in habitaculis eorum in medio eorum | Ego autem ad deum clamavi et dominus salvabit me | Vespere et mane et meridie narrabo et annuntiabo et exaudiet vocem meam | Redimet in pace animam meam ab his qui appropinquant mihi quoniam inter multos erant mecum | Exaudiet deus et humiliabit illos qui est ante saecula non enim est illis commutatio et non timuerunt deum | Extendit manum suam in retribuendo contaminaverunt testamentum ejus | Divisi sunt ab ira vultus ejus et appropinquavit cor illius molliti sunt sermones ejus super oleum et ipsi sunt jacula | Jacta super dominum curam tuam et ipse te enutriet non dabit in aeternum fluctuationem justo | Tu vero deus deduces eos in puteum interitus viri sanguinum et dolosi non dimidiabunt dies suos ego autem sperabo in te domine",
        "genre": "PS"
    },
    {
        "cid": "920067",
        "fulltext": "In finem psalmus cantici ipsi David | Exsurgat deus et dissipentur inimici ejus et fugiant qui oderunt eum a facie ejus | Sicut deficit fumus deficiant sicut fluit cera a facie ignis sic pereant peccatores a facie dei | Et justi epulentur et exsultent in conspectu dei et delectentur in laetitia | Cantate deo psalmum dicite nomini ejus iter facite ei qui ascendit super occasum dominus nomen illi exsultate in conspectu ejus turbabuntur a facie ejus | Patris orphanorum et judicis viduarum deus in loco sancto suo | Deus qui inhabitare facit unius moris in domo qui educit vinctos in fortitudine similiter eos qui exasperant qui habitant in sepulcris | Deus cum egredereris in conspectu populi tui cum pertransires in deserto | Terra mota est etenim caeli distillaverunt a facie dei Sinai a facie dei Israel | Pluviam voluntariam segregabis deus hereditati tuae et infirmata est tu vero perfecisti eam | Animalia tua habitabunt in ea parasti in dulcedine tua pauperi deus dominus dabit verbum evangelizantibus virtute multa | Rex virtutum dilecti dilecti et speciei domus dividere spolia | Si dormiatis inter medios cleros pennae columbae deargentatae et posteriora dorsi ejus in pallore auri | Dum discernit caelestis reges super eam nive dealbabuntur in Selmon | Mons dei mons pinguis mons coagulatus mons pinguis | Ut quid suspicamini montes coagulatos mons in quo beneplacitum est deo habitare in eo etenim dominus habitabit in finem | Currus dei decem milibus multiplex milia laetantium dominus in eis in Sina in sancto | Ascendisti in altum coepisti captivitatem accepisti dona in hominibus etenim non credentes inhabitare dominum deum | Benedictus dominus die cottidie prosperum iter faciet nobis deus salutarium nostrorum | Deus noster deus salvos faciendi et domini domini exitus mortis | Verumtamen deus confringet capita inimicorum suorum verticem capilli perambulantium in delictis suis | Dixit dominus ex Basan convertam convertam in profundum maris | Ut intingatur pes tuus in sanguine lingua canum tuorum ex inimicis ab ipso | Viderunt ingressus tuos deus ingressus dei mei regis mei qui est in sancto | Praevenerunt principes conjuncti psallentibus in medio juvencularum tympanistriarum | In ecclesiis benedicite deo domino de fontibus Israel | Ibi Benjamin adolescentulus in mentis excessu principes Juda duces eorum principes Zabulon principes Nephthali | Manda deus virtuti tuae confirma hoc deus quod operatus es in nobis | A templo tuo in Jerusalem tibi offerent reges munera | Increpa feras arundinis congregatio taurorum in vaccis populorum ut excludant eos qui probati sunt argento dissipa gentes quae bella volunt | Venient legati ex Aegypto Aethiopia praeveniet manus ejus deo | Regna terrae cantate deo psallite domino psallite deo | Qui ascendit super caelum caeli ad orientem ecce dabit voci suae vocem virtutis | Date gloriam deo super Israel magnificentia ejus et virtus ejus in nubibus | Mirabilis deus in sanctis suis deus Israel ipse dabit virtutem et fortitudinem plebi suae benedictus deus",
        "genre": "PS"
    },
    {
        "cid": "006088",
        "fulltext": "Angelus ad pastores ait annuntio vobis gaudium magnum quod erit omni populo quia natus est vobis salvator qui est Christus dominus in civitate David",
        "genre": "R"
    },
    {
        "cid": "006206",
        "fulltext": "Beatus es Simon Bar Jona quia caro et sanguis non revelavit tibi sed pater meus qui est in caelis dicit dominus",
        "genre": "R"
    },
    {
        "cid": "006520",
        "fulltext": "Dominus Jesus Christus qui est caput corporis ecclesiae per singula sua membra se colligit in caelum cottidie in quibus sanctum Findanum gloriae confessorum coaequavit quem de hac convalle lacrimarum hodie ad aeternae vitae gaudia sublevavit",
        "genre": "R"
    },
    {
        "cid": "007311",
        "fulltext": "Oculis caeci nati homo dei digitos imprimens dixit dominus Jesus Christus qui est vera lux quae illuminat credentes ipse te per invocationem sancti nominis sui illuminare dignetur",
        "genre": "R"
    },
    {"cid": "601691", "fulltext": "Omnes sancti qui estis (...)", "genre": "R"},
    {
        "cid": "a00115",
        "fulltext": "Dicebat dominus Jesus turbis Judaeorum et principibus sacerdotum quis ex vobis arguet me de peccato si veritatem dico quare non creditis mihi qui est ex deo verba dei audit ergo vos non auditis quia ex deo non estis ego autem a deo processi",
        "genre": "R"
    },
    {
        "cid": "a00546",
        "fulltext": "O vos angeli qui custoditis populos quorum forma fulget in facie vestra et o vos archangeli qui suscipitis animas justorum et vos virtutes potestates principatus dominationes et throni qui estis computati in quintum secretum numerum et o vos cherubin et seraphin sigillum secretorum dei sit laus vobis qui loculum antiqui cordis in fonte aspicitis",
        "genre": "R"
    },
    {
        "cid": "a07762",
        "fulltext": "Ab intus in fimbriis aureis circumamicta varietate haec turba virginum ei se ornari studuit qui est forma speciosus prae filiis hominum",
        "genre": "R"
    },
    {
        "cid": "g02501",
        "fulltext": "Columba aspexit per cancellos fenestrae ubi ante faciem ejus sudando sudavit balsamum de lucido Maximino calor solis exarsit et in tenebras resplenduit unde gemma surrexit in aedificatione templi purissimi cordis benevoli iste turris excelsa de ligno Libani et cupresso facta hyacintho et sardio ornata est urbs praecellens artes aliorum artificum ipse velox cervus cucurrit ad fontem purissimae aquae fluentis de fortissimo lapide qui dulcia aromata irrigavit o pigmentarii qui estis in suavissima viriditate ortorum regis ascendentes in altum quando sanctum sacrificium in arietibus perfecistis inter vos fulget hic artifex paries templi qui desideravit alas aquilae osculando nutricem sapientiam in gloriosa fecunditate ecclesiae o Maximine mons et vallis es et in utroque alta aedificatio appares ubi capricornus cum elephante exivit et sapientia in deliciis fuit tu es fortis et suavis in cerimoniis et in coruscatione altaris ascendens ut fumus aromatum ad columnam laudis ubi intercedis pro populo qui tendit ad speculum lucis cui laus est in altis",
        "genre": "Sq"
    }
]
"""

# We add the expected BOM in the response when using the old
# Cantus Index domain that we have to handle correctly.
utf8_bom: bytes = b"\xef\xbb\xbf\xef\xbb\xbf"
mock_get_ci_text_search_quiest_content: bytes = utf8_bom + bytes(
    mock_get_ci_text_search_quiest_text,
    encoding="utf-8",
)

#########################################################################
### mocking requests.get("https://cantusindex.org/json-text/123xyz") ###
#########################################################################


# We add the expected BOM in the response when using the old
# Cantus Index domain that we have to handle correctly.
mock_get_ci_text_search_123xyz_text: str = ""
utf8_bom: bytes = b"\xef\xbb\xbf\xef\xbb\xbf"
mock_get_ci_text_search_123xyz_content: bytes = utf8_bom + bytes(
    mock_get_ci_text_search_123xyz_text,
    encoding="utf-8",
)
