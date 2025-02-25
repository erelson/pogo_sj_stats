#! /usr/bin/env python

# Flask!

# Standard library
import argparse
import json
import sys

# Third party
from flask import request, flash, redirect, url_for, send_from_directory
from flask import Flask
from flask import render_template
from wtforms import Form, BooleanField, DecimalField, StringField, IntegerField, \
                    PasswordField, validators
from flask_wtf import FlaskForm
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import OperationalError
from sqlalchemy import create_engine
from sqlalchemy.engine import ExceptionContext

# Local
from tables import Stat, Response, Trainer
from settings import LOCAL_DB_SPECIFIER


MEDALS = ["No medal", "Bronze", "Silver", "Gold", "Platinum"]
TYPE_MEDALS = ["Schoolkid",  # This list's fields get put at the very end of the survey
               "Black Belt",
               "Bird Keeper",
               "Punk Girl",
               "Ruin Maniac",
               "Hiker",
               "Bug Catcher",
               "Hex Maniac",
               "Rail Staff",
               "Kindler",
               "Swimmer",
               "Gardener",
               "Rocker",
               "Psychic",
               "Skier",
               "Dragon Tamer",
               "Delinquent",
               "Fairy Tale Girl",
              ]

app = Flask(__name__)


def get_survey_data_in_survey_order(session, user=None):
    """Load data from DB for user and put it in order that we want to display the survey in.

    Args:
        session: sqlalchemy session
        user (str): trainer name
        stats: Preloaded information about stat categories and badge thresholds.
            Otherwise query DB for this information

    Returns:
        stats_list: (TODO rename?) list of lists. Each sublist is
            [Name, img, previous value/None, maximum/None]
    """
    # We get two lists, the stats_list from json
    # and the trainer_data from the database.
    # We want to return the stats in the best order for the person taking the survey...
    # So approach to sorting...
    # - Option 1: Starting from the default offsets, increment the offsets based on the
    # trainer's medal level (since this is what the game uses for ordering)
    # - Option 2: Go stat by stat and bin them into 0/bronze/silver/gold/platinum categories,
    # then concatenate the categories.

    # We ultimately return stat_lists, a list of lists, where each sublist is [Stat, previous_val]

    # If we do not have trainer data, we just return the default order from json.
    # If we have trainer data, we also fill in the previous recorded value.

    stats_list = []  # list of lists, each sublist is [index, Stat, previous_val]; previous_val gets set later
    # For now, load from json. The json is a list in a hand-chosen desired order.
    # This means we can update the order (in the json file), without updating/migrating the database.
    static_stat_info = json.load(open("stats.json", 'r'))  # dict
    stat_keys = static_stat_info["key"]  # list   TODO probably not using this here...
    stat_vals = static_stat_info["data"]  # dict keyed by Stat Names
    for cnt, stat_name in enumerate(stat_vals):
        stats_list.append([cnt,  # index to sort by later
                           Stat(name=stat_name, # order_idx=cnt,  # Probably don't need this order since we're not saving this object to DB...
                                **dict(zip(stat_keys, stat_vals[stat_name]))),
                           0,  # previous value
                           ])

    # Get trainer's last survey data if any, to help set order, limits and hints on the survey page.
    trainer = None
    trainer_data = {}
    if user:
        try:
            trainer = session.query(Trainer).filter_by(name=user.lower()).one()
        except NoResultFound:
            # The user doesn't have a submission yet, so blank data.
            pass
    if trainer:
        # trainer_data will be a dict by stat name of values from previous response
        # stderr is used ... why?
        trainer_data = trainer.get_newest_response(session)  # May be None for newly (manually?) added trainer
        if trainer_data is None:
            print(f"Got NO data for trainer {user}..", file=sys.stderr)
            # NOTE this probably shouldn't happen and doesn't happen... so TODO should be an exception
        else:
            print(f"Got trainer {user} data.. non-None? {trainer_data != None}", file=sys.stderr)

    # Calculate offsets for each stat category
    # For each stat category, iterate through its badge amounts, calculating offsets based on previous stat amount.
    # Use cnt as index in stats_list, generated from stats_vals.
    for cnt, x in enumerate(stat_vals.values()):  # iterate through the entries loaded from json
        try:
            # The actual keys are tuples...
            previousval = trainer_data[(key,)]
            if previousval == '':  # Trying to load a new field that is not in the previous response's strdata
                previousval = 0
            else:
                previousval = int(previousval) # TODO int or float support
        except ValueError as e:
            previousval = float(trainer_data[(key,)])  # Technically we could do this always
        except KeyError:
            print("Missing key:", key)  # Stat/key is not in DB; but should be added by next survey submission.
            previousval = 0
        except TypeError:
            #print(f"TypeError with trainer_data[{key}], {type(key)}")
            previousval = 0

        # Calculate order offsets used for ordering of survey items
        bronze_thresh = x[1]
        if bronze_thresh == 0:  # 0 indicates NO MEDALS for this stat
            # Always put these medal-less stats at top of render order
            order_offset = 0
            medal_name = ""
        else:  # All other categories; lower orders for higher badge numbers, displayed first
            # TODO(enhancement): If a state is zero, set the order_offset even higher...
            order_offset = 400
            medal_idx = 1  # 1/2/3/4/5 none/bronze/silver/gold/platinum
            while medal_idx < 5 and previousval >= x[medal_idx]:
                order_offset -= 100
                medal_idx += 1
            medal_name = f"({MEDALS[medal_idx-1]})"

            # Special cases
            if key == "Vivillon Collector":
                order_offset = 499  # hardcode this one to be last before type medals
            elif key in TYPE_MEDALS:
                # Put these after the other medals
                order_offset += 600

        # From CSS stuff, for reference...
        #print(f"    #main-panel .mdl-grid > #{x[4]} " + "{ order: " + f"{order}; " + "}")
        stats_list[cnt][0] += order_offset
        if medal_name:
            stats_list[cnt][2] = f"{previousval} {medal_name}"
        else:
            stats_list[cnt][2] = f"{previousval}"

    # Sort things!
    stats_list.sort(key=lambda x: x[0])

    # Returns:
    # stats: (TODO rename?) list of lists. Each sublist is
    #     [Name, img, previous value/None, maximum/None]
    return stats_list


