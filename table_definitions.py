from dominate.tags import *

class RankingTable():
    # For monthly plus total

    # TODO add params for stuff like "duration"
    def __init__(self, data, stat, category, max_entries=20):
        self.category = category  # e.g. "October 2021"


        # Properties used to make pretty tables:
        self.title
        self.rankings_total
        self.rankings_month


    def to_html(self):
        print(img(**{"class": 123, "href": f"{tag}.png", "alt": f"{tag}"}))
        html_start = \
"""<div
