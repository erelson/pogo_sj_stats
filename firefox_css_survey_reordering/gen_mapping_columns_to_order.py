#! /usr/bin/env python3

# Need a mapping from the rows we're writing (from medal_counts.json) to the current column #s in tl40

# Standard library
import json


with open("ids", 'r') as fr:
    active_columns = fr.read().splitlines()

with open("medal_counts.json", 'r') as fr:
    displayjson = fr.read()

display_order = json.loads(displayjson)

mapping = {}
for value in display_order.values():
    id_name = value[4]
    #print(id_name)
    for cnt, row in enumerate(active_columns):
        if id_name in row:  # TODO short names shouldn't match
            mapping[id_name] = cnt
            break
with open("survey_to_pogo_order_mapping.json", 'w') as fw:
    fw.write(json.dumps(mapping, indent=2))