def print_incomplete_warning():
    # Return text (HTML) that will be displayed above the Submit button
    return "<p><b>There are one or more empty required fields, or errors to correct.</b>"

class RegistrationForm(Form):
    username = StringField('Username', [validators.Length(min=4, max=25)])
    age = IntegerField('Age', [validators.NumberRange(min=4, max=25)])
    email = StringField('Email Address', [validators.Length(min=6, max=35)])
    password = PasswordField('New Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords must match')
    ])
    confirm = PasswordField('Repeat Password')
    accept_tos = BooleanField('I accept the TOS', [validators.DataRequired()])


def load_stats():
    return []

class PogoStatsForm(Form):
    """Form class used for the survey fields. See survey_gen()."""
    pass


def survey_gen(stats_list, formclass, _test_default_val=None):
    """Sets survey fields as attrs on form object

    Also inserts sectional breaks.

    Stats with "required = -1" are not not included in the form (survey).

    Args:
        stats_list: list of Stat objects. Each list will drive a input field on the form.
            The order of the list determines the order of the fields on the form.
        formclass: Class of a form object.
        _test_default_val: Default value for all fields. Normally set by
            test code.

    Returns:
        A formclass with attributes set, ready to be instantiated.
    """
    statlist = []  # lookup of attribute names on the FormClass which hold Field objects
    statdivider = []  # list of booleans: when True, jinja2 template script will add a divider after the stat
    # TODO(enhancement) this is stupidly brittle? Every time I add a new non-badge stat...? or if we get too many badges
    # See also shenanigans around line 150 above.
    sections = [20, 100, 200, 300, 400, 500, 600, 700, 800, 900, 10000]
    section_idx = 0
    for order, stat, previous_val_str in stats_list:  # in order already
        # required == -1 stats are no longer collected
        if stat.required == -1:
            continue
        # Strings are "123 (badge level)" so need to strip second part before casting
        # This previous_val_str to previous_val crap would be good to clean up.
        if stat.numtype == "Float":
            previous_val = float(previous_val_str.split()[0])
        else:
            previous_val = int(previous_val_str.split()[0])
        #print(section_idx, order, stat.icon)
        if order > sections[section_idx]:
            statdivider.append(True)
            while order > sections[section_idx]:
                section_idx += 1
        else:
            statdivider.append(False)

        #print(stat.name, previous_val_str)
        if stat.name == 'Trainer Level':
            minimum = max(40, previous_val)
        elif stat.monotonic:
            try:
                minimum = previous_val  # todo floats
            except:
                minimum = 0
        else:
            minimum = 0
        checks = [validators.NumberRange(min=minimum,
                                         max=stat.maximum if stat.maximum > 0 else None)
                     ]
        default_val = _test_default_val
        if previous_val == stat.maximum:  # Note there are no stats with maximums that are also float values.
            # Fill in the field for already-maxed stats.
            default_val = previous_val
        elif stat.required == 0:
            checks = [validators.Optional()] + checks
        if stat.numtype == "Float":
            # TODO fix float input here?
            # Per wtforms docs, DecimalField is usually preferred over FloatField
            print("FLOAT BOX:", stat.name)
            field = DecimalField(stat.name, validators=checks,
                                 default=default_val,
                                 render_kw={"inputmode": "numeric", "type": "number",
                                            "placeholder": previous_val_str,
                                            "previous_val_with_badge": previous_val_str,  # unused
                                            },
                                 )
        else:
            field = IntegerField(stat.name, validators=checks,
                                 default=default_val, # Could use this but it fills a valid value. Use render_kw["placeholder"] instead
                                 render_kw={"inputmode": "numeric", "type": "number",
                                            "placeholder": previous_val_str,
                                            "previous_val_with_badge": previous_val_str,  # unused
                                            },
                                 )
        # Set the field object on our form, which will later generate the HTML
        # We cast str on stat.icon, otherwise we actually have a sqlalchemy object, and this causes
        # thread issues with sqlite at render time.  (This theory didn't prove correct)
        setattr(formclass, str(stat.icon), field)  # using icon because name has spaces in it
        # Order of newly added attrs is preserved in statlist
        statlist.append(stat.icon)

    setattr(formclass, "statlist", statlist)
    setattr(formclass, "statdivider", statdivider)
    # https://gaming.stackexchange.com/a/281007
    trainername = StringField('Trainer Name',
                              validators=[validators.Length(min=4, max=15),
                                          validators.Regexp(regex=r"^[\w\d]+$",
                                                            message="Trainer name can only be letters and numbers"),
                                  ])
    formclass.trainername = trainername
    #print(type(formclass.statlist), formclass.statlist)
    #setattr(form,
    #form = formclass()
    #return form #formclass()
    return formclass


