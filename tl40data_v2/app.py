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
from wtforms import Form, BooleanField, DecimalField, StringField, IntegerField, PasswordField, validators
from flask_wtf import FlaskForm
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import OperationalError
from sqlalchemy import create_engine
from sqlalchemy.engine import ExceptionContext

# Local
from tables import Stat, Response, Trainer
from settings import LOCAL_DB_SPECIFIER


STATS = []
PogoForm = None

session = None

app = Flask(__name__)


def get_survey_data_in_survey_order(session, user=None):
    """

    Args:
        session: sqlalchemy session
        user (str): trainer name
        stats: Preloaded information about stat categories and badge thresholds.
            Otherwise query DB for this information
    Returns:
        stats: (TODO rename?) list of lists. Each sublist is
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
        #STATS.append(Stat(name=stat_name, order_idx=cnt,
        stats_list.append([cnt,  # index to sort by later
                           Stat(name=stat_name, # order_idx=cnt,  # Probably don't need this order since we're not saving this object to DB...
                                **dict(zip(stat_keys, stat_vals[stat_name]))),
                           0,  # previous value
                           ])

    ## TODO user data will eventually factor in here too
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
        trainer_data = trainer.get_newest_response(session)  # May be None for newly added trainer
        if trainer_data is None:
            print(f"Got NO data for trainer {user}..", file=sys.stderr)
        else:
            print(f"Got trainer {user} data.. non-None? {trainer_data != None}", file=sys.stderr)

    #if trainer_data:
    # Calculate offsets for each stat category
    # For each stat category, iterate through its badge amounts, calculating offsets based on previous stat amount
    # NOTE static_stat_info should be the same as categories was in my firefox CSS-tweak script??
    #for cnt, key in enumerate(categories):
    # TODO static_stat_info vs stats_list
    #for cnt, key in enumerate(static_stat_info["data"]):
    for cnt, key in enumerate(stat_vals):  # iterate through the entries loaded from json
        # Note: key is e.g. "Unique Species Caught"
        #x = categories[key]  # We don't actually use the key names in this script...
        #x = static_stat_info["data"][key]  # We don't actually use the data key names in this script...
        # TODO we could probably just iterate over the .values()...
        x = stat_vals[key]  # We don't actually use the key names in this script...
        #= x[4]
        statname = x[7]
        # This conditional... not sure we need it; should blow up instead
        #if statname not in column_lookup:
        #    #print("SKIPPING:", x[4])
        #    continue  # Skip some things that aren't in the survey, like Alola and Hisui dexes
        try:
            previousval = trainer_data[key]
        except KeyError:
            previousval = 0

        bronze_thresh = x[1]
        if bronze_thresh == 0:  # Always put these level-less stats at top of render order
            # TODO revisit and start from 0, rather than using negative numbers
            #order = -400 + cnt
            order_offset = -400
        else:  # All other categories, lower orders for higher badge numbers, displayed first
            #order = cnt
            order_offset = 0
            medal_idx = 1  # 1/2/3/4 bronze/silver/gold/platinum
            while medal_idx < 5 and previousval > x[medal_idx]:
                #order -= 100
                order_offset -= 100
                medal_idx += 1

        # From CSS stuff, for reference...
        #print(f"    #main-panel .mdl-grid > #{x[4]} " + "{ order: " + f"{order}; " + "}")
        stats_list[cnt][0] += order_offset
        stats_list[cnt][2] = previousval

    # Sort things!

    # Returns:
    # stats: (TODO rename?) list of lists. Each sublist is
    #     [Name, img, previous value/None, maximum/None]
    return stats_list


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
    pass


def survey_gen(stats_list, formclass):
    """Sets survey fields as attrs on form object

    Args:
        stats_list: list of Stat objects. Each list will drive a input field on the form.
            The order of the list determines the order of the fields on the form.
        formclass: Class of a form object. 

    Returns:
        A class with attributes set, ready to be instantiated.
    """
    statlist = []  # lookup of attribute names on the FormClass which hold Field objects
    for order, stat, previous_val in stats_list:  # in order already
        # TODO
        placeholder = 123
        if stat.name == 'Trainer Level':
            minimum = 40
        else:
            minimum = 0
        checks = [validators.NumberRange(min=minimum,
                                             max=stat.maximum if stat.maximum > 0 else None)
                     ]
        if not stat.required:
            checks = [validators.Optional()] + checks
        if stat.numtype == "Float":
            # Per wtforms docs, DecimalField is usually preferred over FloatField
            field = DecimalField(stat.name, validators=checks,
                                 render_kw={"inputmode": "numeric", "type": "number"},
                                 )
        else:
            field = IntegerField(stat.name, validators=checks,
                                 # TODO move this image part to a setatrr call?
                                 #image="imgs/" + stat.icon + ".png",  # accessed with statlist[i].kwargs['image']
                                 render_kw={"inputmode": "numeric", "type": "number",
                                     "placeholder": previous_val},
                                 )
        setattr(formclass, stat.icon, field)  # using icon because name has spaces in it
        #statlist.append(field)  # Problem is this is the unbound field, DUH
        #statlist.append(getattr(formclass, stat.icon))
        statlist.append(stat.icon)
    setattr(formclass, "statlist", statlist)
    # https://gaming.stackexchange.com/a/281007
    trainername = StringField('Trainer Name',
                              validators=[validators.Length(min=4, max=15),
                                          validators.Regexp(regex="^[\w\d]+$",
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
    # Should load the previous month's stats
    return send_from_directory('static', month)

# Not sure this is necessary
@app.route("/static/<month>")
def stats_previous_from_static(month=None):
    # Should load the previous month's stats
    return send_from_directory('static', month)


@app.route("/")
def stats():
    return send_from_directory('static', 'index.html')


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
    return render_template('register.html', form=form)

@app.route('/survey/<username>', methods=['GET', 'POST'])
def fill_survey_for_user(username=None):
    return fill_survey(username)

@app.route('/survey', methods=['GET', 'POST'])
def fill_survey(user=None):
    # Fill in the data for the form generation
    #global STATS
    #if not STATS:  # TODO find a main() method or whatever convention flask uses and run this here...
    #    get_survey_data_in_survey_order(None, user=user)
    #stats_list = STATS

    # Generate a stats list, either default order, or order by user's badge levels if known
    global session
    stats_list = get_survey_data_in_survey_order(session=session, user=user)

    global PogoForm
    if PogoForm is None:
        # This will return TODO
        PogoForm = survey_gen(stats_list, PogoStatsForm)
    form = PogoForm(request.form)

    # Prefill trainername field
    if user:
        form.trainername.data = user

    html_out = "placeholder"
    print("")
    print("DEBUG HERE - got", request.method)
    if hasattr(request, "values"):
        print(request.values)
    if request.method == 'POST' and form.validate():
        # If valid
            # Display validation success
            # Save in DB
            # Display save success
            # Redirect to user history page
        #global session  # Delete this; I do it above; 2-26
        if session:  # is set up
            response = Response.save_response(session, response_values=request.values)
            print(response)
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
        #flash('Thanks for ...')

        # TODO subsequent HTML or redirect

    else:
        print("DEBUG HERE - got", request.method)
        print("RENDER HERE:")
        html_out = render_template('survey_template.html', form=form)
    return html_out


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("secret_key", action='store')
    parser.add_argument("--test-get-survey-data", action='store_true')
    parser.add_argument("--test-user", action='store', default=None)
    args = parser.parse_args()

    db_specifier = LOCAL_DB_SPECIFIER
    engine = create_engine(db_specifier)
    session = Session(engine, autoflush=True)

    if args.test_get_survey_data:
        print("TESTING get_survey_data_in_survey_order")
        get_survey_data_in_survey_order(session, user=args.test_user)
        exit(0)

    app.secret_key = args.secret_key

    try:
        app.run()
    except (BaseException, Exception) as e:
        print(f"Caught {e}; closing DB connection and exiting.")
        try:
            session.close()
        except:
            pass
        print("Cleanup finished successfully!")

else:
    print("Note that db saving isn't set up")
    print("WARNING TEST MODE - SECRET KEY NOT SECURE")
    app.secret_key = "UNSET"

