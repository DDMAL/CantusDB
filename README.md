# CantusDB
Documentation for Cantus Database, including documentation on its APIs, can be found in the [Wiki](https://github.com/DDMAL/CantusDB/wiki).

## OldCantus vs. NewCantus

This repository contains code for "NewCantus," an updated version of Cantus Database built in Django. "OldCantus", built in Drupal, can be accessed at https://cantus.uwaterloo.ca.

Discrepancies between text stored in the CantusDB database and the manuscript text are compiled by testers in the following Google Spreadsheet: https://docs.google.com/spreadsheets/d/133lVOVM15l7a6bQKIQije4op363ragG4OXewYop_cbQ/edit#gid=0

### Differences in functionality/behavior:
#### Visible to All Users (Logged-In and Anonymous)
- Several of the APIs from OldCantus are not implemented in NewCantus, or are implemented differently:
  - json-activity (accessed via https://cantus.uwaterloo.ca/json-activity and https://cantus.uwaterloo.ca/json-activity?all) is not implemented in NewCantus ([Discussion](https://github.com/DDMAL/CantusDB/issues/126))
  - json-analysis-export (accessed, we think, via [https://cantus.uwaterloo.ca/json-analysis-export/?src=\<source id\>](https://cantus.uwaterloo.ca/json-analysis-export/?src=123591)) is not implemented in NewCantus ([Discussion](https://github.com/DDMAL/CantusDB/issues/124))
  - some of the keys in the json generated by json-node (accessed via [https://cantus.uwaterloo.ca/json-node/\<id\>](https://cantus.uwaterloo.ca/json-node/123591)) are different in NewCantus ([Discussion](https://github.com/DDMAL/CantusDB/issues/106))
- very soon, all people will be represented as Users in NewCantus. This is in contrast to OldCantus, where there were two separate lists of people: one of Indexers and one of Users. ([Discussion](https://github.com/DDMAL/CantusDB/issues/218))

#### Logged-In Users
- on the edit-volpiano page, there are some additional links in NewCantus that were previously unclickable text in OldCantus ([Discussion](https://github.com/DDMAL/CantusDB/issues/253))