@app.template_filter()
def printx(*args):
    print("HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH")
    print(*args)
    return ''

@app.route("/<month>")
def stats_previous(month=None):
    """month is something like 2022-3"""
    # Should load the previous month's stats
    return send_from_directory('static', month)

# Not sure this is necessary
@app.route("/static/<month>")
def stats_previous_from_static(month=None):
    """month is something like 2022-3"""
    # Should load the previous month's stats
    return send_from_directory('static', month)


@app.route("/")
def stats():
    return send_from_directory('static', 'index.html')


# TODO not implemented
@app.route('/register', methods=['GET', 'POST'])
def register():
    print()
    print("DEBUG")
    form = RegistrationForm(request.form)
    #print(type(form.username), form.username)
    print(dir(request))
    if hasattr(request, "data"):
        print(request.data)
    if hasattr(request, "values"):
        print(request.values)
    if request.method == 'POST' and form.validate():
        #user = User(form.username.data, form.email.data,
        #            form.password.data)
        #db_session.add(user)
        print(form)
        print(dir(form))
        print("skipped db_session.add call")
        flash('Thanks for registering')

        return redirect(url_for('login'))
    return render_template('register.html', form=form,
                           zip=zip, type=type, print=print,
                           )

@app.route('/survey/<username>', methods=['GET', 'POST'])
def fill_survey_for_user(username=None):
    # TODO sanitize the username string? Check: What does the decorator do already?
    return fill_survey(username)

