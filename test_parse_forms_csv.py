# Unit tests for some functionalities

import datetime
from io import StringIO
from unittest import TestCase

from parse_forms_csv import parse_csv_to_clean_submissions, relative_date_string_to_date

# Valid input (3 columns of data)
simple_example_user1 = """
Timestamp,PoGo Name (either in-game or discord name),Copy paste
10/31/2021 20:13:17,Gertlex,"
Survey History
		Response Date 	Admin Override 	Total XP 	Trainer Level 	
done	09/30/2021	---	67,227,587 (+2,562,828)	45 (+1)	648 (+8)
done	08/31/2021	---	64,664,759 (+2,142,517)	44 (+0)	640 (+7)
done	08/02/2021	---	62,522,242 (+0)	44 (+0)
"""

#simple_example_user1_csv_entries = 

ignore_for_now = """
10/31/2021 20:53:47,Gertlex,"Response Date 	Admin Override 	Total XP 	
edit
	done	Today at 8:16 PM	---	70,419,835 (+3,192,248)	45 (+0)	
done"
10/31/2021 21:26:53,TheNakedHornet,"	Response Date	Admin Override	Total XP
edit	done	Today at 7:01 PM	---	121,477,982 (+4,340,644)	
edit	done	09/30/2021	---	117,137,338 (+6,257,517)	47 (+0)	

"""

# TODO didn't actually implement the test cases yet. Just listing them was enough
# to drive coding them up.
class TestParsing(TestCase):

    def test_good_input(self):
        #parse_input(simple_example_user1)
        pass

    def test_bad_input_file(self):
        pass

    def test_no_complete_rows(self):
        pass

    def test_more_columns_than_expected(self):
        pass

    def test_warn_skip_incomplete_first_row(self):
        pass

    def test_skip_incomplete_last_row(self):
        pass


# Test converting wordy relative dates into actual dates
class TestDateInferral(TestCase):

    def test_last_xday(self):
        # 30th Oct 2021 was a Saturday... get relative dates to that
        str_exp_list = [("Last Saturday", datetime.date(2021, 10, 23)),
                        ("Last Sunday", datetime.date(2021, 10, 24)),
                        ("Last Friday", datetime.date(2021, 10, 29)),
                        ]
        for datestr, exp in str_exp_list:
            res = relative_date_string_to_date(datestr, ref_date_str="10/30/2021")
            print(res, exp)
            assert res == exp
