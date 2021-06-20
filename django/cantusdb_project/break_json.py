import ijson.backends.yajl2_c as ijson
import json
import os

CWD = os.getcwd()
LARGE_JSON = os.path.join(
    CWD, "main_app/fixtures/chant_fixtures.json"
)  # path to the large json file
TARGET_PATH = os.path.join(
    CWD, "main_app/fixtures/chant_fixtures"
)  # directory to put generated smaller json file
if not os.path.exists(TARGET_PATH):
    os.makedirs(TARGET_PATH)
RESULT_BATCH_SIZE = 100  # how many chants in a resulting smaller json file

# to count how many chants are in the iterator
# to do this, it has to iterate till the end
def count_iterator(i):
    return sum(1 for e in i)


file = open(LARGE_JSON, "rb")
chants = ijson.items(file, "item")
number_of_chants = count_iterator(chants)
print("total chants: ", number_of_chants)  # 492794 chants
file.close()
# in order to use the elements in the iterator,
# we have to open it again
file = open(LARGE_JSON, "rb")
chants = ijson.items(file, "item")
chant_list = []
for x in range(number_of_chants + 1):
    # +1 in order to push to the limit and raise StopIteration
    try:
        chant = next(chants)  # chant is a dict
        chant_list.append(chant)
        print("processing chant: ", x)
        if (x + 1) % RESULT_BATCH_SIZE == 0:
            with open(
                os.path.join(
                    TARGET_PATH,
                    "chant_fixture_{}.json".format(int((x + 1) / RESULT_BATCH_SIZE)),
                ),
                "w",
            ) as f:
                json.dump(chant_list, f, indent=2, separators=(", ", ": "))
            chant_list = []
    except StopIteration:
        print("StopIteration_Raised")
        with open(
            os.path.join(
                TARGET_PATH,
                "chant_fixture_{}.json".format(int((x + 1) / RESULT_BATCH_SIZE + 1)),
            ),
            "w",
        ) as f:
            json.dump(chant_list, f, indent=2, separators=(", ", ": "))
        chant_list = []
file.close()