@app.route('/survey', methods=['GET', 'POST'])
@app.route('/survey/', methods=['GET', 'POST'])
def fill_survey(user=None):
    # Generate a stats list, either default order, or order by user's badge levels if known
    session = Session(engine, autoflush=True)
    stats_list = get_survey_data_in_survey_order(session=session, user=user)

    PogoForm = survey_gen(stats_list, PogoStatsForm)
    try:
        form = PogoForm(request.form)
        real_function_call = True  # TODO cleanup
        # These are debug stuff...
        print("")
        if hasattr(request, "values"):
            print(request.values)
    except RuntimeError:  # likely "Working outside of request context"
        # Presumably this is because we're testing stuff and request isn't defined.
        form = PogoForm()
        real_function_call = False  # TODO cleanup

    # Prefill trainername field
    if user:
        form.trainername.data = user

    html_out = "placeholder"
    print("", file=sys.stderr)
    try:
        print("SUBMISSION HERE - got request type", request.method)
        if hasattr(request, "values"):
            print("Survey values given were:", request.values)
        request_method = request.method
        form_validated = form.validate()
    except RuntimeError:
        # e.g. app.py was run with --test-get-survey-data or similar option
        request_method = 'POST'
        form_validated = True
    # POST via Submit button on survey with validation passing
    if request_method == 'POST' and form_validated:
        # If valid
            # Display validation success
            # Save in DB
            # Display save success
            # Redirect to user history page
        if session:  # is set up
            response = Response.save_response(session, response_values=request.values)
            print(response)
            session.commit()
            session.flush()

            # Submission page
            # <pre> tags preserve the tab characters, so users can paste data into spreadsheets
            html_out = "Thanks for the submission! Stats will be regenerated on the 1st.<p>" \
                    "But here's the raw data you submitted if you want to back it up for now:<p>" \
                    "<pre>" \
                    + "<br>".join([f"{k}:\t{v}" for k, v in request.values.items()]) \
                    + "</pre>"
        else:
            print("skipped db_session.add call")
        # TODO subsequent HTML or redirect

    else:
        #print("DEBUG HERE - got", request.method)
        print("RENDER HERE:")

        # Print a helpful warning if there are errors in the survey (i.e. validation failed)
        # otherwise, no-op.
        if request_method == 'POST' and not form_validated:
            print("THERE WERE INCOMPLETE STATS:")
            piw = print_incomplete_warning
        else:
            piw = lambda: ""

        try:
            html_out = render_template('survey_template.html', form=form,
                                       zip=zip, type=type, print=print,
                                       print_incomplete_warning=piw,
                                       )
        except RuntimeError:
            pass

    try:
        session.close()
    except:
        pass

    return html_out


@app.route('/test_survey/', methods=['GET', 'POST'])
def fill_test_survey():
    # Generate a stats list, either default order, or order by user's badge levels if known
    session = Session(engine, autoflush=True)
    stats_list = get_survey_data_in_survey_order(session=session, user="test")

    PogoForm = survey_gen(stats_list, PogoStatsForm)
    try:
        form = PogoForm(request.form)
        real_function_call = True  # TODO cleanup
        # These are debug stuff...
        print("")
        if hasattr(request, "values"):
            print(request.values)
    except RuntimeError:  # likely "Working outside of request context"
        # Presumably this is because we're testing stuff and request isn't defined.
        form = PogoForm()
        real_function_call = False  # TODO cleanup

    # Prefill trainername field
    if user:
        form.trainername.data = user
    # Button for loading a user's past submission is done in the jinja template + JS

    html_out = "placeholder"
    print("", file=sys.stderr)
    print("DEBUG HERE - got", request.method)
    if hasattr(request, "values"):
        print(request.values)
    if request.method == 'POST' and form.validate():
        # If valid
            # Display validation success
            # Save in DB
            # Display save success
            # Redirect to user history page
        if session:  # is set up
            response = Response.save_response(session, response_values=request.values)
            print("Raw saved response object:", response)  # TODO delete this? It just prints a python object identifier I think?
            session.commit()
            session.flush()

            # From example
            #user = User(form.username.data, form.email.data,
            #            form.password.data)
            #db_session.add(user)
            html_out = "Thanks for the submission! Sorry, this isn't more complete yet.<p>" \
                    "But here's the raw data you submitted if you want to back it up for now:<p>" \
                    + str(request.values)
        else:
            print("skipped db_session.add call")
        # TODO subsequent HTML or redirect

    else:
        print("DEBUG HERE - got", request.method)
        print("RENDER HERE:")
        if request_method == 'POST' and form_validated:
            piw = print_incomplete_warning
        else:  # GET
            piw = lambda: ""

        html_out = render_template('survey_template.html', form=form,
                                   zip=zip, type=type, print=print,
                                   print_incomplete_warning=piw,
                                   )

    try:
        session.close()
    except:
        pass

    return html_out


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("secret_key", action='store')
    parser.add_argument("--test-get-survey-data", action='store_true',
                        help="Test just the loading of the survey data, to verify e.g. "
                        "it's in the order expected.")
    parser.add_argument("--test-user", action='store', default=None)
    args = parser.parse_args()

    if True: # Later can support alternate
        db_specifier = LOCAL_DB_SPECIFIER
        print(f"Using: {LOCAL_DB_SPECIFIER}")

    engine = create_engine(db_specifier)

    if args.test_get_survey_data:
        # Why autoflush?
        session = Session(engine, autoflush=True)
        get_survey_data_in_survey_order(session, user=args.test_user)
        exit(0)

    app.secret_key = args.secret_key

    try:
        app.run()
    except (BaseException, Exception) as e:
        # TODO no cleanup here; used to do cleanup on a global session object here...
        print("Cleanup finished successfully!")

else:
    print("Note that db saving isn't set up")
    print("WARNING TEST MODE - SECRET KEY NOT SECURE")
    app.secret_key = "UNSET"

